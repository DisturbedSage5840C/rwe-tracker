"""Drug and report schemas used by CRUD and analysis trigger routes."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PerceptionReportSummary(BaseModel):
    """Compact report shape returned in drug detail endpoints."""

    id: UUID
    created_at: datetime
    perception_score: float
    trial_score: float
    gap_score: float
    confidence_interval_lower: float | None
    confidence_interval_upper: float | None
    methodology_version: str


class DrugCreateRequest(BaseModel):
    """Payload to create a monitored drug entity."""

    name: str = Field(min_length=1, max_length=255)
    indication: str | None = None
    manufacturer: str | None = None


class DrugRead(BaseModel):
    """Drug resource payload."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    name: str
    normalized_name: str
    indication: str | None
    manufacturer: str | None
    created_at: datetime


class DrugDetailRead(DrugRead):
    """Drug payload including latest report projection."""

    latest_report: PerceptionReportSummary | None = None


class PerceptionReportRead(BaseModel):
    """Full perception report payload for report listing."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    drug_id: UUID
    summary: str | None
    perception_score: float
    trial_score: float
    gap_score: float
    confidence_interval_lower: float | None
    confidence_interval_upper: float | None
    sample_size_reviews: int
    sample_size_social: int
    methodology_version: str
    created_at: datetime


class AnalyzeTriggerResponse(BaseModel):
    """Response payload for async analysis trigger."""

    job_id: UUID
    celery_task_id: str
    status: str


class AnalyzeJobStatusResponse(BaseModel):
    """Status payload for polling analysis job progress."""

    job_id: UUID
    celery_task_id: str
    status: str
    result_payload: dict
