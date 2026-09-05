from datetime import date, datetime
from typing import Self
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from careerops.domain.jobs import JobStatus


class JobCreateRequest(BaseModel):
    company: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=200)
    raw_description: str = Field(min_length=1, max_length=50_000)
    source_url: str | None = Field(default=None, max_length=2_048)
    location: str | None = Field(default=None, max_length=200)
    deadline: date | None = None
    status: JobStatus = JobStatus.SAVED

    @field_validator("company", "title", "raw_description", "source_url", "location")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if stripped == "":
            raise ValueError("field must not be blank")
        return stripped


class JobUpdateRequest(BaseModel):
    company: str | None = Field(default=None, min_length=1, max_length=200)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    raw_description: str | None = Field(default=None, min_length=1, max_length=50_000)
    source_url: str | None = Field(default=None, max_length=2_048)
    location: str | None = Field(default=None, max_length=200)
    deadline: date | None = None
    status: JobStatus | None = None

    @field_validator("company", "title", "raw_description", "source_url", "location")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return JobCreateRequest.strip_text(value)

    @model_validator(mode="after")
    def require_at_least_one_field(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("at least one field must be provided")
        return self


class JobResponse(BaseModel):
    id: UUID
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


class JobListResponse(BaseModel):
    items: list[JobResponse]
    next_cursor: str | None
