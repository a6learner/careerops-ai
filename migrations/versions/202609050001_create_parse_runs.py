"""create parse runs and job requirements

Revision ID: 202609050001
Revises: 202609040001
Create Date: 2026-09-05 00:01:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "202609050001"
down_revision: str | None = "202609040001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "parse_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("input_fingerprint", sa.Text(), nullable=False),
        sa.Column("model_name", sa.Text(), nullable=False),
        sa.Column("prompt_version", sa.Text(), nullable=False),
        sa.Column("attempt", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')",
            name="ck_parse_runs_status",
        ),
        sa.CheckConstraint("char_length(input_fingerprint) = 64", name="ck_parse_runs_fingerprint"),
        sa.CheckConstraint("attempt >= 1", name="ck_parse_runs_attempt_positive"),
        sa.CheckConstraint("latency_ms IS NULL OR latency_ms >= 0", name="ck_parse_runs_latency"),
        sa.CheckConstraint(
            "input_tokens IS NULL OR input_tokens >= 0",
            name="ck_parse_runs_input_tokens",
        ),
        sa.CheckConstraint(
            "output_tokens IS NULL OR output_tokens >= 0",
            name="ck_parse_runs_output_tokens",
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["jobs.id"],
            name="fk_parse_runs_job_id_jobs",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_parse_runs_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_parse_runs"),
    )
    op.create_index(
        "uq_parse_runs_user_idempotency",
        "parse_runs",
        ["user_id", "idempotency_key"],
        unique=True,
    )
    op.create_index(
        "idx_parse_runs_user_job_created",
        "parse_runs",
        ["user_id", "job_id", sa.text("created_at DESC")],
    )

    op.create_table(
        "job_requirements",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parse_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("skill_normalized", sa.Text(), nullable=True),
        sa.Column("source_span_start", sa.Integer(), nullable=True),
        sa.Column("source_span_end", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "category IN ('must_have', 'nice_to_have', 'responsibility', 'education')",
            name="ck_job_requirements_category",
        ),
        sa.CheckConstraint(
            "(source_span_start IS NULL AND source_span_end IS NULL) OR "
            "(source_span_start >= 0 AND source_span_end > source_span_start)",
            name="ck_job_requirements_source_span",
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["jobs.id"],
            name="fk_job_requirements_job_id_jobs",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["parse_run_id"],
            ["parse_runs.id"],
            name="fk_job_requirements_parse_run_id_parse_runs",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_job_requirements"),
    )
    op.create_index(
        "idx_job_requirements_job_run",
        "job_requirements",
        ["job_id", "parse_run_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_job_requirements_job_run", table_name="job_requirements")
    op.drop_table("job_requirements")
    op.drop_index("idx_parse_runs_user_job_created", table_name="parse_runs")
    op.drop_index("uq_parse_runs_user_idempotency", table_name="parse_runs")
    op.drop_table("parse_runs")
