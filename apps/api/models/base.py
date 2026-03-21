"""Shared declarative base and mixins for ORM models."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base declarative class for all ORM models."""


class TimestampMixin:
    """Common created/updated timestamps to keep schema DRY."""

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class SoftDeleteMixin:
    """Soft delete fields used to preserve tenant data for auditability."""

    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"), default=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class UUIDPrimaryKeyMixin:
    """UUID primary key mixin for non-guessable identifiers."""

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class UserRole(StrEnum):
    """Role hierarchy for organization-scoped access control."""

    OWNER = "OWNER"
    ADMIN = "ADMIN"
    ANALYST = "ANALYST"
    VIEWER = "VIEWER"
