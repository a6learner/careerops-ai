from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from careerops.domain.evidence_matching import EvidenceVerdict


class ActionItemStatus(StrEnum):
    TODO = "todo"
    DOING = "doing"
    DONE = "done"


@dataclass(frozen=True)
class ActionItemCreate:
    user_id: UUID
    job_id: UUID
    title: str
    source_evidence_match_id: UUID | None
    idempotency_key: str


@dataclass(frozen=True)
class ActionItemUpdate:
    title: str | None = None
    status: ActionItemStatus | None = None


@dataclass(frozen=True)
class ActionItemCursor:
    updated_at: datetime
    id: UUID


@dataclass(frozen=True)
class ActionItemRecord:
    id: UUID
    user_id: UUID
    job_id: UUID
    source_evidence_match_id: UUID | None
    title: str
    status: ActionItemStatus
    version: int
    idempotency_key: str
    request_fingerprint: str
    job_is_archived: bool
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class ActionItemSourceRecord:
    id: UUID
    verdict: EvidenceVerdict


@dataclass(frozen=True)
class ActionItemCreationResult:
    item: ActionItemRecord
    created: bool
