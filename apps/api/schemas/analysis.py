"""Schemas for cross-drug comparisons, trends, and gap breakdowns."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from pydantic import BaseModel


class DrugComparisonItem(BaseModel):
    """Per-drug comparison metric projection."""

    drug_id: UUID
    drug_name: str
    latest_gap_score: float | None
    latest_perception_score: float | None


class TrendPoint(BaseModel):
    """Time-series point used in trend responses."""

    date: date
    perception_score: float
    trial_score: float
    gap_score: float


class GapBreakdown(BaseModel):
    """Gap dimensions for a specific drug report baseline."""

    efficacy: float | None
    safety: float | None
    tolerability: float | None
    convenience: float | None
    quality_of_life: float | None


class TrendResponse(BaseModel):
    """Trend payload wrapper for analysis route."""

    drug_id: UUID
    granularity: str
    points: list[TrendPoint]


class CompareResponse(BaseModel):
    """Cross-drug comparison response payload."""

    items: list[DrugComparisonItem]


class GapResponse(BaseModel):
    """Gap breakdown response payload."""

    drug_id: UUID
    latest_report_id: UUID | None
    breakdown: GapBreakdown
