"""Drug CRUD and analysis trigger routes for organization-scoped resources."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request

from apps.api.deps import get_drug_service, require_role
from apps.api.limiter import AUTH_LIMIT, limiter
from apps.api.models.base import UserRole
from apps.api.models.user import User
from apps.api.response import ok
from apps.api.schemas.drug import (
    AnalyzeJobStatusResponse,
    AnalyzeTriggerResponse,
    DrugCreateRequest,
    DrugDetailRead,
    DrugRead,
    PerceptionReportRead,
)
from apps.api.schemas.envelope import APIEnvelope
from apps.api.schemas.pagination import CursorPage, CursorParams
from apps.api.services.drug_service import DrugService

router = APIRouter()


@router.get("", response_model=APIEnvelope[CursorPage[DrugRead]])
@limiter.limit(AUTH_LIMIT)
async def list_drugs(
    request: Request,
    params: Annotated[CursorParams, Depends()],
    current_user: Annotated[User, Depends(require_role(UserRole.VIEWER))],
    drug_service: Annotated[DrugService, Depends(get_drug_service)],
) -> APIEnvelope[CursorPage[DrugRead]]:
    """Description: list organization drugs with cursor pagination.
    Required role: VIEWER.
    Example curl: curl -X GET 'http://localhost:8000/drugs?limit=20' -H 'Authorization: Bearer <access_token>'
    """
    page = await drug_service.list_drugs(current_user.organization_id, params.cursor, params.limit)
    typed_page = CursorPage[DrugRead](items=[DrugRead.model_validate(item) for item in page.items], next_cursor=page.next_cursor, prev_cursor=page.prev_cursor)
    return ok(typed_page, request, next_cursor=page.next_cursor, prev_cursor=page.prev_cursor, count=len(page.items))


@router.post("", response_model=APIEnvelope[DrugRead])
@limiter.limit(AUTH_LIMIT)
async def create_drug(
    request: Request,
    payload: DrugCreateRequest,
    current_user: Annotated[User, Depends(require_role(UserRole.ANALYST))],
    drug_service: Annotated[DrugService, Depends(get_drug_service)],
) -> APIEnvelope[DrugRead]:
    """Description: create a new monitored drug.
    Required role: ANALYST or higher.
    Example curl: curl -X POST http://localhost:8000/drugs -H 'Authorization: Bearer <access_token>' -H 'Content-Type: application/json' -d '{"name":"Drug X"}'
    """
    created = await drug_service.create_drug(payload, current_user)
    return ok(DrugRead.model_validate(created), request)


@router.get("/{drug_id}", response_model=APIEnvelope[DrugDetailRead])
@limiter.limit(AUTH_LIMIT)
async def get_drug(
    request: Request,
    drug_id: UUID,
    current_user: Annotated[User, Depends(require_role(UserRole.VIEWER))],
    drug_service: Annotated[DrugService, Depends(get_drug_service)],
) -> APIEnvelope[DrugDetailRead]:
    """Description: get drug detail and latest perception report summary.
    Required role: VIEWER.
    Example curl: curl -X GET http://localhost:8000/drugs/<drug_id> -H 'Authorization: Bearer <access_token>'
    """
    drug, latest = await drug_service.get_drug_detail(drug_id, current_user.organization_id)
    detail = DrugDetailRead.model_validate(drug)
    if latest:
        detail.latest_report = {
            "id": latest.id,
            "created_at": latest.created_at,
            "perception_score": latest.perception_score,
            "trial_score": latest.trial_score,
            "gap_score": latest.gap_score,
            "confidence_interval_lower": latest.confidence_interval_lower,
            "confidence_interval_upper": latest.confidence_interval_upper,
            "methodology_version": latest.methodology_version,
        }
    return ok(detail, request)


@router.delete("/{drug_id}", response_model=APIEnvelope[dict])
@limiter.limit(AUTH_LIMIT)
async def delete_drug(
    request: Request,
    drug_id: UUID,
    current_user: Annotated[User, Depends(require_role(UserRole.ADMIN))],
    drug_service: Annotated[DrugService, Depends(get_drug_service)],
) -> APIEnvelope[dict]:
    """Description: soft-delete a monitored drug.
    Required role: ADMIN or OWNER.
    Example curl: curl -X DELETE http://localhost:8000/drugs/<drug_id> -H 'Authorization: Bearer <access_token>'
    """
    await drug_service.delete_drug(drug_id, current_user.organization_id)
    return ok({"deleted": True}, request)


@router.get("/{drug_id}/reports", response_model=APIEnvelope[CursorPage[PerceptionReportRead]])
@limiter.limit(AUTH_LIMIT)
async def list_reports(
    request: Request,
    drug_id: UUID,
    params: Annotated[CursorParams, Depends()],
    current_user: Annotated[User, Depends(require_role(UserRole.VIEWER))],
    drug_service: Annotated[DrugService, Depends(get_drug_service)],
) -> APIEnvelope[CursorPage[PerceptionReportRead]]:
    """Description: list perception reports for a drug using cursor pagination.
    Required role: VIEWER.
    Example curl: curl -X GET 'http://localhost:8000/drugs/<drug_id>/reports?limit=20' -H 'Authorization: Bearer <access_token>'
    """
    page = await drug_service.list_reports(drug_id, current_user.organization_id, params.cursor, params.limit)
    typed_page = CursorPage[PerceptionReportRead](
        items=[PerceptionReportRead.model_validate(item) for item in page.items],
        next_cursor=page.next_cursor,
        prev_cursor=page.prev_cursor,
    )
    return ok(typed_page, request, next_cursor=page.next_cursor, prev_cursor=page.prev_cursor, count=len(page.items))


@router.post("/{drug_id}/analyze", response_model=APIEnvelope[AnalyzeTriggerResponse], status_code=202)
@limiter.limit(AUTH_LIMIT)
async def trigger_analysis(
    request: Request,
    drug_id: UUID,
    current_user: Annotated[User, Depends(require_role(UserRole.ANALYST))],
    drug_service: Annotated[DrugService, Depends(get_drug_service)],
) -> APIEnvelope[AnalyzeTriggerResponse]:
    """Description: trigger async analysis job for a drug.
    Required role: ANALYST or higher.
    Example curl: curl -X POST http://localhost:8000/drugs/<drug_id>/analyze -H 'Authorization: Bearer <access_token>'
    """
    result = await drug_service.trigger_analysis(drug_id, current_user)
    return ok(result, request)


@router.get("/{drug_id}/analyze/{job_id}", response_model=APIEnvelope[AnalyzeJobStatusResponse])
@limiter.limit(AUTH_LIMIT)
async def poll_analysis_job(
    request: Request,
    drug_id: UUID,
    job_id: UUID,
    current_user: Annotated[User, Depends(require_role(UserRole.VIEWER))],
    drug_service: Annotated[DrugService, Depends(get_drug_service)],
) -> APIEnvelope[AnalyzeJobStatusResponse]:
    """Description: poll asynchronous analysis job status and result.
    Required role: VIEWER.
    Example curl: curl -X GET http://localhost:8000/drugs/<drug_id>/analyze/<job_id> -H 'Authorization: Bearer <access_token>'
    """
    status = await drug_service.get_analysis_job_status(drug_id, job_id, current_user.organization_id)
    return ok(status, request)
