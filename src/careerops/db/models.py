from datetime import date, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, CITEXT, JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ExperienceKind(StrEnum):
    PROJECT = "project"
    WORK = "work"
    RESEARCH = "research"
    COURSE = "course"
    OTHER = "other"


class JobStatus(StrEnum):
    SAVED = "saved"
    PREPARING = "preparing"
    APPLIED = "applied"
    INTERVIEW = "interview"
    OFFER = "offer"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class ParseRunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RequirementCategory(StrEnum):
    MUST_HAVE = "must_have"
    NICE_TO_HAVE = "nice_to_have"
    RESPONSIBILITY = "responsibility"
    EDUCATION = "education"


class AnalysisRunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class EvidenceVerdict(StrEnum):
    MATCHED = "matched"
    PARTIAL = "partial"
    MISSING = "missing"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class ActionItemStatus(StrEnum):
    TODO = "todo"
    DOING = "doing"
    DONE = "done"


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (
        UniqueConstraint("id", "user_id", name="uq_projects_id_owner"),
        CheckConstraint("char_length(btrim(name)) BETWEEN 1 AND 160", name="ck_projects_name"),
        CheckConstraint("char_length(btrim(goal)) BETWEEN 1 AND 2000", name="ck_projects_goal"),
        CheckConstraint("char_length(idempotency_key) BETWEEN 1 AND 255", name="ck_projects_key"),
        CheckConstraint("request_fingerprint ~ '^[0-9a-f]{64}$'", name="ck_projects_hash"),
        Index("uq_projects_user_key", "user_id", "idempotency_key", unique=True),
        Index("idx_projects_owner_created", "user_id", "created_at", "id"),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ProjectCheckpoint(Base):
    __tablename__ = "project_checkpoints"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "user_id"],
            ["projects.id", "projects.user_id"],
            name="fk_checkpoints_project_owner",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "status IN ('draft', 'confirmed', 'withdrawn')", name="ck_checkpoints_status"
        ),
        CheckConstraint("version >= 1", name="ck_checkpoints_version"),
        CheckConstraint(
            "char_length(idempotency_key) BETWEEN 1 AND 255", name="ck_checkpoints_key"
        ),
        CheckConstraint("content_sha256 ~ '^[0-9a-f]{64}$'", name="ck_checkpoints_hash"),
        CheckConstraint("project_checkpoint_sources_valid(payload)", name="ck_checkpoints_sources"),
        CheckConstraint(
            "(status = 'draft' AND reviewed_at IS NULL AND contribution_note = '') OR "
            "(status = 'confirmed' AND reviewed_at IS NOT NULL "
            "AND char_length(btrim(contribution_note)) BETWEEN 1 AND 2000) OR "
            "(status = 'withdrawn' AND reviewed_at IS NOT NULL "
            "AND char_length(contribution_note) <= 2000)",
            name="ck_checkpoints_review",
        ),
        Index("uq_checkpoints_user_key", "user_id", "idempotency_key", unique=True),
        Index("idx_checkpoints_project_created", "user_id", "project_id", "created_at", "id"),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), nullable=False)
    project_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="draft")
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    content_sha256: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    contribution_note: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class EmbeddingRunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SUPERSEDED = "superseded"


class AssistedRunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class DraftStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(CITEXT(), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class Experience(Base):
    __tablename__ = "experiences"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('project', 'work', 'research', 'course', 'other')",
            name="ck_experiences_kind",
        ),
        CheckConstraint("version >= 1", name="ck_experiences_version_positive"),
        CheckConstraint("char_length(content_hash) = 64", name="ck_experiences_content_hash"),
        CheckConstraint(
            "(embedding IS NULL AND embedding_content_hash IS NULL "
            "AND embedding_model IS NULL AND embedding_input_version IS NULL "
            "AND embedded_at IS NULL) OR "
            "(embedding IS NOT NULL AND embedding_content_hash = content_hash "
            "AND embedding_model IS NOT NULL AND embedding_input_version IS NOT NULL "
            "AND embedded_at IS NOT NULL)",
            name="ck_experiences_embedding_provenance",
        ),
        Index(
            "idx_experiences_user_active_updated",
            "user_id",
            text("updated_at DESC"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    skills: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        server_default="{}",
    )
    outcome: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="1",
    )
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)
    embedding_content_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding_input_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class ExperienceEmbeddingRun(Base):
    __tablename__ = "experience_embedding_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed', 'superseded')",
            name="ck_experience_embedding_runs_status",
        ),
        CheckConstraint(
            "experience_version >= 1",
            name="ck_experience_embedding_runs_experience_version_positive",
        ),
        CheckConstraint(
            "attempt >= 1",
            name="ck_experience_embedding_runs_attempt_positive",
        ),
        CheckConstraint(
            "char_length(content_hash) = 64",
            name="ck_experience_embedding_runs_content_hash",
        ),
        CheckConstraint(
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
        Index(
            "uq_experience_embedding_runs_target",
            "experience_id",
            "experience_version",
            "content_hash",
            "model_name",
            "input_version",
            unique=True,
        ),
        Index(
            "uq_experience_embedding_runs_active",
            "experience_id",
            unique=True,
            postgresql_where=text("status IN ('queued', 'running')"),
        ),
        Index(
            "idx_experience_embedding_runs_status_created",
            "status",
            "created_at",
            "id",
        ),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    experience_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("experiences.id", ondelete="CASCADE"),
        nullable=False,
    )
    experience_version: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    model_name: Mapped[str] = mapped_column(Text, nullable=False)
    input_version: Mapped[str] = mapped_column(Text, nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    error_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('saved', 'preparing', 'applied', 'interview', "
            "'offer', 'rejected', 'withdrawn')",
            name="ck_jobs_status",
        ),
        CheckConstraint("version >= 1", name="ck_jobs_version_positive"),
        CheckConstraint("char_length(description_hash) = 64", name="ck_jobs_description_hash"),
        Index(
            "idx_jobs_user_status_updated",
            "user_id",
            "status",
            text("updated_at DESC"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    company: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    raw_description: Mapped[str] = mapped_column(Text, nullable=False)
    description_hash: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(Text, nullable=True)
    deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=JobStatus.SAVED.value)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class ParseRun(Base):
    __tablename__ = "parse_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')",
            name="ck_parse_runs_status",
        ),
        CheckConstraint("char_length(input_fingerprint) = 64", name="ck_parse_runs_fingerprint"),
        CheckConstraint("attempt >= 1", name="ck_parse_runs_attempt_positive"),
        CheckConstraint("latency_ms IS NULL OR latency_ms >= 0", name="ck_parse_runs_latency"),
        CheckConstraint(
            "input_tokens IS NULL OR input_tokens >= 0",
            name="ck_parse_runs_input_tokens",
        ),
        CheckConstraint(
            "output_tokens IS NULL OR output_tokens >= 0",
            name="ck_parse_runs_output_tokens",
        ),
        CheckConstraint(
            "(status = 'queued' AND started_at IS NULL AND finished_at IS NULL "
            "AND error_code IS NULL) OR "
            "(status = 'running' AND started_at IS NOT NULL AND finished_at IS NULL "
            "AND error_code IS NULL) OR "
            "(status = 'succeeded' AND started_at IS NOT NULL AND finished_at IS NOT NULL "
            "AND error_code IS NULL) OR "
            "(status = 'failed' AND started_at IS NOT NULL AND finished_at IS NOT NULL "
            "AND error_code IS NOT NULL) OR "
            "(status = 'cancelled' AND finished_at IS NOT NULL)",
            name="ck_parse_runs_lifecycle",
        ),
        Index(
            "uq_parse_runs_user_job_idempotency",
            "user_id",
            "job_id",
            "idempotency_key",
            unique=True,
        ),
        Index("idx_parse_runs_user_job_created", "user_id", "job_id", text("created_at DESC")),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    job_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    input_fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    input_text: Mapped[str] = mapped_column(Text, nullable=False)
    model_name: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_version: Mapped[str] = mapped_column(Text, nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    error_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class JobRequirement(Base):
    __tablename__ = "job_requirements"
    __table_args__ = (
        CheckConstraint(
            "category IN ('must_have', 'nice_to_have', 'responsibility', 'education')",
            name="ck_job_requirements_category",
        ),
        CheckConstraint(
            "(source_span_start IS NULL AND source_span_end IS NULL) OR "
            "(source_span_start >= 0 AND source_span_end > source_span_start)",
            name="ck_job_requirements_source_span",
        ),
        Index("idx_job_requirements_job_run", "job_id", "parse_run_id"),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    parse_run_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("parse_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    category: Mapped[str] = mapped_column(Text, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    skill_normalized: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_span_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_span_end: Mapped[int | None] = mapped_column(Integer, nullable=True)


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')",
            name="ck_analysis_runs_status",
        ),
        CheckConstraint("char_length(input_fingerprint) = 64", name="ck_analysis_runs_fingerprint"),
        CheckConstraint("attempt >= 1", name="ck_analysis_runs_attempt_positive"),
        CheckConstraint(
            "validation_failure_count >= 0",
            name="ck_analysis_runs_validation_failure_count",
        ),
        CheckConstraint("latency_ms IS NULL OR latency_ms >= 0", name="ck_analysis_runs_latency"),
        CheckConstraint(
            "input_tokens IS NULL OR input_tokens >= 0",
            name="ck_analysis_runs_input_tokens",
        ),
        CheckConstraint(
            "output_tokens IS NULL OR output_tokens >= 0",
            name="ck_analysis_runs_output_tokens",
        ),
        CheckConstraint(
            "(status = 'queued' AND started_at IS NULL AND finished_at IS NULL "
            "AND error_code IS NULL) OR "
            "(status = 'running' AND started_at IS NOT NULL AND finished_at IS NULL "
            "AND error_code IS NULL) OR "
            "(status = 'succeeded' AND started_at IS NOT NULL AND finished_at IS NOT NULL "
            "AND error_code IS NULL) OR "
            "(status = 'failed' AND started_at IS NOT NULL AND finished_at IS NOT NULL "
            "AND error_code IS NOT NULL) OR "
            "(status = 'cancelled' AND finished_at IS NOT NULL)",
            name="ck_analysis_runs_lifecycle",
        ),
        Index(
            "uq_analysis_runs_user_job_idempotency",
            "user_id",
            "job_id",
            "idempotency_key",
            unique=True,
        ),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    job_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    parse_run_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("parse_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    input_fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    model_name: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_version: Mapped[str] = mapped_column(Text, nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    validation_failure_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
    )
    error_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class EvidenceMatch(Base):
    __tablename__ = "evidence_matches"
    __table_args__ = (
        CheckConstraint(
            "verdict IN ('matched', 'partial', 'missing', 'insufficient_evidence')",
            name="ck_evidence_matches_verdict",
        ),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_evidence_matches_confidence",
        ),
        CheckConstraint(
            "((verdict IN ('matched', 'partial')) AND experience_id IS NOT NULL "
            "AND experience_version IS NOT NULL AND experience_version >= 1 "
            "AND quote IS NOT NULL AND char_length(btrim(quote)) > 0 AND quote_valid) OR "
            "((verdict IN ('missing', 'insufficient_evidence')) AND experience_id IS NULL "
            "AND experience_version IS NULL AND quote IS NULL AND NOT quote_valid)",
            name="ck_evidence_matches_grounded_verdict",
        ),
        Index(
            "uq_evidence_matches_run_requirement",
            "analysis_run_id",
            "requirement_id",
            unique=True,
        ),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    analysis_run_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("analysis_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    requirement_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("job_requirements.id", ondelete="RESTRICT"),
        nullable=False,
    )
    experience_id: Mapped[UUID | None] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("experiences.id", ondelete="RESTRICT"),
        nullable=True,
    )
    experience_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    verdict: Mapped[str] = mapped_column(Text, nullable=False)
    quote: Mapped[str | None] = mapped_column(Text, nullable=True)
    quote_valid: Mapped[bool] = mapped_column(Boolean, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Numeric(3, 2), nullable=True)


class ActionItem(Base):
    __tablename__ = "action_items"
    __table_args__ = (
        CheckConstraint(
            "status IN ('todo', 'doing', 'done')",
            name="ck_action_items_status",
        ),
        CheckConstraint(
            "char_length(btrim(title)) BETWEEN 1 AND 200",
            name="ck_action_items_title",
        ),
        CheckConstraint("version >= 1", name="ck_action_items_version_positive"),
        CheckConstraint(
            "char_length(request_fingerprint) = 64",
            name="ck_action_items_request_fingerprint",
        ),
        CheckConstraint(
            "char_length(idempotency_key) BETWEEN 1 AND 255",
            name="ck_action_items_idempotency_key",
        ),
        Index(
            "uq_action_items_user_idempotency",
            "user_id",
            "idempotency_key",
            unique=True,
        ),
        Index(
            "idx_action_items_user_updated",
            "user_id",
            text("updated_at DESC"),
            text("id DESC"),
        ),
        Index(
            "idx_action_items_user_status_updated",
            "user_id",
            "status",
            text("updated_at DESC"),
            text("id DESC"),
        ),
        Index(
            "idx_action_items_user_job_updated",
            "user_id",
            "job_id",
            text("updated_at DESC"),
            text("id DESC"),
        ),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    job_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_evidence_match_id: Mapped[UUID | None] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("evidence_matches.id", ondelete="RESTRICT"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=ActionItemStatus.TODO.value,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class CvImport(Base):
    __tablename__ = "cv_imports"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed')",
            name="ck_cv_imports_status",
        ),
        CheckConstraint("size_bytes BETWEEN 1 AND 5242880", name="ck_cv_imports_size"),
        CheckConstraint("char_length(content_sha256) = 64", name="ck_cv_imports_sha256"),
        CheckConstraint("attempt >= 1", name="ck_cv_imports_attempt"),
        CheckConstraint(
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
        Index("uq_cv_imports_user_idempotency", "user_id", "idempotency_key", unique=True),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    document_type: Mapped[str] = mapped_column(Text, nullable=False)
    media_type: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    content_sha256: Mapped[str] = mapped_column(Text, nullable=False)
    source_bytes: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    normalized_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    extractor_name: Mapped[str] = mapped_column(Text, nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    error_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ExperienceDraft(Base):
    __tablename__ = "experience_drafts"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'confirmed', 'rejected')",
            name="ck_experience_drafts_status",
        ),
        CheckConstraint(
            "kind IN ('project', 'work', 'research', 'course', 'other')",
            name="ck_experience_drafts_kind",
        ),
        CheckConstraint("version >= 1", name="ck_experience_drafts_version"),
        CheckConstraint(
            "jsonb_typeof(source_refs) = 'array' AND jsonb_array_length(source_refs) > 0",
            name="ck_experience_drafts_source_refs",
        ),
        CheckConstraint(
            "(status = 'confirmed' AND confirmed_experience_id IS NOT NULL) OR "
            "(status <> 'confirmed' AND confirmed_experience_id IS NULL)",
            name="ck_experience_drafts_confirmation",
        ),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    cv_import_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True), ForeignKey("cv_imports.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    skills: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")
    outcome: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_refs: Mapped[list[dict[str, object]]] = mapped_column(JSONB, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    confirmed_experience_id: Mapped[UUID | None] = mapped_column(
        PostgresUUID(as_uuid=True), ForeignKey("experiences.id", ondelete="RESTRICT"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class JobDiscoveryRun(Base):
    __tablename__ = "job_discovery_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed')",
            name="ck_job_discovery_runs_status",
        ),
        CheckConstraint("attempt >= 1", name="ck_job_discovery_runs_attempt"),
        CheckConstraint(
            "char_length(query_fingerprint) = 64",
            name="ck_job_discovery_runs_fingerprint",
        ),
        CheckConstraint(
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
        Index("uq_job_discovery_runs_user_idempotency", "user_id", "idempotency_key", unique=True),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[str | None] = mapped_column(Text, nullable=True)
    remote: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    published_within_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    query_fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    provider_name: Mapped[str] = mapped_column(Text, nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    error_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class JobDiscoveryResult(Base):
    __tablename__ = "job_discovery_results"
    __table_args__ = (
        Index(
            "uq_job_discovery_results_provider_result",
            "run_id",
            "provider_result_id",
            unique=True,
        ),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    run_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("job_discovery_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider_result_id: Mapped[str] = mapped_column(Text, nullable=False)
    company: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    raw_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class JobDraft(Base):
    __tablename__ = "job_drafts"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'confirmed', 'rejected')", name="ck_job_drafts_status"
        ),
        CheckConstraint("version >= 1", name="ck_job_drafts_version"),
        CheckConstraint(
            "(status = 'confirmed' AND confirmed_job_id IS NOT NULL) OR "
            "(status <> 'confirmed' AND confirmed_job_id IS NULL)",
            name="ck_job_drafts_confirmation",
        ),
        Index("uq_job_drafts_result", "result_id", unique=True),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    result_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("job_discovery_results.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    company: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    raw_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    confirmed_job_id: Mapped[UUID | None] = mapped_column(
        PostgresUUID(as_uuid=True), ForeignKey("jobs.id", ondelete="RESTRICT"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
