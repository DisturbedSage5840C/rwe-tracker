"""Repository layer isolating persistence from API routers and services."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.models.analysis_job import AnalysisJob
from apps.api.models.api_key import APIKey
from apps.api.models.base import UserRole
from apps.api.models.drug import Drug
from apps.api.models.organization import Organization
from apps.api.models.patient_review import PatientReview
from apps.api.models.perception_report import PerceptionReport
from apps.api.models.refresh_token import RefreshToken
from apps.api.models.social_mention import SocialMention
from apps.api.models.user import User
from apps.api.services.pagination import paginate_by_created_desc


class OrganizationRepository:
    """Persistence methods for organizations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, name: str, slug: str) -> Organization:
        """Create and stage organization row."""
        organization = Organization(name=name, slug=slug)
        self.session.add(organization)
        await self.session.flush()
        return organization

    async def get_by_slug(self, slug: str) -> Organization | None:
        """Fetch organization by unique slug."""
        statement = select(Organization).where(Organization.slug == slug, Organization.is_deleted.is_(False))
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> Organization | None:
        """Fetch organization by unique display name."""
        statement = select(Organization).where(Organization.name == name, Organization.is_deleted.is_(False))
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_id(self, organization_id: uuid.UUID) -> Organization | None:
        """Fetch organization by ID."""
        statement = select(Organization).where(Organization.id == organization_id, Organization.is_deleted.is_(False))
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()


class UserRepository:
    """Persistence methods for users."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        organization_id: uuid.UUID,
        email: str,
        full_name: str,
        hashed_password: str,
        role: UserRole,
    ) -> User:
        """Create and stage user row."""
        user = User(
            organization_id=organization_id,
            email=email,
            full_name=full_name,
            hashed_password=hashed_password,
            role=role,
            is_active=True,
        )
        self.session.add(user)
        await self.session.flush()
        return user

    async def get_by_email(self, email: str) -> User | None:
        """Find active user by email."""
        statement = select(User).where(User.email == email, User.is_deleted.is_(False))
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        """Find active user by identifier."""
        statement = select(User).where(User.id == user_id, User.is_deleted.is_(False))
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()


class RefreshTokenRepository:
    """Persistence methods for refresh token lifecycle."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, user_id: uuid.UUID, token_hash: str, expires_at: datetime) -> RefreshToken:
        """Create refresh token row."""
        token = RefreshToken(user_id=user_id, token_hash=token_hash, expires_at=expires_at)
        self.session.add(token)
        await self.session.flush()
        return token

    async def get_valid_by_hash(self, token_hash: str) -> RefreshToken | None:
        """Find an unrevoked, unexpired refresh token by hash."""
        now = datetime.now(UTC)
        statement = select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked_at.is_(None),
            RefreshToken.expires_at > now,
            RefreshToken.is_deleted.is_(False),
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def revoke(self, token: RefreshToken) -> None:
        """Revoke a refresh token row."""
        token.revoked_at = datetime.now(UTC)
        token.is_deleted = True
        token.deleted_at = datetime.now(UTC)
        await self.session.flush()


class APIKeyRepository:
    """Persistence methods for API keys."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        organization_id: uuid.UUID,
        created_by_user_id: uuid.UUID,
        name: str,
        key_prefix: str,
        key_hash: str,
    ) -> APIKey:
        """Create and stage API key row."""
        key = APIKey(
            organization_id=organization_id,
            created_by_user_id=created_by_user_id,
            name=name,
            key_prefix=key_prefix,
            key_hash=key_hash,
        )
        self.session.add(key)
        await self.session.flush()
        return key

    async def get_by_hash(self, key_hash: str) -> APIKey | None:
        """Look up active API key by hashed value."""
        statement = select(APIKey).where(APIKey.key_hash == key_hash, APIKey.is_deleted.is_(False))
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_id(self, key_id: uuid.UUID) -> APIKey | None:
        """Get API key by identifier."""
        statement = select(APIKey).where(APIKey.id == key_id, APIKey.is_deleted.is_(False))
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def revoke(self, key: APIKey) -> None:
        """Soft-delete API key row."""
        key.is_deleted = True
        key.deleted_at = datetime.now(UTC)
        await self.session.flush()


class DrugRepository:
    """Persistence methods for drugs."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        organization_id: uuid.UUID,
        name: str,
        normalized_name: str,
        indication: str | None,
        manufacturer: str | None,
    ) -> Drug:
        """Create and stage drug row."""
        drug = Drug(
            organization_id=organization_id,
            name=name,
            normalized_name=normalized_name,
            indication=indication,
            manufacturer=manufacturer,
        )
        self.session.add(drug)
        await self.session.flush()
        return drug

    async def list_for_org_paginated(self, organization_id: uuid.UUID, cursor: str | None, limit: int):
        """Return cursor-page of active drugs for an organization."""
        return await paginate_by_created_desc(
            session=self.session,
            model=Drug,
            base_filters=[Drug.organization_id == organization_id, Drug.is_deleted.is_(False)],
            cursor=cursor,
            limit=limit,
        )

    async def get_by_id_for_org(self, drug_id: uuid.UUID, organization_id: uuid.UUID) -> Drug | None:
        """Return a single drug row if it belongs to tenant."""
        statement = select(Drug).where(
            Drug.id == drug_id,
            Drug.organization_id == organization_id,
            Drug.is_deleted.is_(False),
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def soft_delete(self, drug: Drug) -> None:
        """Soft-delete drug row."""
        drug.is_deleted = True
        drug.deleted_at = datetime.now(UTC)
        await self.session.flush()


class PerceptionReportRepository:
    """Persistence methods for perception reports."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_latest_for_drug(self, drug_id: uuid.UUID) -> PerceptionReport | None:
        """Fetch most recent non-deleted report for drug."""
        statement = (
            select(PerceptionReport)
            .where(PerceptionReport.drug_id == drug_id, PerceptionReport.is_deleted.is_(False))
            .order_by(PerceptionReport.created_at.desc(), PerceptionReport.id.desc())
            .limit(1)
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def list_for_drug_paginated(self, drug_id: uuid.UUID, cursor: str | None, limit: int):
        """Return cursor-page of reports for specific drug."""
        return await paginate_by_created_desc(
            session=self.session,
            model=PerceptionReport,
            base_filters=[PerceptionReport.drug_id == drug_id, PerceptionReport.is_deleted.is_(False)],
            cursor=cursor,
            limit=limit,
        )

    async def list_latest_for_drugs(self, drug_ids: list[uuid.UUID]) -> list[tuple[uuid.UUID, float | None, float | None]]:
        """Return latest gap/perception scores per drug for comparison responses."""
        rows: list[tuple[uuid.UUID, float | None, float | None]] = []
        for drug_id in drug_ids:
            latest = await self.get_latest_for_drug(drug_id)
            rows.append((drug_id, latest.gap_score if latest else None, latest.perception_score if latest else None))
        return rows

    async def list_trends(self, drug_id: uuid.UUID, days: int) -> list[PerceptionReport]:
        """Return recent reports for trend plotting."""
        cutoff = datetime.now(UTC).replace(microsecond=0) - timedelta(days=days)
        statement = (
            select(PerceptionReport)
            .where(
                PerceptionReport.drug_id == drug_id,
                PerceptionReport.is_deleted.is_(False),
                PerceptionReport.created_at >= cutoff,
            )
            .order_by(PerceptionReport.created_at.asc())
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())


class PatientReviewRepository:
    """Persistence methods for patient review aggregations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_dimension_averages(self, drug_id: uuid.UUID) -> dict[str, float | None]:
        """Aggregate average sentiment dimensions for a drug."""
        statement = select(
            func.avg(PatientReview.efficacy_sentiment),
            func.avg(PatientReview.safety_sentiment),
            func.avg(PatientReview.tolerability_sentiment),
            func.avg(PatientReview.convenience_sentiment),
            func.avg(PatientReview.qol_sentiment),
        ).where(PatientReview.drug_id == drug_id, PatientReview.is_deleted.is_(False))
        result = await self.session.execute(statement)
        row = result.one()
        return {
            "efficacy": row[0],
            "safety": row[1],
            "tolerability": row[2],
            "convenience": row[3],
            "quality_of_life": row[4],
        }


class SocialMentionRepository:
    """Persistence methods for social mention aggregations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def count_for_drug(self, drug_id: uuid.UUID) -> int:
        """Count social mentions for a specific drug."""
        statement = select(func.count(SocialMention.id)).where(
            SocialMention.drug_id == drug_id,
            SocialMention.is_deleted.is_(False),
        )
        result = await self.session.execute(statement)
        return int(result.scalar_one())


class AnalysisJobRepository:
    """Persistence methods for background analysis jobs."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, drug_id: uuid.UUID, organization_id: uuid.UUID, celery_task_id: str) -> AnalysisJob:
        """Create and stage analysis job row."""
        job = AnalysisJob(drug_id=drug_id, organization_id=organization_id, celery_task_id=celery_task_id)
        self.session.add(job)
        await self.session.flush()
        return job

    async def get_for_org(self, job_id: uuid.UUID, organization_id: uuid.UUID, drug_id: uuid.UUID) -> AnalysisJob | None:
        """Fetch job if it belongs to tenant and drug."""
        statement = select(AnalysisJob).where(
            AnalysisJob.id == job_id,
            AnalysisJob.organization_id == organization_id,
            AnalysisJob.drug_id == drug_id,
            AnalysisJob.is_deleted.is_(False),
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_latest_for_drug(self, organization_id: uuid.UUID, drug_id: uuid.UUID) -> AnalysisJob | None:
        """Fetch newest analysis job row for a tenant/drug pair."""
        statement = (
            select(AnalysisJob)
            .where(
                AnalysisJob.organization_id == organization_id,
                AnalysisJob.drug_id == drug_id,
                AnalysisJob.is_deleted.is_(False),
            )
            .order_by(AnalysisJob.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def update_status(self, job: AnalysisJob, status: str, result_payload: dict | None = None) -> None:
        """Persist updated job status and optional result payload."""
        job.status = status
        if result_payload is not None:
            job.result_payload = result_payload
        await self.session.flush()
