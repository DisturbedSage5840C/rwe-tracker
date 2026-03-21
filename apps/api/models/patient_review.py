"""Patient review model with normalized sentiment dimensions and embeddings."""

from __future__ import annotations

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class PatientReview(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """Patient-generated review enriched by NLP processing."""

    __tablename__ = "patient_reviews"

    drug_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("drugs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source: Mapped[str] = mapped_column(String(128), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True, index=True)
    source_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    author_handle: Mapped[str | None] = mapped_column(String(255), nullable=True)
    review_text: Mapped[str] = mapped_column(Text, nullable=False)
    review_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    crawled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    engagement_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    sentiment_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    overall_sentiment: Mapped[float | None] = mapped_column(Float, nullable=True)
    efficacy_sentiment: Mapped[float | None] = mapped_column(Float, nullable=True)
    safety_sentiment: Mapped[float | None] = mapped_column(Float, nullable=True)
    tolerability_sentiment: Mapped[float | None] = mapped_column(Float, nullable=True)
    convenience_sentiment: Mapped[float | None] = mapped_column(Float, nullable=True)
    qol_sentiment: Mapped[float | None] = mapped_column(Float, nullable=True)

    embedding: Mapped[list[float] | None] = mapped_column(Vector(384), nullable=True)
    review_metadata: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, server_default="{}")
