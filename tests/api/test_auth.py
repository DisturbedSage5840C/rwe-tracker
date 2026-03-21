"""Authentication and token lifecycle API tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from sqlalchemy import select

from apps.api.config import get_settings
from apps.api.models.api_key import APIKey
from apps.api.models.organization import Organization
from apps.api.models.refresh_token import RefreshToken
from apps.api.models.user import User


@pytest.mark.asyncio
async def test_register_creates_org_and_owner_user(test_client, async_db_session) -> None:
    response = await test_client.post(
        "/auth/register",
        json={
            "organization_name": "Acme Pharma",
            "organization_slug": "acme-pharma",
            "full_name": "Owner One",
            "email": "owner@acme.com",
            "password": "StrongPassword123!",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["access_token"]
    assert body["data"]["refresh_token"]

    org = (await async_db_session.execute(select(Organization).where(Organization.slug == "acme-pharma"))).scalar_one()
    user = (await async_db_session.execute(select(User).where(User.email == "owner@acme.com"))).scalar_one()
    assert user.organization_id == org.id
    assert user.hashed_password != "StrongPassword123!"
    assert "StrongPassword123!" not in user.hashed_password


@pytest.mark.asyncio
async def test_login_returns_jwt_pair(test_client, test_user_factory) -> None:
    user = await test_user_factory(email="login@example.com", password="StrongPassword123!")

    response = await test_client.post("/auth/token", json={"email": user.email, "password": "StrongPassword123!"})
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["access_token"]
    assert body["data"]["refresh_token"]


@pytest.mark.asyncio
async def test_login_wrong_password(test_client, test_user_factory) -> None:
    user = await test_user_factory(email="wrong-pass@example.com", password="StrongPassword123!")

    response = await test_client.post("/auth/token", json={"email": user.email, "password": "WrongPassword123!"})
    assert response.status_code == 401
    message = response.json()["errors"][0]["message"]
    assert message == "Incorrect email or password"
    assert "user" not in message.lower() or "not found" not in message.lower()


@pytest.mark.asyncio
async def test_refresh_token_rotation(test_client, test_user_factory, async_db_session) -> None:
    user = await test_user_factory(email="refresh@example.com", password="StrongPassword123!")

    login_response = await test_client.post("/auth/token", json={"email": user.email, "password": "StrongPassword123!"})
    old_refresh = login_response.json()["data"]["refresh_token"]

    refresh_response = await test_client.post("/auth/refresh", json={"refresh_token": old_refresh})
    assert refresh_response.status_code == 200
    new_refresh = refresh_response.json()["data"]["refresh_token"]
    assert new_refresh != old_refresh

    reused = await test_client.post("/auth/refresh", json={"refresh_token": old_refresh})
    assert reused.status_code == 401

    tokens = (await async_db_session.execute(select(RefreshToken))).scalars().all()
    assert any(token.revoked_at is not None for token in tokens)


@pytest.mark.asyncio
async def test_expired_access_token(test_client, test_user_factory) -> None:
    user = await test_user_factory(email="expired@example.com")
    settings = get_settings()
    now = datetime.now(UTC)
    expired_payload = {
        "sub": str(user.id),
        "org": str(user.organization_id),
        "role": user.role.value,
        "typ": "access",
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": int(now.timestamp()),
        "exp": int((now - timedelta(minutes=1)).timestamp()),
    }

    from jose import jwt

    expired_token = jwt.encode(expired_payload, settings.secret_key, algorithm=settings.jwt_algorithm)
    response = await test_client.get("/drugs", headers={"Authorization": f"Bearer {expired_token}"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_api_key_auth(test_client, test_user_factory, auth_header) -> None:
    admin_user = await test_user_factory(email="admin@example.com")
    create_response = await test_client.post(
        "/auth/api-keys",
        headers=auth_header(admin_user),
        json={"name": "integration-bot"},
    )
    assert create_response.status_code == 200
    api_key = create_response.json()["data"]["api_key"]

    verify = await test_client.get("/auth/api-keys/verify", headers={"X-API-Key": api_key})
    assert verify.status_code == 200


@pytest.mark.asyncio
async def test_api_key_revoked(test_client, test_user_factory, auth_header, async_db_session) -> None:
    admin_user = await test_user_factory(email="admin-revoke@example.com")
    create_response = await test_client.post(
        "/auth/api-keys",
        headers=auth_header(admin_user),
        json={"name": "etl-key"},
    )
    data = create_response.json()["data"]

    revoke_response = await test_client.delete(f"/auth/api-keys/{data['id']}", headers=auth_header(admin_user))
    assert revoke_response.status_code == 200

    verify = await test_client.get("/auth/api-keys/verify", headers={"X-API-Key": data["api_key"]})
    assert verify.status_code == 401

    key = (await async_db_session.execute(select(APIKey).where(APIKey.id == UUID(data["id"])))).scalar_one()
    assert key.is_deleted is True


@pytest.mark.asyncio
async def test_rate_limit_triggers(test_client) -> None:
    from apps.api.limiter import limiter

    storage = getattr(limiter, "_storage", None)
    if storage is not None and hasattr(storage, "reset"):
        storage.reset()

    status_codes: list[int] = []
    for _ in range(11):
        response = await test_client.get("/health")
        status_codes.append(response.status_code)

    assert status_codes[-1] == 429
