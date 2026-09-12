"""create analysis and evidence integrity foundation

Revision ID: 202609110001
Revises: 202609070001
Create Date: 2026-09-11 00:01:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "202609110001"
down_revision: str | None = "202609070001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "analysis_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parse_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("input_fingerprint", sa.Text(), nullable=False),
        sa.Column("model_name", sa.Text(), nullable=False),
        sa.Column("prompt_version", sa.Text(), nullable=False),
        sa.Column("attempt", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column(
            "validation_failure_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
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
            name="ck_analysis_runs_status",
        ),
        sa.CheckConstraint(
            "char_length(input_fingerprint) = 64",
            name="ck_analysis_runs_fingerprint",
        ),
        sa.CheckConstraint("attempt >= 1", name="ck_analysis_runs_attempt_positive"),
        sa.CheckConstraint(
            "validation_failure_count >= 0",
            name="ck_analysis_runs_validation_failure_count",
        ),
        sa.CheckConstraint(
            "latency_ms IS NULL OR latency_ms >= 0",
            name="ck_analysis_runs_latency",
        ),
        sa.CheckConstraint(
            "input_tokens IS NULL OR input_tokens >= 0",
            name="ck_analysis_runs_input_tokens",
        ),
        sa.CheckConstraint(
            "output_tokens IS NULL OR output_tokens >= 0",
            name="ck_analysis_runs_output_tokens",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_analysis_runs_user_id_users", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], name="fk_analysis_runs_job_id_jobs", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["parse_run_id"],
            ["parse_runs.id"],
            name="fk_analysis_runs_parse_run_id_parse_runs",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_analysis_runs"),
    )
    op.create_index(
        "uq_analysis_runs_active_input",
        "analysis_runs",
        ["job_id", "input_fingerprint"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued', 'running')"),
    )
    op.create_index(
        "uq_analysis_runs_user_job_idempotency",
        "analysis_runs",
        ["user_id", "job_id", "idempotency_key"],
        unique=True,
    )

    op.create_table(
        "evidence_matches",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("analysis_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requirement_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("experience_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("experience_version", sa.Integer(), nullable=True),
        sa.Column("verdict", sa.Text(), nullable=False),
        sa.Column("quote", sa.Text(), nullable=True),
        sa.Column("quote_valid", sa.Boolean(), nullable=False),
        sa.Column("confidence", sa.Numeric(3, 2), nullable=True),
        sa.CheckConstraint(
            "verdict IN ('matched', 'partial', 'missing', 'insufficient_evidence')",
            name="ck_evidence_matches_verdict",
        ),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_evidence_matches_confidence",
        ),
        sa.CheckConstraint(
            "((verdict IN ('matched', 'partial')) AND experience_id IS NOT NULL "
            "AND experience_version IS NOT NULL AND experience_version >= 1 "
            "AND quote IS NOT NULL AND char_length(btrim(quote)) > 0 AND quote_valid) OR "
            "((verdict IN ('missing', 'insufficient_evidence')) AND experience_id IS NULL "
            "AND experience_version IS NULL AND quote IS NULL AND NOT quote_valid)",
            name="ck_evidence_matches_grounded_verdict",
        ),
        sa.ForeignKeyConstraint(
            ["analysis_run_id"],
            ["analysis_runs.id"],
            name="fk_evidence_matches_analysis_run_id_analysis_runs",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["requirement_id"],
            ["job_requirements.id"],
            name="fk_evidence_matches_requirement_id_job_requirements",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["experience_id"],
            ["experiences.id"],
            name="fk_evidence_matches_experience_id_experiences",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_evidence_matches"),
    )
    op.create_index(
        "idx_evidence_matches_run_requirement",
        "evidence_matches",
        ["analysis_run_id", "requirement_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_evidence_matches_run_requirement", table_name="evidence_matches")
    op.drop_table("evidence_matches")
    op.drop_index("uq_analysis_runs_user_job_idempotency", table_name="analysis_runs")
    op.drop_index("uq_analysis_runs_active_input", table_name="analysis_runs")
    op.drop_table("analysis_runs")
