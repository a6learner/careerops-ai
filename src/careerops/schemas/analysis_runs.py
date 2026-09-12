from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from careerops.domain.analysis_runs import AnalysisRunStatus
from careerops.domain.evidence_matching import EvidenceVerdict


class AnalysisRunSubmitRequest(BaseModel):
    parse_run_id: UUID


class EvidenceMatchResponse(BaseModel):
    id: UUID
    requirement_id: UUID
    experience_id: UUID | None
    experience_version: int | None
    verdict: EvidenceVerdict
    quote: str | None
    quote_valid: bool
    confidence: float | None


class AnalysisRunResponse(BaseModel):
    id: UUID
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
    matches: list[EvidenceMatchResponse]
