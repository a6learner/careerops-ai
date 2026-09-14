from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from careerops.domain.action_items import ActionItemStatus


class ActionItemCreateRequest(BaseModel):
    job_id: UUID
    title: str = Field(min_length=1, max_length=200)
    source_evidence_match_id: UUID | None = None

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str) -> str:
        stripped = value.strip()
        if stripped == "":
            raise ValueError("title must not be blank")
        return stripped


class ActionItemUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    status: ActionItemStatus | None = None

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return ActionItemCreateRequest.strip_title(value)

    @model_validator(mode="after")
    def require_at_least_one_field(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("at least one field must be provided")
        if self.title is None and self.status is None:
            raise ValueError("at least one field must be non-null")
        return self


class ActionItemResponse(BaseModel):
    id: UUID
    job_id: UUID
    source_evidence_match_id: UUID | None
    title: str
    status: ActionItemStatus
    version: int
    job_is_archived: bool
    created_at: datetime
    updated_at: datetime


class ActionItemListResponse(BaseModel):
    items: list[ActionItemResponse]
    next_cursor: str | None
