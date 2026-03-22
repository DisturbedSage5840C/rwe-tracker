"""Drug CRUD and analysis orchestration service layer."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from celery.result import AsyncResult
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.models.user import User
from apps.api.schemas.drug import AnalyzeJobStatusResponse, AnalyzeTriggerResponse, DrugCreateRequest
from apps.api.services.repositories import AnalysisJobRepository, DrugRepository, PerceptionReportRepository
from apps.common.errors import NotFoundError
from apps.worker.celery_app import celery_app

TERMINAL_STATES = {"SUCCESS", "FAILURE", "REVOKED"}


class DrugService:
    """Business operations for organization-scoped drug resources."""

    def __init__(
        self,
        session: AsyncSession,
        drug_repository: DrugRepository,
        report_repository: PerceptionReportRepository,
        analysis_job_repository: AnalysisJobRepository,
    ) -> None:
        self.session = session
        self.drug_repository = drug_repository
        self.report_repository = report_repository
        self.analysis_job_repository = analysis_job_repository

    async def create_drug(self, payload: DrugCreateRequest, current_user: User):
        """Create a drug under current user's organization."""
        drug = await self.drug_repository.create(
            organization_id=current_user.organization_id,
            name=payload.name,
            normalized_name=payload.name.strip().lower(),
            indication=payload.indication,
            manufacturer=payload.manufacturer,
        )
        await self.session.commit()
        await self.session.refresh(drug)
        return drug

    async def list_drugs(self, organization_id: uuid.UUID, cursor: str | None, limit: int):
        """Return cursor-page list of drugs for tenant organization."""
        return await self.drug_repository.list_for_org_paginated(organization_id, cursor, limit)

    async def get_drug_detail(self, drug_id: uuid.UUID, organization_id: uuid.UUID):
        """Fetch drug with latest report summary projection."""
        drug = await self.drug_repository.get_by_id_for_org(drug_id, organization_id)
        if not drug:
            raise NotFoundError("Drug not found")
        latest_report = await self.report_repository.get_latest_for_drug(drug.id)
        return drug, latest_report

    async def delete_drug(self, drug_id: uuid.UUID, organization_id: uuid.UUID) -> None:
        """Soft-delete a drug scoped to tenant."""
        drug = await self.drug_repository.get_by_id_for_org(drug_id, organization_id)
        if not drug:
            raise NotFoundError("Drug not found")
        await self.drug_repository.soft_delete(drug)
        await self.session.commit()

    async def list_reports(self, drug_id: uuid.UUID, organization_id: uuid.UUID, cursor: str | None, limit: int):
        """List reports for a drug after tenant ownership validation."""
        drug = await self.drug_repository.get_by_id_for_org(drug_id, organization_id)
        if not drug:
            raise NotFoundError("Drug not found")
        return await self.report_repository.list_for_drug_paginated(drug_id, cursor, limit)

    async def trigger_analysis(self, drug_id: uuid.UUID, current_user: User) -> AnalyzeTriggerResponse:
        """Send asynchronous analysis task and persist job tracking row."""
        drug = await self.drug_repository.get_by_id_for_org(drug_id, current_user.organization_id)
        if not drug:
            raise NotFoundError("Drug not found")

        latest_job = await self.analysis_job_repository.get_latest_for_drug(current_user.organization_id, drug.id)
        if latest_job and latest_job.created_at >= datetime.now(UTC) - timedelta(minutes=2):
            latest_state = AsyncResult(latest_job.celery_task_id, app=celery_app).state
            if latest_state not in TERMINAL_STATES:
                return AnalyzeTriggerResponse(
                    job_id=latest_job.id,
                    celery_task_id=latest_job.celery_task_id,
                    status=latest_state,
                )

        task = celery_app.send_task(
            "analysis.trigger_full",
            args=[str(drug.id), str(current_user.organization_id), drug.name],
        )
        job = await self.analysis_job_repository.create(
            drug_id=drug.id,
            organization_id=current_user.organization_id,
            celery_task_id=task.id,
        )
        await self.session.commit()
        await self.session.refresh(job)

        return AnalyzeTriggerResponse(job_id=job.id, celery_task_id=job.celery_task_id, status=job.status)

    async def get_analysis_job_status(
        self,
        drug_id: uuid.UUID,
        job_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> AnalyzeJobStatusResponse:
        """Read status from Celery and project it onto stored job row."""
        job = await self.analysis_job_repository.get_for_org(job_id, organization_id, drug_id)
        if not job:
            raise NotFoundError("Analysis job not found")

        result = AsyncResult(job.celery_task_id, app=celery_app)
        state = result.state
        payload = result.result if isinstance(result.result, dict) else {}

        chord_id = payload.get("chord_id") if isinstance(payload, dict) else None
        if chord_id:
            task_states: dict[str, str] = {}
            header_task_ids = payload.get("tasks") if isinstance(payload.get("tasks"), dict) else {}
            header_keys = ("openfda", "reddit", "clinical_trials")
            header_progress_total = 0
            callback_progress_value = 0
            client = redis.from_url(celery_app.conf.result_backend, decode_responses=True)
            try:
                for key in header_keys:
                    task_id = header_task_ids.get(key)
                    if not task_id:
                        continue

                    header_state = AsyncResult(task_id, app=celery_app).state
                    task_states[key] = header_state

                    if header_state in TERMINAL_STATES:
                        header_progress_total += 100
                        continue

                    raw_progress = await client.get(f"job:{task_id}:progress")
                    try:
                        header_progress_total += max(0, min(100, int(raw_progress or 0)))
                    except (TypeError, ValueError):
                        header_progress_total += 0

                callback_raw_progress = await client.get(f"job:{chord_id}:progress")
                try:
                    callback_progress_value = max(0, min(100, int(callback_raw_progress or 0)))
                except (TypeError, ValueError):
                    callback_progress_value = 0
            finally:
                await client.close()

            callback_result = AsyncResult(chord_id, app=celery_app)
            state = callback_result.state
            callback_payload = callback_result.result
            if isinstance(callback_payload, dict):
                payload = callback_payload
            elif state == "FAILURE":
                payload = {"error": str(callback_payload)}
            else:
                previous_progress = 0
                if isinstance(job.result_payload, dict):
                    existing_progress = job.result_payload.get("progress")
                    if isinstance(existing_progress, int | float):
                        previous_progress = max(0, min(99, int(existing_progress)))

                header_average = int(header_progress_total / len(header_keys)) if header_keys else 0
                progress = min(90, int(header_average * 0.9))
                if header_average >= 100:
                    progress = max(progress, 90 + int(callback_progress_value * 0.09))

                completed_header_count = sum(1 for status_name in task_states.values() if status_name in TERMINAL_STATES)
                elapsed_seconds = max(0, int((datetime.now(UTC) - job.created_at).total_seconds()))
                if header_average < 100:
                    phase_floor_by_completed = {
                        0: min(45, 5 + elapsed_seconds // 6),
                        1: min(70, 35 + elapsed_seconds // 6),
                        2: min(88, 65 + elapsed_seconds // 8),
                    }
                    progress = max(progress, phase_floor_by_completed.get(completed_header_count, progress))
                    progress = min(progress, 89)
                else:
                    callback_floor = min(98, 90 + elapsed_seconds // 20)
                    progress = max(progress, callback_floor)

                if state in {"PENDING", "STARTED", "RETRY", "RUNNING"}:
                    progress = max(progress, previous_progress)

                payload = {
                    "status": state.lower(),
                    "chord_id": chord_id,
                    "progress": progress,
                    "tasks": task_states,
                }

        await self.analysis_job_repository.update_status(job, state, payload)
        await self.session.commit()

        return AnalyzeJobStatusResponse(
            job_id=job.id,
            celery_task_id=job.celery_task_id,
            status=state,
            result_payload=payload,
        )
