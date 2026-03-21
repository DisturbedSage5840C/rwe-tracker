"""Alembic migration environment configuration for async SQLAlchemy models."""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from apps.api.config import get_settings
from apps.api.models.analysis_job import AnalysisJob
from apps.api.models.api_key import APIKey
from apps.api.models.base import Base
from apps.api.models.clinical_trial import ClinicalTrial
from apps.api.models.drug import Drug
from apps.api.models.organization import Organization
from apps.api.models.patient_review import PatientReview
from apps.api.models.perception_report import PerceptionReport
from apps.api.models.refresh_token import RefreshToken
from apps.api.models.social_mention import SocialMention
from apps.api.models.user import User

config = context.config
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Importing model classes above ensures metadata is registered for autogeneration.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in offline mode with literal binds."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Configure Alembic context and execute migration scripts."""
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in online mode using async SQLAlchemy engine."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async def migrate() -> None:
        async with connectable.connect() as connection:
            await connection.run_sync(do_run_migrations)
        await connectable.dispose()

    import asyncio

    asyncio.run(migrate())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
