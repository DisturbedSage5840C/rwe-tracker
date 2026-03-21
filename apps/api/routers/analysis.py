"""Analysis routes exposing compare, trend, and gap breakdown endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request

from apps.api.deps import get_analysis_service, require_role
from apps.api.limiter import AUTH_LIMIT, limiter
from apps.api.models.base import UserRole
from apps.api.models.user import User
from apps.api.response import ok
from apps.api.schemas.analysis import CompareResponse, GapResponse, TrendResponse
from apps.api.schemas.envelope import APIEnvelope
from apps.api.services.analysis_service import AnalysisService
from apps.common.errors import ValidationAppError

router = APIRouter()


@router.get("/compare", response_model=APIEnvelope[CompareResponse])
@limiter.limit(AUTH_LIMIT)
async def compare_drugs(
    request: Request,
    drug_ids: Annotated[str, Query()],
    current_user: Annotated[User, Depends(require_role(UserRole.VIEWER))],
    analysis_service: Annotated[AnalysisService, Depends(get_analysis_service)],
) -> APIEnvelope[CompareResponse]:
    """Description: compare latest perception metrics across selected drugs.
    Required role: VIEWER.
    Example curl: curl -X GET 'http://localhost:8000/analysis/compare?drug_ids=<id1>&drug_ids=<id2>' -H 'Authorization: Bearer <access_token>'
    """
    try:
        parsed_ids = [UUID(item.strip()) for item in drug_ids.split(",") if item.strip()]
    except ValueError as exc:
        raise ValidationAppError("Malformed UUID in drug_ids query parameter") from exc
    result = await analysis_service.compare_drugs(current_user.organization_id, parsed_ids)
    return ok(result, request)


@router.get("/trends/{drug_id}", response_model=APIEnvelope[TrendResponse])
@limiter.limit(AUTH_LIMIT)
async def trends(
    request: Request,
    drug_id: UUID,
    current_user: Annotated[User, Depends(require_role(UserRole.VIEWER))],
    analysis_service: Annotated[AnalysisService, Depends(get_analysis_service)],
    days: int = Query(default=90, ge=1, le=365),
    granularity: str = Query(default="daily", pattern="^(daily|weekly|monthly)$"),
) -> APIEnvelope[TrendResponse]:
    """Description: return sentiment trend time-series for selected drug.
    Required role: VIEWER.
    Example curl: curl -X GET 'http://localhost:8000/analysis/trends/<drug_id>?days=90&granularity=daily' -H 'Authorization: Bearer <access_token>'
    """
    result = await analysis_service.trends(current_user.organization_id, drug_id, days, granularity)
    return ok(result, request)


@router.get("/gaps/{drug_id}", response_model=APIEnvelope[GapResponse])
@limiter.limit(AUTH_LIMIT)
async def gaps(
    request: Request,
    drug_id: UUID,
    current_user: Annotated[User, Depends(require_role(UserRole.VIEWER))],
    analysis_service: Annotated[AnalysisService, Depends(get_analysis_service)],
) -> APIEnvelope[GapResponse]:
    """Description: return detailed perception gap breakdown by dimension.
    Required role: VIEWER.
    Example curl: curl -X GET http://localhost:8000/analysis/gaps/<drug_id> -H 'Authorization: Bearer <access_token>'
    """
    result = await analysis_service.gap_breakdown(current_user.organization_id, drug_id)
    return ok(result, request)
