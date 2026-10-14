"""add assisted import workflows

Revision ID: 202610110001
Revises: 202610060001
Create Date: 2026-10-11 00:01:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "202610110001"
down_revision: str | None = "202610060001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cv_imports",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("document_type", sa.Text(), nullable=False),
        sa.Column("media_type", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("content_sha256", sa.Text(), nullable=False),
        sa.Column("source_bytes", sa.LargeBinary(), nullable=False),
        sa.Column("normalized_text", sa.Text(), nullable=True),
        sa.Column("extractor_name", sa.Text(), nullable=False),
        sa.Column("attempt", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed')",
            name="ck_cv_imports_status",
        ),
        sa.CheckConstraint("size_bytes BETWEEN 1 AND 5242880", name="ck_cv_imports_size"),
        sa.CheckConstraint("char_length(content_sha256) = 64", name="ck_cv_imports_sha256"),
        sa.CheckConstraint("attempt >= 1", name="ck_cv_imports_attempt"),
        sa.CheckConstraint(
            "(status = 'queued' AND started_at IS NULL AND finished_at IS NULL "
            "AND error_code IS NULL) OR "
            "(status = 'running' AND started_at IS NOT NULL AND finished_at IS NULL "
            "AND error_code IS NULL) OR "
            "(status = 'succeeded' AND started_at IS NOT NULL AND finished_at IS NOT NULL "
            "AND error_code IS NULL AND normalized_text IS NOT NULL) OR "
            "(status = 'failed' AND started_at IS NOT NULL AND finished_at IS NOT NULL "
            "AND error_code IS NOT NULL)",
            name="ck_cv_imports_lifecycle",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_cv_imports_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_cv_imports"),
    )
    op.create_index(
        "uq_cv_imports_user_idempotency",
        "cv_imports",
        ["user_id", "idempotency_key"],
        unique=True,
    )

    op.create_table(
        "experience_drafts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cv_import_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("skills", postgresql.ARRAY(sa.Text()), server_default="{}", nullable=False),
        sa.Column("outcome", sa.Text(), nullable=True),
        sa.Column("source_refs", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("confirmed_experience_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'confirmed', 'rejected')",
            name="ck_experience_drafts_status",
        ),
        sa.CheckConstraint(
            "kind IN ('project', 'work', 'research', 'course', 'other')",
            name="ck_experience_drafts_kind",
        ),
        sa.CheckConstraint("version >= 1", name="ck_experience_drafts_version"),
        sa.CheckConstraint(
            "jsonb_typeof(source_refs) = 'array' AND jsonb_array_length(source_refs) > 0",
            name="ck_experience_drafts_source_refs",
        ),
        sa.CheckConstraint(
            "(status = 'confirmed' AND confirmed_experience_id IS NOT NULL) OR "
            "(status <> 'confirmed' AND confirmed_experience_id IS NULL)",
            name="ck_experience_drafts_confirmation",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_experience_drafts_user_id_users", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["cv_import_id"],
            ["cv_imports.id"],
            name="fk_experience_drafts_cv_import_id_cv_imports",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["confirmed_experience_id"],
            ["experiences.id"],
            name="fk_experience_drafts_confirmed_experience_id_experiences",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_experience_drafts"),
    )

    op.create_table(
        "job_discovery_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("location", sa.Text(), nullable=True),
        sa.Column("remote", sa.Boolean(), nullable=True),
        sa.Column("published_within_days", sa.Integer(), nullable=True),
        sa.Column("query_fingerprint", sa.Text(), nullable=False),
        sa.Column("provider_name", sa.Text(), nullable=False),
        sa.Column("attempt", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed')",
            name="ck_job_discovery_runs_status",
        ),
        sa.CheckConstraint("attempt >= 1", name="ck_job_discovery_runs_attempt"),
        sa.CheckConstraint(
            "char_length(query_fingerprint) = 64", name="ck_job_discovery_runs_fingerprint"
        ),
        sa.CheckConstraint(
            "(status = 'queued' AND started_at IS NULL AND finished_at IS NULL "
            "AND error_code IS NULL) OR "
            "(status = 'running' AND started_at IS NOT NULL AND finished_at IS NULL "
            "AND error_code IS NULL) OR "
            "(status = 'succeeded' AND started_at IS NOT NULL AND finished_at IS NOT NULL "
            "AND error_code IS NULL) OR "
            "(status = 'failed' AND started_at IS NOT NULL AND finished_at IS NOT NULL "
            "AND error_code IS NOT NULL)",
            name="ck_job_discovery_runs_lifecycle",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_job_discovery_runs_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_job_discovery_runs"),
    )
    op.create_index(
        "uq_job_discovery_runs_user_idempotency",
        "job_discovery_runs",
        ["user_id", "idempotency_key"],
        unique=True,
    )

    op.create_table(
        "job_discovery_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider_result_id", sa.Text(), nullable=False),
        sa.Column("company", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("raw_description", sa.Text(), nullable=True),
        sa.Column("location", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_job_discovery_results_user_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["job_discovery_runs.id"],
            name="fk_job_discovery_results_run_id_job_discovery_runs",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_job_discovery_results"),
    )
    op.create_index(
        "uq_job_discovery_results_provider_result",
        "job_discovery_results",
        ["run_id", "provider_result_id"],
        unique=True,
    )

    op.create_table(
        "job_drafts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("result_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("company", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("raw_description", sa.Text(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("location", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("confirmed_job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'confirmed', 'rejected')", name="ck_job_drafts_status"
        ),
        sa.CheckConstraint("version >= 1", name="ck_job_drafts_version"),
        sa.CheckConstraint(
            "(status = 'confirmed' AND confirmed_job_id IS NOT NULL) OR "
            "(status <> 'confirmed' AND confirmed_job_id IS NULL)",
            name="ck_job_drafts_confirmation",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_job_drafts_user_id_users", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["result_id"],
            ["job_discovery_results.id"],
            name="fk_job_drafts_result_id_job_discovery_results",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["confirmed_job_id"],
            ["jobs.id"],
            name="fk_job_drafts_confirmed_job_id_jobs",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_job_drafts"),
    )
    op.create_index("uq_job_drafts_result", "job_drafts", ["result_id"], unique=True)


def downgrade() -> None:
    op.drop_index("uq_job_drafts_result", table_name="job_drafts")
    op.drop_table("job_drafts")
    op.drop_index(
        "uq_job_discovery_results_provider_result", table_name="job_discovery_results"
    )
    op.drop_table("job_discovery_results")
    op.drop_index(
        "uq_job_discovery_runs_user_idempotency", table_name="job_discovery_runs"
    )
    op.drop_table("job_discovery_runs")
    op.drop_table("experience_drafts")
    op.drop_index("uq_cv_imports_user_idempotency", table_name="cv_imports")
    op.drop_table("cv_imports")
