"""add analysis run lifecycle constraint

Revision ID: 202610060001
Revises: 202609190001
Create Date: 2026-10-06 00:01:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "202610060001"
down_revision: str | None = "202609190001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_analysis_runs_lifecycle",
        "analysis_runs",
        "(status = 'queued' AND started_at IS NULL AND finished_at IS NULL "
        "AND error_code IS NULL) OR "
        "(status = 'running' AND started_at IS NOT NULL AND finished_at IS NULL "
        "AND error_code IS NULL) OR "
        "(status = 'succeeded' AND started_at IS NOT NULL AND finished_at IS NOT NULL "
        "AND error_code IS NULL) OR "
        "(status = 'failed' AND started_at IS NOT NULL AND finished_at IS NOT NULL "
        "AND error_code IS NOT NULL) OR "
        "(status = 'cancelled' AND finished_at IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_analysis_runs_lifecycle",
        "analysis_runs",
        type_="check",
    )
