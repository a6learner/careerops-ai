"""finalize analysis run uniqueness constraints

Revision ID: 202609120001
Revises: 202609110001
Create Date: 2026-09-12 00:01:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202609120001"
down_revision: str | None = "202609110001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("uq_analysis_runs_active_input", table_name="analysis_runs")
    op.drop_index("idx_evidence_matches_run_requirement", table_name="evidence_matches")
    op.create_index(
        "uq_evidence_matches_run_requirement",
        "evidence_matches",
        ["analysis_run_id", "requirement_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_evidence_matches_run_requirement", table_name="evidence_matches")
    op.create_index(
        "idx_evidence_matches_run_requirement",
        "evidence_matches",
        ["analysis_run_id", "requirement_id"],
    )
    op.drop_index(
        "uq_analysis_runs_active_input",
        table_name="analysis_runs",
        if_exists=True,
    )
    op.create_index(
        "uq_analysis_runs_active_input",
        "analysis_runs",
        ["job_id", "input_fingerprint"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued', 'running')"),
    )
