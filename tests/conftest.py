"""Shared pytest fixtures for API, worker, and integration tests."""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator, Awaitable, Callable
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Provide deterministic test defaults for settings that are required at import time.
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("SECRET_KEY", "test-secret-key-with-minimum-32-characters")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/postgres")
os.environ.setdefault("NLP_SERVICE_URL", "http://localhost:8001")
os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")
os.environ.setdefault("OPENFDA_BASE_URL", "https://api.fda.gov")
os.environ.setdefault("JWT_ISSUER", "rwe-tracker-api")
os.environ.setdefault("JWT_AUDIENCE", "rwe-tracker-clients")
os.environ.setdefault("CORS_ALLOWED_ORIGINS", "[\"http://localhost:3000\"]")

from apps.api.config import get_settings
from apps.api.db import get_db_session
from apps.api.main import app
from apps.api.models.base import Base, UserRole
from apps.api.models.drug import Drug
from apps.api.models.organization import Organization
from apps.api.models.user import User
from apps.api.services.security import hash_password


@pytest.fixture
def test_database_url() -> str:
    """Resolve async SQLAlchemy DSN for integration tests against real Postgres."""
    explicit_url = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not explicit_url:
        raise RuntimeError("TEST_DATABASE_URL or DATABASE_URL must be set for PostgreSQL-backed tests")
    if explicit_url.startswith("postgresql://"):
        return explicit_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return explicit_url


@pytest.fixture
async def test_engine(test_database_url: str):
    """Create async engine and bootstrap schema once per test session."""
    os.environ["DATABASE_URL"] = test_database_url
    get_settings.cache_clear()

    engine = create_async_engine(test_database_url, pool_pre_ping=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def async_db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Provide isolated transaction-bound DB session and roll back per test."""
    async with test_engine.connect() as conn:
        transaction = await conn.begin()
        session = AsyncSession(bind=conn, expire_on_commit=False)
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()


@pytest.fixture
async def test_client(async_db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Provide async HTTP client backed by FastAPI app with overridden DB dependency."""

    async def _override_db() -> AsyncGenerator[AsyncSession, None]:
        yield async_db_session

    app.dependency_overrides[get_db_session] = _override_db

    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield client

    app.dependency_overrides.clear()


@pytest.fixture
def access_token_factory() -> Callable[[User, int], str]:
    """Create signed access tokens for arbitrary users and expiry offsets."""

    def _factory(user: User, expires_minutes: int = 15) -> str:
        settings = get_settings()
        now = datetime.now(UTC)
        expire = now + timedelta(minutes=expires_minutes)
        payload = {
            "sub": str(user.id),
            "org": str(user.organization_id),
            "role": user.role.value,
            "typ": "access",
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
            "iat": int(now.timestamp()),
            "exp": int(expire.timestamp()),
        }
        return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)

    return _factory


@pytest.fixture
def auth_header(access_token_factory: Callable[[User, int], str]) -> Callable[[User], dict[str, str]]:
    """Build Authorization header for a provided user."""

    def _factory(user: User) -> dict[str, str]:
        return {"Authorization": f"Bearer {access_token_factory(user)}"}

    return _factory


@pytest.fixture
def test_org_factory(async_db_session: AsyncSession) -> Callable[..., Awaitable[Organization]]:
    """Create organizations for multi-tenant tests."""

    async def _factory(name: str | None = None, slug: str | None = None) -> Organization:
        org = Organization(name=name or f"Org-{uuid4()}", slug=slug or f"org-{uuid4()}")
        async_db_session.add(org)
        await async_db_session.flush()
        return org

    return _factory


@pytest.fixture
def test_user_factory(async_db_session: AsyncSession, test_org_factory) -> Callable[..., Awaitable[User]]:
    """Create users with configurable role and organization."""

    async def _factory(
        *,
        organization: Organization | None = None,
        role: UserRole = UserRole.OWNER,
        email: str | None = None,
        password: str = "StrongPassword123!",
    ) -> User:
        org = organization or await test_org_factory()
        user = User(
            organization_id=org.id,
            email=email or f"user-{uuid4()}@example.com",
            full_name="Test User",
            hashed_password=hash_password(password),
            role=role,
            is_active=True,
        )
        async_db_session.add(user)
        await async_db_session.flush()
        return user

    return _factory


@pytest.fixture
def test_drug_factory(async_db_session: AsyncSession, test_org_factory) -> Callable[..., Awaitable[Drug]]:
    """Create drug rows for tenant-scoped API tests."""

    async def _factory(*, organization: Organization | None = None, name: str | None = None) -> Drug:
        org = organization or await test_org_factory()
        drug_name = name or f"Drug-{uuid4()}"
        drug = Drug(
            organization_id=org.id,
            name=drug_name,
            normalized_name=drug_name.lower(),
            indication="Oncology",
            manufacturer="RWE Pharma",
        )
        async_db_session.add(drug)
        await async_db_session.flush()
        return drug

    return _factory
