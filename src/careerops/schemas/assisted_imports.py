from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from careerops.domain.assisted_imports import AssistedRunStatus, DocumentType, DraftStatus
from careerops.domain.experiences import ExperienceKind


class SourceReferenceResponse(BaseModel):
    field: str
    start: int
    end: int
    quote: str


class ExperienceDraftResponse(BaseModel):
    id: UUID
    cv_import_id: UUID
    status: DraftStatus
    title: str
    kind: ExperienceKind
    description: str
    skills: list[str]
    outcome: str | None
    source_refs: list[SourceReferenceResponse]
    version: int
    confirmed_experience_id: UUID | None
    created_at: datetime
    updated_at: datetime


class ExperienceDraftUpdateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    kind: ExperienceKind
    description: str = Field(min_length=1, max_length=10_000)
    skills: list[str] = Field(default_factory=list, max_length=50)
    outcome: str | None = Field(default=None, max_length=2_000)

    @field_validator("title", "description", "outcome")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("field must not be blank")
        return stripped

    @field_validator("skills")
    @classmethod
    def normalize_skills(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for skill in value:
            stripped = skill.strip()
            if not stripped:
                raise ValueError("skills must not contain blank values")
            key = stripped.casefold()
            if key not in seen:
                seen.add(key)
                normalized.append(stripped)
        return normalized


class CvImportResponse(BaseModel):
    id: UUID
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
    drafts: list[ExperienceDraftResponse]


class JobDiscoveryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=300)
    location: str | None = Field(default=None, max_length=200)
    remote: bool | None = None
    published_within_days: int | None = Field(default=None, ge=1, le=90)

    @field_validator("query", "location")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("field must not be blank")
        return stripped


class JobDiscoveryResultResponse(BaseModel):
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


class JobDiscoveryRunResponse(BaseModel):
    id: UUID
    status: AssistedRunStatus
    query: str
    location: str | None
    remote: bool | None
    published_within_days: int | None
    query_fingerprint: str
    provider_name: str
    attempt: int
    error_code: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    results: list[JobDiscoveryResultResponse]


class JobDraftResponse(BaseModel):
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


class JobDraftUpdateRequest(BaseModel):
    company: str | None = Field(default=None, min_length=1, max_length=200)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    raw_description: str | None = Field(default=None, min_length=1, max_length=50_000)
    location: str | None = Field(default=None, max_length=200)

    @field_validator("company", "title", "raw_description", "location")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("field must not be blank")
        return stripped

    @model_validator(mode="after")
    def require_field(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("at least one field must be provided")
        return self
