from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from careerops.domain.experiences import ExperienceKind


class ExperienceCreateRequest(BaseModel):
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
        if stripped == "":
            raise ValueError("field must not be blank")
        return stripped

    @field_validator("skills")
    @classmethod
    def normalize_skills(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for skill in value:
            stripped = skill.strip()
            if stripped == "":
                raise ValueError("skills must not contain blank values")
            key = stripped.casefold()
            if key not in seen:
                seen.add(key)
                normalized.append(stripped)
        return normalized


class ExperienceUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    kind: ExperienceKind | None = None
    description: str | None = Field(default=None, min_length=1, max_length=10_000)
    skills: list[str] | None = Field(default=None, max_length=50)
    outcome: str | None = Field(default=None, max_length=2_000)

    @field_validator("title", "description", "outcome")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return ExperienceCreateRequest.strip_text(value)

    @field_validator("skills")
    @classmethod
    def normalize_skills(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        return ExperienceCreateRequest.normalize_skills(value)

    @model_validator(mode="after")
    def require_at_least_one_field(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("at least one field must be provided")
        return self


class ExperienceResponse(BaseModel):
    id: UUID
    title: str
    kind: ExperienceKind
    description: str
    skills: list[str]
    outcome: str | None
    version: int
    content_hash: str
    created_at: datetime
    updated_at: datetime


class ExperienceListResponse(BaseModel):
    items: list[ExperienceResponse]
