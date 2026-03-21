"""Drug CRUD and analysis orchestration service layer."""

from __future__ import annotations

import uuid

from celery.result import AsyncResult
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.models.user import User
from apps.api.schemas.drug import AnalyzeJobStatusResponse, AnalyzeTriggerResponse, DrugCreateRequest
from apps.api.services.repositories import AnalysisJobRepository, DrugRepository, PerceptionReportRepository
from apps.common.errors import NotFoundError
from apps.worker.celery_app import celery_app


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

        await self.analysis_job_repository.update_status(job, state, payload)
        await self.session.commit()

        return AnalyzeJobStatusResponse(
            job_id=job.id,
            celery_task_id=job.celery_task_id,
            status=state,
            result_payload=payload,
        )
