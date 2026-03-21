"""Response envelope helpers for consistent API output shape."""

from __future__ import annotations

from fastapi import Request

from apps.api.schemas.envelope import APIEnvelope, MetaData


def ok(data, request: Request, **meta_kwargs):
    """Build standard envelope with request-scoped metadata."""
    request_id = getattr(request.state, "request_id", None)
    meta = MetaData(request_id=request_id, **meta_kwargs)
    return APIEnvelope(data=data, meta=meta, errors=None)
