"""Add isolated project evidence records without changing existing resources."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "202610270001"
down_revision: str | None = "202610110001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE FUNCTION project_checkpoint_sources_valid(document jsonb) RETURNS boolean
        LANGUAGE plpgsql IMMUTABLE AS $$
        DECLARE source jsonb;
        BEGIN
            IF jsonb_typeof(document) IS DISTINCT FROM 'object'
               OR octet_length(document::text) > 262144
               OR jsonb_typeof(document->'sources') IS DISTINCT FROM 'array' THEN
                RETURN false;
            END IF;
            IF jsonb_array_length(document->'sources') NOT BETWEEN 1 AND 8 THEN
                RETURN false;
            END IF;
            FOR source IN SELECT value FROM jsonb_array_elements(document->'sources') LOOP
                IF jsonb_typeof(source) IS DISTINCT FROM 'object'
                   OR jsonb_typeof(source->'content') IS DISTINCT FROM 'string'
                   OR jsonb_typeof(source->'quote') IS DISTINCT FROM 'string'
                   OR jsonb_typeof(source->'locator') IS DISTINCT FROM 'string'
                   OR jsonb_typeof(source->'kind') IS DISTINCT FROM 'string' THEN
                    RETURN false;
                END IF;
                IF char_length(btrim(source->>'content')) NOT BETWEEN 1 AND 8000
                   OR char_length(btrim(source->>'quote')) NOT BETWEEN 1 AND 2000
                   OR char_length(btrim(source->>'locator')) NOT BETWEEN 1 AND 300
                   OR source->>'kind' NOT IN ('repository_excerpt', 'test_output', 'user_note')
                   OR strpos(source->>'content', source->>'quote') = 0 THEN
                    RETURN false;
                END IF;
            END LOOP;
            RETURN true;
        END $$
    """)
    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("goal", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("request_fingerprint", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("id", "user_id", name="uq_projects_id_owner"),
        sa.CheckConstraint("char_length(btrim(name)) BETWEEN 1 AND 160", name="ck_projects_name"),
        sa.CheckConstraint("char_length(btrim(goal)) BETWEEN 1 AND 2000", name="ck_projects_goal"),
        sa.CheckConstraint(
            "char_length(idempotency_key) BETWEEN 1 AND 255", name="ck_projects_key"
        ),
        sa.CheckConstraint("request_fingerprint ~ '^[0-9a-f]{64}$'", name="ck_projects_hash"),
    )
    op.create_index("uq_projects_user_key", "projects", ["user_id", "idempotency_key"], unique=True)
    op.create_index("idx_projects_owner_created", "projects", ["user_id", "created_at", "id"])
    op.create_table(
        "project_checkpoints",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.Text(), server_default="draft", nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("content_sha256", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("contribution_note", sa.Text(), server_default="", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["project_id", "user_id"],
            ["projects.id", "projects.user_id"],
            name="fk_checkpoints_project_owner",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'confirmed', 'withdrawn')", name="ck_checkpoints_status"
        ),
        sa.CheckConstraint("version >= 1", name="ck_checkpoints_version"),
        sa.CheckConstraint(
            "char_length(idempotency_key) BETWEEN 1 AND 255", name="ck_checkpoints_key"
        ),
        sa.CheckConstraint("content_sha256 ~ '^[0-9a-f]{64}$'", name="ck_checkpoints_hash"),
        sa.CheckConstraint(
            "project_checkpoint_sources_valid(payload)", name="ck_checkpoints_sources"
        ),
        sa.CheckConstraint(
            "(status = 'draft' AND reviewed_at IS NULL AND contribution_note = '') OR "
            "(status = 'confirmed' AND reviewed_at IS NOT NULL "
            "AND char_length(btrim(contribution_note)) BETWEEN 1 AND 2000) OR "
            "(status = 'withdrawn' AND reviewed_at IS NOT NULL "
            "AND char_length(contribution_note) <= 2000)",
            name="ck_checkpoints_review",
        ),
    )
    op.create_index(
        "uq_checkpoints_user_key",
        "project_checkpoints",
        ["user_id", "idempotency_key"],
        unique=True,
    )
    op.create_index(
        "idx_checkpoints_project_created",
        "project_checkpoints",
        ["user_id", "project_id", "created_at", "id"],
    )
    op.execute("""
        CREATE FUNCTION protect_project_checkpoint() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                IF NEW.status <> 'draft' OR NEW.version <> 1 THEN
                    RAISE EXCEPTION 'checkpoint must start as a draft' USING ERRCODE = '23514';
                END IF;
            ELSE
                IF (NEW.id, NEW.user_id, NEW.project_id, NEW.payload, NEW.content_sha256,
                    NEW.idempotency_key, NEW.created_at) IS DISTINCT FROM
                   (OLD.id, OLD.user_id, OLD.project_id, OLD.payload, OLD.content_sha256,
                    OLD.idempotency_key, OLD.created_at)
                   OR OLD.status = 'withdrawn'
                   OR (NEW.status = 'withdrawn'
                       AND NEW.contribution_note IS DISTINCT FROM OLD.contribution_note)
                   OR NEW.status = OLD.status OR NEW.status = 'draft'
                   OR NEW.version <> OLD.version + 1 THEN
                    RAISE EXCEPTION 'immutable checkpoint or invalid transition'
                        USING ERRCODE = '23514';
                END IF;
            END IF;
            RETURN NEW;
        END $$
    """)
    op.execute("""
        CREATE TRIGGER trg_protect_project_checkpoint BEFORE INSERT OR UPDATE
        ON project_checkpoints FOR EACH ROW EXECUTE FUNCTION protect_project_checkpoint()
    """)


def downgrade() -> None:
    op.drop_table("project_checkpoints")
    op.execute("DROP FUNCTION protect_project_checkpoint()")
    op.drop_table("projects")
    op.execute("DROP FUNCTION project_checkpoint_sources_valid(jsonb)")
