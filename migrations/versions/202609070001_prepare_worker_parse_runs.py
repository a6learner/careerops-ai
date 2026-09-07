"""prepare parse runs for worker execution

Revision ID: 202609070001
Revises: 202609060001
Create Date: 2026-09-07 00:01:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202609070001"
down_revision: str | None = "202609060001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("parse_runs", sa.Column("input_text", sa.Text(), nullable=True))
    op.execute(
        sa.text(
            "UPDATE parse_runs SET input_text = jobs.raw_description "
            "FROM jobs WHERE parse_runs.job_id = jobs.id"
        )
    )
    op.alter_column("parse_runs", "input_text", existing_type=sa.Text(), nullable=False)
    op.create_check_constraint(
        "ck_parse_runs_lifecycle",
        "parse_runs",
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
    op.drop_constraint("ck_parse_runs_lifecycle", "parse_runs", type_="check")
    op.drop_column("parse_runs", "input_text")
