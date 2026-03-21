"""Authentication routes for registration, session, and API key lifecycle."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request

from apps.api.deps import get_api_key_org, get_auth_service, get_current_user_read, require_role
from apps.api.models.organization import Organization
from apps.api.limiter import AUTH_LIMIT, UNAUTH_LIMIT, limiter
from apps.api.models.base import UserRole
from apps.api.models.user import User
from apps.api.response import ok
from apps.api.schemas.auth import (
    APIKeyCreateRequest,
    APIKeyCreateResponse,
    APIKeyRead,
    LoginRequest,
    LogoutRequest,
    RefreshTokenRequest,
    RegisterRequest,
    TokenPair,
)
from apps.api.schemas.envelope import APIEnvelope
from apps.api.services.auth_service import AuthService
from apps.api.schemas.user import UserRead

router = APIRouter()


@router.post("/register", response_model=APIEnvelope[TokenPair])
@limiter.limit(UNAUTH_LIMIT)
async def register(
    request: Request,
    payload: RegisterRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> APIEnvelope[TokenPair]:
    """Description: create organization and owner user.
    Required role: none.
    Example curl: curl -X POST http://localhost:8000/auth/register -H 'Content-Type: application/json' -d '{"organization_name":"Acme","organization_slug":"acme","full_name":"Owner","email":"owner@acme.com","password":"StrongPassword123!"}'
    """
    _, tokens = await auth_service.register(payload)
    return ok(tokens, request)


@router.post("/token", response_model=APIEnvelope[TokenPair])
@limiter.limit(UNAUTH_LIMIT)
async def login(
    request: Request,
    payload: LoginRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> APIEnvelope[TokenPair]:
    """Description: authenticate user and return access plus refresh token.
    Required role: none.
    Example curl: curl -X POST http://localhost:8000/auth/token -H 'Content-Type: application/json' -d '{"email":"owner@acme.com","password":"StrongPassword123!"}'
    """
    user = await auth_service.authenticate(email=payload.email, password=payload.password)
    token_pair = await auth_service.create_token_pair(user)
    return ok(token_pair, request)


@router.post("/refresh", response_model=APIEnvelope[TokenPair])
@limiter.limit(UNAUTH_LIMIT)
async def refresh_token(
    request: Request,
    payload: RefreshTokenRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> APIEnvelope[TokenPair]:
    """Description: exchange refresh token for a new token pair.
    Required role: none.
    Example curl: curl -X POST http://localhost:8000/auth/refresh -H 'Content-Type: application/json' -d '{"refresh_token":"token"}'
    """
    tokens = await auth_service.refresh_access_token(payload.refresh_token)
    return ok(tokens, request)


@router.post("/logout", response_model=APIEnvelope[dict])
@limiter.limit(UNAUTH_LIMIT)
async def logout(
    request: Request,
    payload: LogoutRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> APIEnvelope[dict]:
    """Description: invalidate a refresh token and terminate session.
    Required role: none.
    Example curl: curl -X POST http://localhost:8000/auth/logout -H 'Content-Type: application/json' -d '{"refresh_token":"token"}'
    """
    await auth_service.logout(payload.refresh_token)
    return ok({"message": "Logged out"}, request)


@router.get("/me", response_model=APIEnvelope[UserRead])
@limiter.limit(AUTH_LIMIT)
async def me(
    request: Request,
    current_user: Annotated[UserRead, Depends(get_current_user_read)],
) -> APIEnvelope[UserRead]:
    """Description: return current authenticated principal.
    Required role: VIEWER.
    Example curl: curl -X GET http://localhost:8000/auth/me -H 'Authorization: Bearer <access_token>'
    """
    return ok(current_user, request)


@router.post("/api-keys", response_model=APIEnvelope[APIKeyCreateResponse])
@limiter.limit(AUTH_LIMIT)
async def create_api_key(
    request: Request,
    payload: APIKeyCreateRequest,
    current_user: Annotated[User, Depends(require_role(UserRole.ADMIN))],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> APIEnvelope[APIKeyCreateResponse]:
    """Description: create organization API key for machine-to-machine access.
    Required role: ADMIN or OWNER.
    Example curl: curl -X POST http://localhost:8000/auth/api-keys -H 'Authorization: Bearer <access_token>' -H 'Content-Type: application/json' -d '{"name":"etl-bot"}'
    """
    key = await auth_service.create_api_key(payload.name, current_user)
    return ok(key, request)


@router.delete("/api-keys/{key_id}", response_model=APIEnvelope[APIKeyRead])
@limiter.limit(AUTH_LIMIT)
async def revoke_api_key(
    request: Request,
    key_id: UUID,
    current_user: Annotated[User, Depends(require_role(UserRole.ADMIN))],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> APIEnvelope[APIKeyRead]:
    """Description: revoke an existing organization API key.
    Required role: ADMIN or OWNER.
    Example curl: curl -X DELETE http://localhost:8000/auth/api-keys/<key_id> -H 'Authorization: Bearer <access_token>'
    """
    revoked = await auth_service.revoke_api_key(key_id, current_user.organization_id)
    payload = APIKeyRead.model_validate(revoked)
    return ok(payload, request)


@router.get("/api-keys/verify", response_model=APIEnvelope[dict[str, str]])
@limiter.limit(AUTH_LIMIT)
async def verify_api_key(
    request: Request,
    organization: Annotated[Organization, Depends(get_api_key_org)],
) -> APIEnvelope[dict[str, str]]:
    """Description: validate X-API-Key and return resolved organization metadata.
    Required role: API key header.
    Example curl: curl -X GET http://localhost:8000/auth/api-keys/verify -H 'X-API-Key: <api_key>'
    """
    return ok({"organization_id": str(organization.id), "slug": organization.slug}, request)
