"""Healthcheck endpoints for API liveness and readiness probes."""

from __future__ import annotations

from fastapi import APIRouter, Request

from apps.api.limiter import UNAUTH_LIMIT, limiter
from apps.api.response import ok
from apps.api.schemas.envelope import APIEnvelope

router = APIRouter()


@router.get("/health")
@limiter.limit(UNAUTH_LIMIT)
async def healthcheck(request: Request) -> APIEnvelope[dict[str, str]]:
    """Simple probe endpoint for load balancers and compose healthchecks."""
    return ok({"status": "ok"}, request)
