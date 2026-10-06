from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from careerops.domain.embeddings import (
    FAKE_EMBEDDING_SPACE,
    EmbeddingSpace,
    analysis_pipeline_version,
)
from careerops.domain.evidence_matching import (
    MATCHER_PROMPT_VERSION,
    MATCHER_SCHEMA_VERSION,
    SUPPORTED_MATCHER_PROMPT_VERSIONS,
    EvidenceVerdict,
    ProposedEvidenceMatch,
)
from careerops.domain.experiences import ExperienceRecord
from careerops.domain.parse_runs import JobRequirementRecord

FAKE_ANALYSIS_MODEL_NAME = "local-fake-evidence-matcher"


def matcher_pipeline_version(space: EmbeddingSpace, matcher_model_name: str) -> str:
    return ":".join(
        (
            analysis_pipeline_version(space),
            MATCHER_SCHEMA_VERSION,
            MATCHER_PROMPT_VERSION,
            matcher_model_name,
        )
    )


def fake_matcher_pipeline_version(space: EmbeddingSpace) -> str:
    return matcher_pipeline_version(space, FAKE_ANALYSIS_MODEL_NAME)


ANALYSIS_PROMPT_VERSION = fake_matcher_pipeline_version(FAKE_EMBEDDING_SPACE)


def matcher_prompt_version_from_pipeline(pipeline_version: str) -> str:
    matches = [
        version
        for version in SUPPORTED_MATCHER_PROMPT_VERSIONS
        if version in pipeline_version.split(":")
    ]
    if len(matches) != 1:
        raise ValueError("Analysis pipeline has no unique matcher prompt version.")
    return matches[0]


def matcher_model_name_from_pipeline(pipeline_version: str) -> str:
    model_name = pipeline_version.rpartition(":")[2].strip()
    if not model_name:
        raise ValueError("Analysis pipeline has no matcher model name.")
    return model_name


class AnalysisRunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AnalysisDispatchSource(StrEnum):
    SUBMISSION = "submission"
    IDEMPOTENT_REPLAY = "idempotent_replay"
    RECOVERY = "recovery"
    LEGACY = "legacy"


class AnalysisRunErrorCode(StrEnum):
    ANALYSIS_INPUT_CHANGED = "ANALYSIS_INPUT_CHANGED"
    MATCHER_FAILED = "MATCHER_FAILED"
    MATCHER_OUTPUT_INVALID = "MATCHER_OUTPUT_INVALID"
    MATCHER_PROVIDER_DISABLED = "MATCHER_PROVIDER_DISABLED"
    MATCHER_PROVIDER_MISCONFIGURED = "MATCHER_PROVIDER_MISCONFIGURED"
    MATCHER_PROVIDER_TIMEOUT = "MATCHER_PROVIDER_TIMEOUT"
    MATCHER_PROVIDER_RATE_LIMITED = "MATCHER_PROVIDER_RATE_LIMITED"
    MATCHER_PROVIDER_UNAVAILABLE = "MATCHER_PROVIDER_UNAVAILABLE"
    MATCHER_PROVIDER_FAILED = "MATCHER_PROVIDER_FAILED"
    MATCHER_OUTPUT_INVALID_JSON = "MATCHER_OUTPUT_INVALID_JSON"
    MATCHER_OUTPUT_INVALID_SCHEMA = "MATCHER_OUTPUT_INVALID_SCHEMA"
    MATCHER_OUTPUT_INVALID_CONTRACT = "MATCHER_OUTPUT_INVALID_CONTRACT"


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
class AnalysisRateLimitReservation:
    token: str


@dataclass(frozen=True)
class AnalysisRunWorkItem:
    id: UUID
    attempt: int
    user_id: UUID
    job_id: UUID
    parse_run_id: UUID
    input_fingerprint: str
    model_name: str
    prompt_version: str
    created_at: datetime


@dataclass(frozen=True)
class AnalysisRunRecoveryItem:
    id: UUID
    attempt: int


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
