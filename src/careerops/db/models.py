from datetime import date, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, CITEXT
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import UserDefinedType


class Base(DeclarativeBase):
    pass


class PgVector(UserDefinedType[list[float]]):
    cache_ok = True

    def __init__(self, dimensions: int = 1536) -> None:
        self._dimensions = dimensions

    def get_col_spec(self, **kw: object) -> str:
        return f"vector({self._dimensions})"


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
    embedding: Mapped[list[float] | None] = mapped_column(PgVector(1536), nullable=True)
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
