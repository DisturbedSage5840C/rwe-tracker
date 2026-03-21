"""Clinical trial model storing normalized trial data for a drug."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class ClinicalTrial(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """Clinical trial record imported from trusted trial registries."""

    __tablename__ = "clinical_trials"

    drug_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("drugs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    nct_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    phase: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str | None] = mapped_column(String(128), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    adverse_event_rate: Mapped[float | None] = mapped_column(nullable=True)
    discontinuation_proxy: Mapped[float | None] = mapped_column(nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
