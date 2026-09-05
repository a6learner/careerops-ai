from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from uuid import UUID


class JobStatus(StrEnum):
    SAVED = "saved"
    PREPARING = "preparing"
    APPLIED = "applied"
    INTERVIEW = "interview"
    OFFER = "offer"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


@dataclass(frozen=True)
class JobCreate:
    user_id: UUID
    company: str
    title: str
    raw_description: str
    source_url: str | None
    location: str | None
    deadline: date | None
    status: JobStatus = JobStatus.SAVED


@dataclass(frozen=True)
class JobUpdate:
    company: str | None = None
    title: str | None = None
    raw_description: str | None = None
    source_url: str | None = None
    clear_source_url: bool = False
    location: str | None = None
    clear_location: bool = False
    deadline: date | None = None
    clear_deadline: bool = False
    status: JobStatus | None = None


@dataclass(frozen=True)
class JobCursor:
    updated_at: datetime
    id: UUID


@dataclass(frozen=True)
class JobRecord:
    id: UUID
    user_id: UUID
    company: str
    title: str
    raw_description: str
    description_hash: str
    source_url: str | None
    location: str | None
    deadline: date | None
    status: JobStatus
    version: int
    created_at: datetime
    updated_at: datetime
