"""Reusable API response envelope schema used by all endpoints."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field
from pydantic.generics import GenericModel

T = TypeVar("T")


class ErrorDetail(BaseModel):
    """API error detail item for non-success responses."""

    code: str
    message: str


class MetaData(BaseModel):
    """Response metadata container for paging and tracing hints."""

    request_id: str | None = None
    next_cursor: str | None = None
    prev_cursor: str | None = None
    count: int | None = None


class APIEnvelope(GenericModel, Generic[T]):
    """Consistent success payload envelope across the API surface."""

    data: T
    meta: MetaData = Field(default_factory=MetaData)
    errors: list[ErrorDetail] | None = None
