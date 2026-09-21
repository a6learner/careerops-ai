"""add experience embedding lifecycle

Revision ID: 202609190001
Revises: 202609120002
Create Date: 2026-09-19 00:01:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "202609190001"
down_revision: str | None = "202609120002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("experiences", sa.Column("embedding_content_hash", sa.Text(), nullable=True))
    op.add_column("experiences", sa.Column("embedding_model", sa.Text(), nullable=True))
    op.add_column("experiences", sa.Column("embedding_input_version", sa.Text(), nullable=True))
    op.add_column(
        "experiences",
        sa.Column("embedded_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        "ck_experiences_embedding_provenance",
        "experiences",
        "(embedding IS NULL AND embedding_content_hash IS NULL "
        "AND embedding_model IS NULL AND embedding_input_version IS NULL "
        "AND embedded_at IS NULL) OR "
        "(embedding IS NOT NULL AND embedding_content_hash = content_hash "
        "AND embedding_model IS NOT NULL AND embedding_input_version IS NOT NULL "
        "AND embedded_at IS NOT NULL)",
    )

    op.create_table(
        "experience_embedding_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("experience_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("experience_version", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("model_name", sa.Text(), nullable=False),
        sa.Column("input_version", sa.Text(), nullable=False),
        sa.Column("attempt", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed', 'superseded')",
            name="ck_experience_embedding_runs_status",
        ),
        sa.CheckConstraint(
            "experience_version >= 1",
            name="ck_experience_embedding_runs_experience_version_positive",
        ),
        sa.CheckConstraint(
            "attempt >= 1",
            name="ck_experience_embedding_runs_attempt_positive",
        ),
        sa.CheckConstraint(
            "char_length(content_hash) = 64",
            name="ck_experience_embedding_runs_content_hash",
        ),
        sa.CheckConstraint(
            "(status = 'queued' AND started_at IS NULL AND finished_at IS NULL "
            "AND error_code IS NULL) OR "
            "(status = 'running' AND started_at IS NOT NULL AND finished_at IS NULL "
            "AND error_code IS NULL) OR "
            "(status = 'succeeded' AND started_at IS NOT NULL AND finished_at IS NOT NULL "
            "AND error_code IS NULL) OR "
            "(status = 'failed' AND started_at IS NOT NULL AND finished_at IS NOT NULL "
            "AND error_code IS NOT NULL) OR "
            "(status = 'superseded' AND finished_at IS NOT NULL AND error_code IS NULL)",
            name="ck_experience_embedding_runs_lifecycle",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_experience_embedding_runs_user_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["experience_id"],
            ["experiences.id"],
            name="fk_experience_embedding_runs_experience_id_experiences",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_experience_embedding_runs"),
    )
    op.create_index(
        "uq_experience_embedding_runs_target",
        "experience_embedding_runs",
        ["experience_id", "experience_version", "content_hash", "model_name", "input_version"],
        unique=True,
    )
    op.create_index(
        "uq_experience_embedding_runs_active",
        "experience_embedding_runs",
        ["experience_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued', 'running')"),
    )
    op.create_index(
        "idx_experience_embedding_runs_status_created",
        "experience_embedding_runs",
        ["status", "created_at", "id"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_experience_embedding_runs_status_created",
        table_name="experience_embedding_runs",
    )
    op.drop_index(
        "uq_experience_embedding_runs_active",
        table_name="experience_embedding_runs",
    )
    op.drop_index(
        "uq_experience_embedding_runs_target",
        table_name="experience_embedding_runs",
    )
    op.drop_table("experience_embedding_runs")
    op.drop_constraint(
        "ck_experiences_embedding_provenance",
        "experiences",
        type_="check",
    )
    op.drop_column("experiences", "embedded_at")
    op.drop_column("experiences", "embedding_input_version")
    op.drop_column("experiences", "embedding_model")
    op.drop_column("experiences", "embedding_content_hash")
