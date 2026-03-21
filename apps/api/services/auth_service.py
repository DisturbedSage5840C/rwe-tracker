"""Authentication service implementing user, token, and API key flows."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.config import get_settings
from apps.api.models.base import UserRole
from apps.api.models.user import User
from apps.api.schemas.auth import APIKeyCreateResponse, RegisterRequest, TokenPair
from apps.api.services.repositories import APIKeyRepository, OrganizationRepository, RefreshTokenRepository, UserRepository
from apps.api.services.security import (
    generate_api_key,
    generate_refresh_token,
    hash_api_key,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from apps.common.errors import AuthError, ValidationAppError


class AuthService:
    """Orchestrates password verification, session lifecycle, and API keys."""

    def __init__(
        self,
        user_repository: UserRepository,
        organization_repository: OrganizationRepository,
        refresh_token_repository: RefreshTokenRepository,
        api_key_repository: APIKeyRepository,
        session: AsyncSession,
    ) -> None:
        self.user_repository = user_repository
        self.organization_repository = organization_repository
        self.refresh_token_repository = refresh_token_repository
        self.api_key_repository = api_key_repository
        self.session = session
        self.settings = get_settings()

    async def register(self, payload: RegisterRequest) -> tuple[User, TokenPair]:
        """Create organization with owner user and issue initial token pair."""
        existing_org = await self.organization_repository.get_by_slug(payload.organization_slug)
        if existing_org:
            raise ValidationAppError("Organization slug already exists")

        existing_user = await self.user_repository.get_by_email(payload.email)
        if existing_user:
            raise ValidationAppError("Email already registered")

        organization = await self.organization_repository.create(
            name=payload.organization_name,
            slug=payload.organization_slug,
        )

        user = await self.user_repository.create(
            organization_id=organization.id,
            email=payload.email,
            full_name=payload.full_name,
            hashed_password=hash_password(payload.password),
            role=UserRole.OWNER,
        )

        tokens = await self._issue_token_pair(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user, tokens

    async def authenticate(self, email: str, password: str) -> User:
        """Validate user credentials and return active user."""
        user = await self.user_repository.get_by_email(email)
        if not user or not verify_password(password, user.hashed_password):
            raise AuthError("Incorrect email or password")
        if not user.is_active:
            raise AuthError("Inactive user")
        return user

    async def create_access_token(self, subject: uuid.UUID, organization_id: uuid.UUID, role: str) -> str:
        """Create signed JWT access token for user subject."""
        now = datetime.now(UTC)
        expire = now + timedelta(minutes=self.settings.access_token_expire_minutes)
        payload = {
            "sub": str(subject),
            "org": str(organization_id),
            "role": role,
            "typ": "access",
            "iss": self.settings.jwt_issuer,
            "aud": self.settings.jwt_audience,
            "iat": int(now.timestamp()),
            "exp": int(expire.timestamp()),
        }
        return jwt.encode(payload, self.settings.secret_key, algorithm=self.settings.jwt_algorithm)

    async def create_token_pair(self, user: User) -> TokenPair:
        """Issue token pair for validated user login."""
        tokens = await self._issue_token_pair(user)
        await self.session.commit()
        return tokens

    async def refresh_access_token(self, refresh_token: str) -> TokenPair:
        """Exchange valid refresh token for fresh access and refresh tokens."""
        token_hash = hash_refresh_token(refresh_token)
        stored = await self.refresh_token_repository.get_valid_by_hash(token_hash)
        if not stored:
            raise AuthError("Invalid refresh token")

        user = await self.user_repository.get_by_id(stored.user_id)
        if not user:
            raise AuthError("User no longer exists")

        await self.refresh_token_repository.revoke(stored)
        tokens = await self._issue_token_pair(user)
        await self.session.commit()
        return tokens

    async def logout(self, refresh_token: str) -> None:
        """Invalidate refresh token if it exists and is active."""
        token_hash = hash_refresh_token(refresh_token)
        stored = await self.refresh_token_repository.get_valid_by_hash(token_hash)
        if stored:
            await self.refresh_token_repository.revoke(stored)
            await self.session.commit()

    async def create_api_key(self, name: str, user: User) -> APIKeyCreateResponse:
        """Generate, hash, and store API key for organization automation."""
        api_key = generate_api_key()
        key_prefix = api_key[:12]
        row = await self.api_key_repository.create(
            organization_id=user.organization_id,
            created_by_user_id=user.id,
            name=name,
            key_prefix=key_prefix,
            key_hash=hash_api_key(api_key),
        )
        await self.session.commit()
        return APIKeyCreateResponse(
            id=row.id,
            name=row.name,
            key_prefix=row.key_prefix,
            api_key=api_key,
            created_at=row.created_at,
        )

    async def revoke_api_key(self, key_id: uuid.UUID, organization_id: uuid.UUID):
        """Soft-delete an API key owned by organization."""
        row = await self.api_key_repository.get_by_id(key_id)
        if not row or row.organization_id != organization_id:
            raise AuthError("API key not found")
        snapshot = {
            "id": row.id,
            "name": row.name,
            "key_prefix": row.key_prefix,
            "created_at": row.created_at,
            "revoked": True,
        }
        await self.api_key_repository.revoke(row)
        await self.session.commit()
        return snapshot

    async def get_user_by_id(self, user_id: uuid.UUID) -> User | None:
        """Lookup user by id for auth dependency resolution."""
        return await self.user_repository.get_by_id(user_id)

    async def get_user_by_api_key(self, api_key: str):
        """Resolve organization via API key hash."""
        key = await self.api_key_repository.get_by_hash(hash_api_key(api_key))
        if not key:
            raise AuthError("Invalid API key")
        org = await self.organization_repository.get_by_id(key.organization_id)
        if not org:
            raise AuthError("Organization not found")
        return org

    async def _issue_token_pair(self, user: User) -> TokenPair:
        """Generate and persist new access/refresh token pair for a user."""
        access_token = await self.create_access_token(
            subject=user.id,
            organization_id=user.organization_id,
            role=user.role.value,
        )

        raw_refresh = generate_refresh_token()
        refresh_exp = datetime.now(UTC) + timedelta(days=self.settings.refresh_token_expire_days)
        await self.refresh_token_repository.create(
            user_id=user.id,
            token_hash=hash_refresh_token(raw_refresh),
            expires_at=refresh_exp,
        )

        return TokenPair(
            access_token=access_token,
            refresh_token=raw_refresh,
            token_type="bearer",
            expires_in_seconds=self.settings.access_token_expire_minutes * 60,
        )
