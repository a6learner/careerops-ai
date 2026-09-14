"""create action items

Revision ID: 202609120002
Revises: 202609120001
Create Date: 2026-09-12 02:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "202609120002"
down_revision: str | None = "202609120001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "action_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "source_evidence_match_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'todo'"), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("request_fingerprint", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('todo', 'doing', 'done')",
            name="ck_action_items_status",
        ),
        sa.CheckConstraint(
            "char_length(btrim(title)) BETWEEN 1 AND 200",
            name="ck_action_items_title",
        ),
        sa.CheckConstraint("version >= 1", name="ck_action_items_version_positive"),
        sa.CheckConstraint(
            "char_length(request_fingerprint) = 64",
            name="ck_action_items_request_fingerprint",
        ),
        sa.CheckConstraint(
            "char_length(idempotency_key) BETWEEN 1 AND 255",
            name="ck_action_items_idempotency_key",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_action_items_user_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["jobs.id"],
            name="fk_action_items_job_id_jobs",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_evidence_match_id"],
            ["evidence_matches.id"],
            name="fk_action_items_source_evidence_match_id_evidence_matches",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_action_items"),
    )
    op.create_index(
        "uq_action_items_user_idempotency",
        "action_items",
        ["user_id", "idempotency_key"],
        unique=True,
    )
    op.create_index(
        "idx_action_items_user_updated",
        "action_items",
        ["user_id", sa.text("updated_at DESC"), sa.text("id DESC")],
    )
    op.create_index(
        "idx_action_items_user_status_updated",
        "action_items",
        ["user_id", "status", sa.text("updated_at DESC"), sa.text("id DESC")],
    )
    op.create_index(
        "idx_action_items_user_job_updated",
        "action_items",
        ["user_id", "job_id", sa.text("updated_at DESC"), sa.text("id DESC")],
    )


def downgrade() -> None:
    op.drop_index("idx_action_items_user_job_updated", table_name="action_items")
    op.drop_index("idx_action_items_user_status_updated", table_name="action_items")
    op.drop_index(
        "idx_action_items_user_updated",
        table_name="action_items",
        if_exists=True,
    )
    op.drop_index("uq_action_items_user_idempotency", table_name="action_items")
    op.drop_table("action_items")
