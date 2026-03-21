"""Async SQLAlchemy engine and session factory for the API service."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from apps.api.config import get_settings

settings = get_settings()

# Async engine enables non-blocking DB I/O for API requests.
engine = create_async_engine(settings.database_url, pool_pre_ping=True, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a transactional async session per request lifecycle."""
    async with SessionLocal() as session:
        yield session
