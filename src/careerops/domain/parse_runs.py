from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

FAKE_PARSE_MODEL_NAME = "local-fake-parser"
PARSE_PROMPT_VERSION = "parse-v1"


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


@dataclass(frozen=True)
class ParsedRequirement:
    category: RequirementCategory
    text: str
    skill_normalized: str | None
    source_span_start: int
    source_span_end: int


@dataclass(frozen=True)
class JobRequirementRecord:
    id: UUID
    job_id: UUID
    parse_run_id: UUID
    category: RequirementCategory
    text: str
    skill_normalized: str | None
    source_span_start: int | None
    source_span_end: int | None


@dataclass(frozen=True)
class ParseRunRecord:
    id: UUID
    user_id: UUID
    job_id: UUID
    status: ParseRunStatus
    idempotency_key: str
    input_fingerprint: str
    model_name: str
    prompt_version: str
    attempt: int
    error_code: str | None
    latency_ms: int | None
    input_tokens: int | None
    output_tokens: int | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    requirements: tuple[JobRequirementRecord, ...]


@dataclass(frozen=True)
class ParseRunCreationResult:
    run: ParseRunRecord
    created: bool
