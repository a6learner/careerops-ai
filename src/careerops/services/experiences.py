import hashlib
import json
from typing import Protocol
from uuid import UUID

from careerops.domain.errors import ExperienceNotFoundError, ExperienceVersionConflictError
from careerops.domain.experiences import ExperienceCreate, ExperienceRecord, ExperienceUpdate


class ExperienceStore(Protocol):
    async def create_experience(
        self,
        payload: ExperienceCreate,
        content_hash: str,
    ) -> ExperienceRecord:
        ...

    async def list_experiences(self, user_id: UUID) -> list[ExperienceRecord]: ...

    async def get_experience(
        self,
        user_id: UUID,
        experience_id: UUID,
    ) -> ExperienceRecord | None: ...

    async def update_experience(
        self,
        user_id: UUID,
        experience_id: UUID,
        expected_version: int,
        payload: ExperienceUpdate,
        content_hash: str,
    ) -> ExperienceRecord | None: ...

    async def soft_delete_experience(
        self,
        user_id: UUID,
        experience_id: UUID,
    ) -> bool: ...

    async def commit(self) -> None: ...


class ExperienceService:
    def __init__(self, experiences: ExperienceStore) -> None:
        self._experiences = experiences

    async def create_experience(self, payload: ExperienceCreate) -> ExperienceRecord:
        content_hash = compute_experience_content_hash(payload)
        experience = await self._experiences.create_experience(payload, content_hash)
        await self._experiences.commit()
        return experience

    async def list_experiences(self, user_id: UUID) -> list[ExperienceRecord]:
        return await self._experiences.list_experiences(user_id)

    async def get_experience(self, user_id: UUID, experience_id: UUID) -> ExperienceRecord:
        experience = await self._experiences.get_experience(user_id, experience_id)
        if experience is None:
            raise ExperienceNotFoundError()
        return experience

    async def update_experience(
        self,
        user_id: UUID,
        experience_id: UUID,
        expected_version: int,
        payload: ExperienceUpdate,
    ) -> ExperienceRecord:
        current = await self.get_experience(user_id, experience_id)
        if current.version != expected_version:
            raise ExperienceVersionConflictError(current.version)

        merged = merge_experience(current, payload)
        content_hash = compute_experience_content_hash(
            ExperienceCreate(
                user_id=user_id,
                title=merged.title,
                kind=merged.kind,
                description=merged.description,
                skills=merged.skills,
                outcome=merged.outcome,
            )
        )
        updated = await self._experiences.update_experience(
            user_id=user_id,
            experience_id=experience_id,
            expected_version=expected_version,
            payload=payload,
            content_hash=content_hash,
        )
        if updated is None:
            raise ExperienceVersionConflictError(current.version)
        await self._experiences.commit()
        return updated

    async def delete_experience(self, user_id: UUID, experience_id: UUID) -> None:
        deleted = await self._experiences.soft_delete_experience(user_id, experience_id)
        if not deleted:
            raise ExperienceNotFoundError()
        await self._experiences.commit()


def compute_experience_content_hash(payload: ExperienceCreate) -> str:
    normalized = {
        "title": payload.title,
        "kind": payload.kind.value,
        "description": payload.description,
        "skills": list(payload.skills),
        "outcome": payload.outcome,
    }
    encoded = json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def merge_experience(current: ExperienceRecord, update: ExperienceUpdate) -> ExperienceRecord:
    outcome = current.outcome
    if update.clear_outcome:
        outcome = None
    elif update.outcome is not None:
        outcome = update.outcome

    return ExperienceRecord(
        id=current.id,
        user_id=current.user_id,
        title=update.title if update.title is not None else current.title,
        kind=update.kind if update.kind is not None else current.kind,
        description=update.description if update.description is not None else current.description,
        skills=update.skills if update.skills is not None else current.skills,
        outcome=outcome,
        version=current.version,
        content_hash=current.content_hash,
        created_at=current.created_at,
        updated_at=current.updated_at,
    )
