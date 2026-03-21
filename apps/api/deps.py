"""Reusable dependency providers for FastAPI routes and services."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.config import get_settings
from apps.api.db import get_db_session
from apps.api.models.base import UserRole
from apps.api.models.organization import Organization
from apps.api.models.user import User
from apps.api.schemas.auth import TokenPayload
from apps.api.schemas.user import UserRead
from apps.api.services.auth_service import AuthService
from apps.api.services.analysis_service import AnalysisService
from apps.api.services.drug_service import DrugService
from apps.api.services.repositories import (
    APIKeyRepository,
    AnalysisJobRepository,
    DrugRepository,
    OrganizationRepository,
    PatientReviewRepository,
    PerceptionReportRepository,
    RefreshTokenRepository,
    UserRepository,
)
from apps.common.errors import AuthError, ForbiddenError

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

ROLE_RANK = {
    UserRole.VIEWER: 0,
    UserRole.ANALYST: 1,
    UserRole.ADMIN: 2,
    UserRole.OWNER: 3,
}


async def get_auth_service(session: Annotated[AsyncSession, Depends(get_db_session)]) -> AuthService:
    """Provide auth service with repository dependencies."""
    return AuthService(
        user_repository=UserRepository(session),
        organization_repository=OrganizationRepository(session),
        refresh_token_repository=RefreshTokenRepository(session),
        api_key_repository=APIKeyRepository(session),
        session=session,
    )


async def get_drug_service(session: Annotated[AsyncSession, Depends(get_db_session)]) -> DrugService:
    """Provide drug service with repository dependencies."""
    return DrugService(
        session=session,
        drug_repository=DrugRepository(session),
        report_repository=PerceptionReportRepository(session),
        analysis_job_repository=AnalysisJobRepository(session),
    )


async def get_analysis_service(session: Annotated[AsyncSession, Depends(get_db_session)]) -> AnalysisService:
    """Provide analysis service with repository dependencies."""
    return AnalysisService(
        drug_repository=DrugRepository(session),
        report_repository=PerceptionReportRepository(session),
        patient_review_repository=PatientReviewRepository(session),
    )


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> User:
    """Resolve authenticated user from bearer token."""
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
        )
        token_data = TokenPayload.model_validate(payload)
    except JWTError as exc:
        raise AuthError("Invalid authentication credentials") from exc

    if token_data.typ != "access":
        raise AuthError("Invalid token type")

    user = await auth_service.get_user_by_id(token_data.sub)
    if not user:
        raise AuthError("User no longer exists")
    return user


async def get_api_key_org(
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> Organization:
    """Resolve organization from X-API-Key header for machine clients."""
    if not x_api_key:
        raise AuthError("Missing X-API-Key header")
    return await auth_service.get_user_by_api_key(x_api_key)


def require_role(min_role: UserRole) -> Callable[[User], User]:
    """Return dependency function enforcing minimum role access."""

    async def _guard(user: Annotated[User, Depends(get_current_user)]) -> User:
        if ROLE_RANK[user.role] < ROLE_RANK[min_role]:
            raise ForbiddenError("Insufficient role permissions")
        return user

    return _guard


async def get_current_user_read(
    user: Annotated[User, Depends(get_current_user)],
) -> UserRead:
    """Project ORM user into response schema for endpoint payloads."""
    return UserRead.model_validate(user)


def parse_uuid(value: str) -> UUID:
    """Parse UUID and normalize error semantics for router helpers."""
    try:
        return UUID(value)
    except ValueError as exc:
        raise AuthError("Malformed UUID") from exc
