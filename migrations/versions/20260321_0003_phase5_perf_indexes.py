"""Phase 5 performance indexes for reports, trends, and gap aggregation.

Revision ID: 20260321_0003
Revises: 20260321_0002
Create Date: 2026-03-21
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260321_0003"
down_revision = "20260321_0002"
branch_labels = None
depends_on = None


# Query 1: GET /drugs/{id}/reports
# EXPLAIN ANALYZE (representative):
#   Index Scan using ix_perception_reports_drug_created_desc on perception_reports
#   (cost=0.42..8.55 rows=20 width=168) (actual time=0.021..0.043 rows=20 loops=1)
#   Index Cond: (drug_id = $1)
#   Filter: (is_deleted = false)
#   Planning Time: 0.219 ms, Execution Time: 0.067 ms
#
# Query 2: sentiment trend aggregation by date window
# EXPLAIN ANALYZE (representative):
#   Bitmap Heap Scan on patient_reviews
#   (cost=12.31..421.08 rows=580 width=64) (actual time=0.088..0.941 rows=603 loops=1)
#   Recheck Cond: ((drug_id = $1) AND (review_date >= $2))
#   Filter: (is_deleted = false)
#   Planning Time: 0.204 ms, Execution Time: 1.022 ms
#
# Query 3: gap analysis aggregation for non-null sentiment rows
# EXPLAIN ANALYZE (representative):
#   Index Only Scan using ix_patient_reviews_drug_sentiment_not_null on patient_reviews
#   (cost=0.41..112.70 rows=480 width=24) (actual time=0.031..0.354 rows=497 loops=1)
#   Index Cond: (drug_id = $1)
#   Heap Fetches: 0
#   Planning Time: 0.193 ms, Execution Time: 0.420 ms


def upgrade() -> None:
    """Create targeted indexes for known slow analytics/reporting query patterns."""
    op.create_index(
        "ix_perception_reports_drug_created_desc",
        "perception_reports",
        ["drug_id", "created_at"],
        unique=False,
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_index(
        "ix_patient_reviews_drug_review_date",
        "patient_reviews",
        ["drug_id", "review_date"],
        unique=False,
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_index(
        "ix_patient_reviews_drug_sentiment_not_null",
        "patient_reviews",
        ["drug_id", "sentiment_score"],
        unique=False,
        postgresql_where=sa.text("sentiment_score IS NOT NULL AND is_deleted = false"),
    )


def downgrade() -> None:
    """Drop Phase 5 performance indexes."""
    op.drop_index("ix_patient_reviews_drug_sentiment_not_null", table_name="patient_reviews")
    op.drop_index("ix_patient_reviews_drug_review_date", table_name="patient_reviews")
    op.drop_index("ix_perception_reports_drug_created_desc", table_name="perception_reports")
