from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from careerops.domain.experiences import ExperienceKind

CV_EXTRACTOR_NAME = "deterministic-extractive-v1"
FAKE_JOB_SEARCH_PROVIDER = "fake-search-v1"
MAX_CV_BYTES = 5 * 1024 * 1024


class AssistedRunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class DraftStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class DocumentType(StrEnum):
    PDF = "pdf"
    DOCX = "docx"
    DOC = "doc"
    ODT = "odt"
    RTF = "rtf"
    TEXT = "txt"
    MARKDOWN = "markdown"


class CvImportErrorCode(StrEnum):
    ENCRYPTED_DOCUMENT = "ENCRYPTED_DOCUMENT"
    EMPTY_TEXT = "EMPTY_TEXT"
    EXTRACTOR_FAILED = "EXTRACTOR_FAILED"
    INVALID_ARCHIVE = "INVALID_ARCHIVE"
    UNSUPPORTED_DOCUMENT = "UNSUPPORTED_DOCUMENT"


class JobDiscoveryErrorCode(StrEnum):
    SEARCH_FAILED = "SEARCH_FAILED"
    SEARCH_OUTPUT_INVALID = "SEARCH_OUTPUT_INVALID"


@dataclass(frozen=True)
class SourceReference:
    field: str
    start: int
    end: int
    quote: str


@dataclass(frozen=True)
class ExtractedExperienceDraft:
    title: str
    kind: ExperienceKind
    description: str
    skills: tuple[str, ...]
    outcome: str | None
    source_refs: tuple[SourceReference, ...]


@dataclass(frozen=True)
class ExperienceDraftRecord:
    id: UUID
    cv_import_id: UUID
    status: DraftStatus
    title: str
    kind: ExperienceKind
    description: str
    skills: tuple[str, ...]
    outcome: str | None
    source_refs: tuple[SourceReference, ...]
    version: int
    confirmed_experience_id: UUID | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class CvImportRecord:
    id: UUID
    user_id: UUID
    status: AssistedRunStatus
    filename: str
    document_type: DocumentType
    media_type: str
    size_bytes: int
    content_sha256: str
    extractor_name: str
    attempt: int
    error_code: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    drafts: tuple[ExperienceDraftRecord, ...]


@dataclass(frozen=True)
class CvImportWorkItem:
    id: UUID
    document_type: DocumentType
    filename: str
    source_bytes: bytes


@dataclass(frozen=True)
class JobSearchQuery:
    query: str
    location: str | None
    remote: bool | None
    published_within_days: int | None


@dataclass(frozen=True)
class JobSearchResult:
    provider_result_id: str
    company: str
    title: str
    source_url: str
    summary: str
    raw_description: str | None
    location: str | None
    published_at: datetime | None


@dataclass(frozen=True)
class JobDiscoveryResultRecord:
    id: UUID
    provider_result_id: str
    company: str
    title: str
    source_url: str
    summary: str
    raw_description: str | None
    location: str | None
    published_at: datetime | None
    observed_at: datetime


@dataclass(frozen=True)
class JobDiscoveryRunRecord:
    id: UUID
    user_id: UUID
    status: AssistedRunStatus
    query: JobSearchQuery
    query_fingerprint: str
    provider_name: str
    attempt: int
    error_code: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    results: tuple[JobDiscoveryResultRecord, ...]


@dataclass(frozen=True)
class JobDiscoveryWorkItem:
    id: UUID
    query: JobSearchQuery


@dataclass(frozen=True)
class JobDraftRecord:
    id: UUID
    result_id: UUID
    status: DraftStatus
    company: str
    title: str
    raw_description: str | None
    source_url: str
    location: str | None
    version: int
    confirmed_job_id: UUID | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class JobDraftUpdate:
    company: str | None = None
    title: str | None = None
    raw_description: str | None = None
    location: str | None = None
    clear_location: bool = False
