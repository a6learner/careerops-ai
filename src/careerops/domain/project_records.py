from datetime import datetime
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class RecordStatus(StrEnum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    WITHDRAWN = "withdrawn"


class RecordInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, frozen=True)

    @field_validator("*", mode="before")
    @classmethod
    def no_null_characters(cls, value: object) -> object:
        if isinstance(value, str) and "\x00" in value:
            raise ValueError("Null characters cannot be stored in project records.")
        return value


class ProjectInput(RecordInput):
    name: str = Field(min_length=1, max_length=160)
    goal: str = Field(min_length=1, max_length=2000)


class EvidenceSource(RecordInput):
    kind: Literal["repository_excerpt", "test_output", "user_note"]
    locator: str = Field(min_length=1, max_length=300)
    content: str = Field(min_length=1, max_length=8000)
    quote: str = Field(min_length=1, max_length=2000)

    @field_validator("locator")
    @classmethod
    def safe_locator(cls, value: str) -> str:
        path = PurePosixPath(value)
        if (
            "\\" in value
            or ":" in value
            or path.is_absolute()
            or ".." in path.parts
            or any(part.casefold() in {".env", ".git", ".aws", ".ssh"} for part in path.parts)
            or any(part.casefold().startswith(".env.") for part in path.parts)
        ):
            raise ValueError("Use a relative, non-sensitive source label; no URLs or parent paths.")
        return value

    @model_validator(mode="after")
    def grounded_quote(self) -> Self:
        if self.quote not in self.content:
            raise ValueError("Source quote must occur exactly in the supplied content.")
        return self


class CheckpointInput(RecordInput):
    schema_version: Literal["1"] = "1"
    title: str = Field(min_length=1, max_length=200)
    objective: str = Field(min_length=1, max_length=2000)
    changes: str = Field(min_length=1, max_length=4000)
    decisions: str = Field(default="", max_length=4000)
    failures: str = Field(default="", max_length=4000)
    verification: str = Field(default="", max_length=4000)
    remaining: str = Field(default="", max_length=2000)
    contribution: str = Field(default="", max_length=2000)
    host: str = Field(min_length=1, max_length=100)
    base_revision: str | None = Field(default=None, min_length=1, max_length=100)
    sources: tuple[EvidenceSource, ...] = Field(min_length=1, max_length=8)

    @model_validator(mode="after")
    def bounded_packet(self) -> Self:
        if len(self.model_dump_json().encode("utf-8")) > 131072:
            raise ValueError("Checkpoint packet must not exceed 128 KiB of UTF-8 JSON.")
        return self


class ReviewInput(RecordInput):
    status: Literal[RecordStatus.CONFIRMED, RecordStatus.WITHDRAWN]
    contribution_note: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def explicit_contribution(self) -> Self:
        if self.status == RecordStatus.CONFIRMED and not self.contribution_note:
            raise ValueError("Confirm what you personally contributed before confirming a record.")
        return self


class ProjectRecord(BaseModel):
    id: UUID
    name: str
    goal: str
    created_at: datetime


class CheckpointRecord(BaseModel):
    id: UUID
    project_id: UUID
    status: RecordStatus
    version: int
    payload: CheckpointInput
    content_sha256: str
    contribution_note: str
    created_at: datetime
    reviewed_at: datetime | None


class RecordCursor(BaseModel):
    created_at: datetime
    id: UUID

    @field_validator("created_at")
    @classmethod
    def timezone_required(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("Cursor must contain a timezone.")
        return value


class ProjectPage(BaseModel):
    items: list[ProjectRecord]
    next_cursor: str | None


class CheckpointPage(BaseModel):
    items: list[CheckpointRecord]
    next_cursor: str | None


class ProjectRecordNotFoundError(Exception):
    pass


class ProjectRecordConflictError(Exception):
    pass
