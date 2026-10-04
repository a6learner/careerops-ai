import hashlib
import json
import logging
from typing import Protocol
from uuid import UUID

from careerops.domain.embeddings import FAKE_EMBEDDING_SPACE, EmbeddingSpace
from careerops.domain.errors import (
    EmbeddingRunDispatchError,
    ExperienceNotFoundError,
    ExperienceVersionConflictError,
)
from careerops.domain.experiences import ExperienceCreate, ExperienceRecord, ExperienceUpdate
from careerops.services.embedding_recovery import EmbeddingRunDispatcher

logger = logging.getLogger(__name__)


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


class EmbeddingRunScheduler(Protocol):
    async def create_run(
        self,
        experience: ExperienceRecord,
        model_name: str,
        input_version: str,
    ) -> UUID: ...

    async def supersede_active_runs(self, user_id: UUID, experience_id: UUID) -> None: ...


class ExperienceService:
    def __init__(
        self,
        experiences: ExperienceStore,
        embedding_runs: EmbeddingRunScheduler,
        dispatcher: EmbeddingRunDispatcher,
        embedding_space: EmbeddingSpace = FAKE_EMBEDDING_SPACE,
    ) -> None:
        self._experiences = experiences
        self._embedding_runs = embedding_runs
        self._dispatcher = dispatcher
        self._embedding_space = embedding_space

    async def create_experience(self, payload: ExperienceCreate) -> ExperienceRecord:
        content_hash = compute_experience_content_hash(payload)
        experience = await self._experiences.create_experience(payload, content_hash)
        run_id = await self._embedding_runs.create_run(
            experience,
            self._embedding_space.model_name,
            self._embedding_space.document_input_version,
        )
        await self._experiences.commit()
        await self._dispatch_best_effort(run_id)
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
        await self._embedding_runs.supersede_active_runs(user_id, experience_id)
        updated = await self._experiences.update_experience(
            user_id=user_id,
            experience_id=experience_id,
            expected_version=expected_version,
            payload=payload,
            content_hash=content_hash,
        )
        if updated is None:
            raise ExperienceVersionConflictError(current.version)
        run_id = await self._embedding_runs.create_run(
            updated,
            self._embedding_space.model_name,
            self._embedding_space.document_input_version,
        )
        await self._experiences.commit()
        await self._dispatch_best_effort(run_id)
        return updated

    async def delete_experience(self, user_id: UUID, experience_id: UUID) -> None:
        await self._embedding_runs.supersede_active_runs(user_id, experience_id)
        deleted = await self._experiences.soft_delete_experience(user_id, experience_id)
        if not deleted:
            raise ExperienceNotFoundError()
        await self._experiences.commit()

    async def _dispatch_best_effort(self, run_id: UUID) -> None:
        try:
            await self._dispatcher.dispatch(run_id)
        except EmbeddingRunDispatchError:
            logger.warning("Embedding run dispatch failed run_id=%s", run_id)


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
