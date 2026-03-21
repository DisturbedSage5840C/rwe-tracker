"""Analysis job model for background NLP processing status tracking."""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class AnalysisJob(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """Job status projection for user-facing polling APIs."""

    __tablename__ = "analysis_jobs"

    drug_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("drugs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    celery_task_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    result_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
