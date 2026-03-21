"""Authentication schemas for user sessions and API key management."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    """Request payload for creating organization and owner account."""

    organization_name: str = Field(min_length=2, max_length=255)
    organization_slug: str = Field(min_length=2, max_length=255)
    full_name: str = Field(min_length=2, max_length=255)
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)


class LoginRequest(BaseModel):
    """Credentials payload for login endpoint."""

    email: EmailStr
    password: str


class TokenPair(BaseModel):
    """Access and refresh tokens returned on login and register."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in_seconds: int


class RefreshTokenRequest(BaseModel):
    """Refresh token exchange payload."""

    refresh_token: str


class LogoutRequest(BaseModel):
    """Logout payload for refresh token invalidation."""

    refresh_token: str


class TokenPayload(BaseModel):
    """Decoded JWT payload schema."""

    sub: UUID
    org: UUID
    role: str
    typ: str
    exp: int


class APIKeyCreateRequest(BaseModel):
    """Request payload for generating organization API key."""

    name: str = Field(min_length=2, max_length=255)


class APIKeyCreateResponse(BaseModel):
    """Response containing clear-text key once at creation time."""

    id: UUID
    name: str
    key_prefix: str
    api_key: str
    created_at: datetime


class APIKeyRead(BaseModel):
    """Response payload for API key metadata."""

    id: UUID
    name: str
    key_prefix: str
    created_at: datetime
    revoked: bool
