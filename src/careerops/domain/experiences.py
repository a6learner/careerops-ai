from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class ExperienceKind(StrEnum):
    PROJECT = "project"
    WORK = "work"
    RESEARCH = "research"
    COURSE = "course"
    OTHER = "other"


@dataclass(frozen=True)
class ExperienceCreate:
    user_id: UUID
    title: str
    kind: ExperienceKind
    description: str
    skills: tuple[str, ...]
    outcome: str | None


@dataclass(frozen=True)
class ExperienceUpdate:
    title: str | None = None
    kind: ExperienceKind | None = None
    description: str | None = None
    skills: tuple[str, ...] | None = None
    outcome: str | None = None
    clear_outcome: bool = False


@dataclass(frozen=True)
class ExperienceRecord:
    id: UUID
    user_id: UUID
    title: str
    kind: ExperienceKind
    description: str
    skills: tuple[str, ...]
    outcome: str | None
    version: int
    content_hash: str
    created_at: datetime
    updated_at: datetime
