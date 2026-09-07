"""scope parse run idempotency to a job

Revision ID: 202609060001
Revises: 202609050001
Create Date: 2026-09-06 00:01:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "202609060001"
down_revision: str | None = "202609050001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("uq_parse_runs_user_idempotency", table_name="parse_runs")
    op.create_index(
        "uq_parse_runs_user_job_idempotency",
        "parse_runs",
        ["user_id", "job_id", "idempotency_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_parse_runs_user_job_idempotency", table_name="parse_runs")
    op.create_index(
        "uq_parse_runs_user_idempotency",
        "parse_runs",
        ["user_id", "idempotency_key"],
        unique=True,
    )
