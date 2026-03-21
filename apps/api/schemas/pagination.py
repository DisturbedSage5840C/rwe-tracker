"""Cursor pagination schemas and cursor serialization helpers."""

from __future__ import annotations

import base64
from datetime import datetime
from typing import Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, Field, ValidationError
from pydantic.generics import GenericModel

T = TypeVar("T")


class CursorParams(BaseModel):
    """Cursor pagination query parameters."""

    cursor: str | None = None
    limit: int = Field(default=20, ge=1, le=100)


class CursorToken(BaseModel):
    """Opaque cursor payload encoded into base64 token."""

    created_at: datetime
    id: UUID


class CursorPage(GenericModel, Generic[T]):
    """Generic cursor page response container."""

    items: list[T]
    next_cursor: str | None = None
    prev_cursor: str | None = None


def encode_cursor(token: CursorToken) -> str:
    """Encode cursor token to URL-safe opaque string."""
    raw = token.model_dump_json().encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("utf-8")


def decode_cursor(cursor: str) -> CursorToken:
    """Decode URL-safe cursor string into typed cursor token."""
    try:
        payload = base64.urlsafe_b64decode(cursor.encode("utf-8")).decode("utf-8")
        return CursorToken.model_validate_json(payload)
    except (ValidationError, ValueError) as exc:
        raise ValueError("Invalid cursor") from exc
