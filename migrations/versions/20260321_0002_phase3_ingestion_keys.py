"""Phase 3 schema additions for ingestion idempotency and trial metrics.

Revision ID: 20260321_0002
Revises: 20260321_0001
Create Date: 2026-03-21
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260321_0002"
down_revision = "20260321_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add ingestion-focused keys and metadata columns."""
    op.add_column("clinical_trials", sa.Column("nct_id", sa.String(length=64), nullable=True))
    op.add_column("clinical_trials", sa.Column("adverse_event_rate", sa.Float(), nullable=True))
    op.add_column("clinical_trials", sa.Column("discontinuation_proxy", sa.Float(), nullable=True))
    op.create_index(op.f("ix_clinical_trials_nct_id"), "clinical_trials", ["nct_id"], unique=True)

    # Existing rows are scaffold-only; set placeholder for safe not-null transition.
    op.execute("UPDATE clinical_trials SET nct_id = trial_identifier WHERE nct_id IS NULL")
    op.alter_column("clinical_trials", "nct_id", nullable=False)

    op.add_column("patient_reviews", sa.Column("external_id", sa.String(length=255), nullable=True))
    op.add_column("patient_reviews", sa.Column("review_date", sa.DateTime(timezone=True), nullable=True))
    op.add_column("patient_reviews", sa.Column("engagement_score", sa.Float(), nullable=True))
    op.add_column("patient_reviews", sa.Column("sentiment_score", sa.Float(), nullable=True))
    op.create_index(op.f("ix_patient_reviews_external_id"), "patient_reviews", ["external_id"], unique=True)

    op.add_column("social_mentions", sa.Column("external_id", sa.String(length=255), nullable=True))
    op.add_column("social_mentions", sa.Column("mention_date", sa.DateTime(timezone=True), nullable=True))
    op.add_column("social_mentions", sa.Column("engagement_score", sa.Float(), nullable=True))
    op.add_column("social_mentions", sa.Column("sentiment_score", sa.Float(), nullable=True))
    op.create_index(op.f("ix_social_mentions_external_id"), "social_mentions", ["external_id"], unique=True)


def downgrade() -> None:
    """Remove Phase 3 ingestion-focused schema additions."""
    op.drop_index(op.f("ix_social_mentions_external_id"), table_name="social_mentions")
    op.drop_column("social_mentions", "sentiment_score")
    op.drop_column("social_mentions", "engagement_score")
    op.drop_column("social_mentions", "mention_date")
    op.drop_column("social_mentions", "external_id")

    op.drop_index(op.f("ix_patient_reviews_external_id"), table_name="patient_reviews")
    op.drop_column("patient_reviews", "sentiment_score")
    op.drop_column("patient_reviews", "engagement_score")
    op.drop_column("patient_reviews", "review_date")
    op.drop_column("patient_reviews", "external_id")

    op.drop_index(op.f("ix_clinical_trials_nct_id"), table_name="clinical_trials")
    op.drop_column("clinical_trials", "discontinuation_proxy")
    op.drop_column("clinical_trials", "adverse_event_rate")
    op.drop_column("clinical_trials", "nct_id")
