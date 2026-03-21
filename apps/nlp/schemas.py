"""Request and response schemas for NLP inference and gap analysis endpoints."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class AspectResult(BaseModel):
    """Aspect-level sentiment projection for domain-specific dimensions."""

    sentiment: float | None
    mention_count: int
    example_sentences: list[str]


class SentimentResult(BaseModel):
    """Single text sentiment and embedding inference output."""

    vader_compound: float
    transformer_label: Literal["positive", "negative", "neutral"]
    transformer_confidence: float
    composite_score: float
    aspects: dict[str, AspectResult]
    embedding: list[float]
    processing_time_ms: float


class AnalyzeRequest(BaseModel):
    """Single text analysis request."""

    text: str = Field(min_length=1)


class AnalyzeBatchRequest(BaseModel):
    """Batch text analysis request."""

    texts: list[str] = Field(min_length=1, max_length=500)
    batch_size: int | None = Field(default=None, ge=1, le=500)


class EmbedRequest(BaseModel):
    """Embedding generation request."""

    text: str = Field(min_length=1)


class GapDimension(BaseModel):
    """Gap statistics per domain dimension."""

    dimension: str
    clinical_score: float
    real_world_mean: float
    gap_magnitude: float
    p_value: float
    ci_lower: float
    ci_upper: float
    significant: bool


class Insight(BaseModel):
    """Narrative insight generated from significant gaps."""

    dimension: str
    severity: Literal["critical", "high", "moderate"]
    recommendation: str


class GapReport(BaseModel):
    """Complete gap analysis report payload."""

    drug_id: str
    dimensions: list[GapDimension]
    overall_score: float
    insights: list[Insight]


class GapAnalysisRequest(BaseModel):
    """Gap analysis request combining trial and real-world aggregate inputs."""

    drug_id: str
    clinical_data: dict[str, float]
    patient_reviews: list[dict]
    social_mentions: list[dict]
