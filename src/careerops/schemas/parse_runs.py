from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from careerops.domain.parse_runs import ParseRunStatus, RequirementCategory


class JobRequirementResponse(BaseModel):
    id: UUID
    category: RequirementCategory
    text: str
    skill_normalized: str | None
    source_span_start: int | None
    source_span_end: int | None


class ParseRunResponse(BaseModel):
    id: UUID
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
    requirements: list[JobRequirementResponse]
