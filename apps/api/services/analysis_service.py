"""Analysis service for comparison, trends, and gap breakdown endpoints."""

from __future__ import annotations

import uuid

from apps.api.schemas.analysis import CompareResponse, DrugComparisonItem, GapBreakdown, GapResponse, TrendPoint, TrendResponse
from apps.api.services.repositories import DrugRepository, PatientReviewRepository, PerceptionReportRepository
from apps.common.errors import NotFoundError


class AnalysisService:
    """Cross-drug analytics orchestration for dashboard analysis routes."""

    def __init__(
        self,
        drug_repository: DrugRepository,
        report_repository: PerceptionReportRepository,
        patient_review_repository: PatientReviewRepository,
    ) -> None:
        self.drug_repository = drug_repository
        self.report_repository = report_repository
        self.patient_review_repository = patient_review_repository

    async def compare_drugs(self, organization_id: uuid.UUID, drug_ids: list[uuid.UUID]) -> CompareResponse:
        """Return latest score comparison across selected drugs."""
        items: list[DrugComparisonItem] = []
        rows = await self.report_repository.list_latest_for_drugs(drug_ids)
        for drug_id, gap_score, perception_score in rows:
            drug = await self.drug_repository.get_by_id_for_org(drug_id, organization_id)
            if not drug:
                continue
            items.append(
                DrugComparisonItem(
                    drug_id=drug.id,
                    drug_name=drug.name,
                    latest_gap_score=gap_score,
                    latest_perception_score=perception_score,
                )
            )
        return CompareResponse(items=items)

    async def trends(self, organization_id: uuid.UUID, drug_id: uuid.UUID, days: int, granularity: str) -> TrendResponse:
        """Return time-series report metrics for a single drug."""
        drug = await self.drug_repository.get_by_id_for_org(drug_id, organization_id)
        if not drug:
            raise NotFoundError("Drug not found")

        reports = await self.report_repository.list_trends(drug_id, days)
        points = [
            TrendPoint(
                date=report.created_at.date(),
                perception_score=report.perception_score,
                trial_score=report.trial_score,
                gap_score=report.gap_score,
            )
            for report in reports
        ]
        return TrendResponse(drug_id=drug_id, granularity=granularity, points=points)

    async def gap_breakdown(self, organization_id: uuid.UUID, drug_id: uuid.UUID) -> GapResponse:
        """Return latest report id and sentiment dimension breakdown."""
        drug = await self.drug_repository.get_by_id_for_org(drug_id, organization_id)
        if not drug:
            raise NotFoundError("Drug not found")

        latest = await self.report_repository.get_latest_for_drug(drug_id)
        dimensions = await self.patient_review_repository.get_dimension_averages(drug_id)

        return GapResponse(
            drug_id=drug_id,
            latest_report_id=latest.id if latest else None,
            breakdown=GapBreakdown(**dimensions),
        )
