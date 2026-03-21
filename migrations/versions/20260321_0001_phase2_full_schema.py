"""Phase 2 full schema for multi-tenant RWE Perception Tracker.

Revision ID: 20260321_0001
Revises: None
Create Date: 2026-03-21
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260321_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create complete Phase 2 schema with tenant isolation and soft deletes."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    user_role = sa.Enum("OWNER", "ADMIN", "ANALYST", "VIEWER", name="user_role")
    user_role.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "organizations",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_organizations_slug"), "organizations", ["slug"], unique=True)
    op.create_index(op.f("ix_organizations_name"), "organizations", ["name"], unique=True)

    op.create_table(
        "users",
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("role", user_role, nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_organization_id"), "users", ["organization_id"], unique=False)

    op.create_table(
        "drugs",
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("normalized_name", sa.String(length=255), nullable=False),
        sa.Column("indication", sa.Text(), nullable=True),
        sa.Column("manufacturer", sa.String(length=255), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_drugs_name"), "drugs", ["name"], unique=False)
    op.create_index(op.f("ix_drugs_normalized_name"), "drugs", ["normalized_name"], unique=False)
    op.create_index(op.f("ix_drugs_organization_id"), "drugs", ["organization_id"], unique=False)

    op.create_table(
        "clinical_trials",
        sa.Column("drug_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("trial_identifier", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("phase", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=128), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("source_url", sa.String(length=1024), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["drug_id"], ["drugs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_clinical_trials_drug_id"), "clinical_trials", ["drug_id"], unique=False)
    op.create_index(op.f("ix_clinical_trials_trial_identifier"), "clinical_trials", ["trial_identifier"], unique=False)

    op.create_table(
        "patient_reviews",
        sa.Column("drug_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source", sa.String(length=128), nullable=False),
        sa.Column("source_url", sa.String(length=1024), nullable=True),
        sa.Column("author_handle", sa.String(length=255), nullable=True),
        sa.Column("review_text", sa.Text(), nullable=False),
        sa.Column("crawled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("word_count", sa.Integer(), nullable=False),
        sa.Column("overall_sentiment", sa.Float(), nullable=True),
        sa.Column("efficacy_sentiment", sa.Float(), nullable=True),
        sa.Column("safety_sentiment", sa.Float(), nullable=True),
        sa.Column("tolerability_sentiment", sa.Float(), nullable=True),
        sa.Column("convenience_sentiment", sa.Float(), nullable=True),
        sa.Column("qol_sentiment", sa.Float(), nullable=True),
        sa.Column("embedding", Vector(dim=384), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["drug_id"], ["drugs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_patient_reviews_drug_id"), "patient_reviews", ["drug_id"], unique=False)

    op.create_table(
        "social_mentions",
        sa.Column("drug_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("platform", sa.String(length=64), nullable=False),
        sa.Column("post_id", sa.String(length=255), nullable=True),
        sa.Column("author_handle", sa.String(length=255), nullable=True),
        sa.Column("source_url", sa.String(length=1024), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("overall_sentiment", sa.Float(), nullable=True),
        sa.Column("embedding", Vector(dim=384), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["drug_id"], ["drugs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_social_mentions_drug_id"), "social_mentions", ["drug_id"], unique=False)

    op.create_table(
        "perception_reports",
        sa.Column("drug_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("perception_score", sa.Float(), nullable=False),
        sa.Column("trial_score", sa.Float(), nullable=False),
        sa.Column("gap_score", sa.Float(), nullable=False),
        sa.Column("confidence_interval_lower", sa.Float(), nullable=True),
        sa.Column("confidence_interval_upper", sa.Float(), nullable=True),
        sa.Column("sample_size_reviews", sa.Integer(), nullable=False),
        sa.Column("sample_size_social", sa.Integer(), nullable=False),
        sa.Column("methodology_version", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["drug_id"], ["drugs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_perception_reports_drug_id"), "perception_reports", ["drug_id"], unique=False)

    op.create_table(
        "refresh_tokens",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(op.f("ix_refresh_tokens_expires_at"), "refresh_tokens", ["expires_at"], unique=False)
    op.create_index(op.f("ix_refresh_tokens_user_id"), "refresh_tokens", ["user_id"], unique=False)

    op.create_table(
        "api_keys",
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("key_prefix", sa.String(length=12), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key_hash"),
    )
    op.create_index(op.f("ix_api_keys_key_prefix"), "api_keys", ["key_prefix"], unique=False)
    op.create_index(op.f("ix_api_keys_organization_id"), "api_keys", ["organization_id"], unique=False)

    op.create_table(
        "analysis_jobs",
        sa.Column("drug_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("celery_task_id", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("result_payload", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["drug_id"], ["drugs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("celery_task_id"),
    )
    op.create_index(op.f("ix_analysis_jobs_celery_task_id"), "analysis_jobs", ["celery_task_id"], unique=True)
    op.create_index(op.f("ix_analysis_jobs_drug_id"), "analysis_jobs", ["drug_id"], unique=False)
    op.create_index(op.f("ix_analysis_jobs_organization_id"), "analysis_jobs", ["organization_id"], unique=False)


def downgrade() -> None:
    """Drop Phase 2 schema objects in reverse dependency order."""
    op.drop_index(op.f("ix_analysis_jobs_organization_id"), table_name="analysis_jobs")
    op.drop_index(op.f("ix_analysis_jobs_drug_id"), table_name="analysis_jobs")
    op.drop_index(op.f("ix_analysis_jobs_celery_task_id"), table_name="analysis_jobs")
    op.drop_table("analysis_jobs")

    op.drop_index(op.f("ix_api_keys_organization_id"), table_name="api_keys")
    op.drop_index(op.f("ix_api_keys_key_prefix"), table_name="api_keys")
    op.drop_table("api_keys")

    op.drop_index(op.f("ix_refresh_tokens_user_id"), table_name="refresh_tokens")
    op.drop_index(op.f("ix_refresh_tokens_expires_at"), table_name="refresh_tokens")
    op.drop_table("refresh_tokens")

    op.drop_index(op.f("ix_perception_reports_drug_id"), table_name="perception_reports")
    op.drop_table("perception_reports")

    op.drop_index(op.f("ix_social_mentions_drug_id"), table_name="social_mentions")
    op.drop_table("social_mentions")

    op.drop_index(op.f("ix_patient_reviews_drug_id"), table_name="patient_reviews")
    op.drop_table("patient_reviews")

    op.drop_index(op.f("ix_clinical_trials_trial_identifier"), table_name="clinical_trials")
    op.drop_index(op.f("ix_clinical_trials_drug_id"), table_name="clinical_trials")
    op.drop_table("clinical_trials")

    op.drop_index(op.f("ix_drugs_organization_id"), table_name="drugs")
    op.drop_index(op.f("ix_drugs_normalized_name"), table_name="drugs")
    op.drop_index(op.f("ix_drugs_name"), table_name="drugs")
    op.drop_table("drugs")

    op.drop_index(op.f("ix_users_organization_id"), table_name="users")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")

    op.drop_index(op.f("ix_organizations_name"), table_name="organizations")
    op.drop_index(op.f("ix_organizations_slug"), table_name="organizations")
    op.drop_table("organizations")

    sa.Enum(name="user_role").drop(op.get_bind(), checkfirst=True)
