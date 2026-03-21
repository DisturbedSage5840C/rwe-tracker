"""Social mention model for public social chatter around drugs."""

from __future__ import annotations

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class SocialMention(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """Social media mention enriched with normalized dimensions."""

    __tablename__ = "social_mentions"

    drug_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("drugs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    platform: Mapped[str] = mapped_column(String(64), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True, index=True)
    post_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    author_handle: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    mention_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    engagement_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    sentiment_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    overall_sentiment: Mapped[float | None] = mapped_column(Float, nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(384), nullable=True)
    mention_metadata: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, server_default="{}")
