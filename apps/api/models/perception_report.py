"""Perception report model for generated trial-vs-reality insights."""

from __future__ import annotations

import uuid

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class PerceptionReport(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """Generated analytics snapshot for a drug."""

    __tablename__ = "perception_reports"

    drug_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("drugs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    perception_score: Mapped[float] = mapped_column(Float, nullable=False)
    trial_score: Mapped[float] = mapped_column(Float, nullable=False)
    gap_score: Mapped[float] = mapped_column(Float, nullable=False)
    confidence_interval_lower: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence_interval_upper: Mapped[float | None] = mapped_column(Float, nullable=True)
    sample_size_reviews: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sample_size_social: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    methodology_version: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
