from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from careerops.domain.evidence_matching import EvidenceVerdict, ProposedEvidenceMatch
from careerops.domain.experiences import ExperienceRecord
from careerops.domain.parse_runs import JobRequirementRecord

FAKE_ANALYSIS_MODEL_NAME = "local-fake-evidence-matcher"
ANALYSIS_PROMPT_VERSION = "match-v1"


class AnalysisRunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AnalysisRunErrorCode(StrEnum):
    ANALYSIS_INPUT_CHANGED = "ANALYSIS_INPUT_CHANGED"
    MATCHER_FAILED = "MATCHER_FAILED"
    MATCHER_OUTPUT_INVALID = "MATCHER_OUTPUT_INVALID"


@dataclass(frozen=True)
class EvidenceMatchRecord:
    id: UUID
    requirement_id: UUID
    experience_id: UUID | None
    experience_version: int | None
    verdict: EvidenceVerdict
    quote: str | None
    quote_valid: bool
    confidence: float | None


@dataclass(frozen=True)
class AnalysisRunRecord:
    id: UUID
    user_id: UUID
    job_id: UUID
    parse_run_id: UUID
    status: AnalysisRunStatus
    idempotency_key: str
    input_fingerprint: str
    model_name: str
    prompt_version: str
    attempt: int
    validation_failure_count: int
    error_code: str | None
    latency_ms: int | None
    input_tokens: int | None
    output_tokens: int | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    matches: tuple[EvidenceMatchRecord, ...]


@dataclass(frozen=True)
class AnalysisRunCreationResult:
    run: AnalysisRunRecord
    created: bool


@dataclass(frozen=True)
class AnalysisRunWorkItem:
    id: UUID
    user_id: UUID
    job_id: UUID
    parse_run_id: UUID
    input_fingerprint: str


@dataclass(frozen=True)
class AnalysisInput:
    parse_input_fingerprint: str
    requirements: tuple[JobRequirementRecord, ...]
    experiences: tuple[ExperienceRecord, ...]


@dataclass(frozen=True)
class EvidenceMatcherOutput:
    model_name: str
    matches: tuple[ProposedEvidenceMatch, ...]
    input_tokens: int | None = None
    output_tokens: int | None = None
