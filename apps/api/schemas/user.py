"""User and organization schemas for API responses."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr


class OrganizationRead(BaseModel):
    """Organization payload visible to authenticated users."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    created_at: datetime


class UserRead(BaseModel):
    """Public user fields returned to clients."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    email: EmailStr
    full_name: str
    role: str
    is_active: bool
    created_at: datetime
