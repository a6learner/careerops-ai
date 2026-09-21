from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from careerops.domain.embeddings import EMBEDDING_INPUT_VERSION, FAKE_EMBEDDING_MODEL_NAME
from careerops.domain.errors import (
    EmbeddingRunDispatchError,
    ExperienceNotFoundError,
    ExperienceVersionConflictError,
)
from careerops.domain.experiences import (
    ExperienceCreate,
    ExperienceKind,
    ExperienceRecord,
    ExperienceUpdate,
)
from careerops.services.experiences import ExperienceService, compute_experience_content_hash


class InMemoryExperienceStore:
    def __init__(self, existing: ExperienceRecord | None = None) -> None:
        self.existing = existing
        self.created_hash: str | None = None
        self.updated_hash: str | None = None
        self.committed = False
        self.deleted = False

    async def create_experience(
        self,
        payload: ExperienceCreate,
        content_hash: str,
    ) -> ExperienceRecord:
        self.created_hash = content_hash
        now = datetime.now(UTC)
        return ExperienceRecord(
            id=uuid4(),
            user_id=payload.user_id,
            title=payload.title,
            kind=payload.kind,
            description=payload.description,
            skills=payload.skills,
            outcome=payload.outcome,
            version=1,
            content_hash=content_hash,
            created_at=now,
            updated_at=now,
        )

    async def list_experiences(self, user_id: UUID) -> list[ExperienceRecord]:
        if self.existing is None or self.existing.user_id != user_id:
            return []
        return [self.existing]

    async def get_experience(self, user_id: UUID, experience_id: UUID) -> ExperienceRecord | None:
        if self.existing is None:
            return None
        if self.existing.user_id != user_id or self.existing.id != experience_id:
            return None
        return self.existing

    async def update_experience(
        self,
        user_id: UUID,
        experience_id: UUID,
        expected_version: int,
        payload: ExperienceUpdate,
        content_hash: str,
    ) -> ExperienceRecord | None:
        self.updated_hash = content_hash
        if self.existing is None or self.existing.version != expected_version:
            return None
        now = datetime.now(UTC)
        return ExperienceRecord(
            id=experience_id,
            user_id=user_id,
            title=payload.title or self.existing.title,
            kind=payload.kind or self.existing.kind,
            description=payload.description or self.existing.description,
            skills=payload.skills or self.existing.skills,
            outcome=None if payload.clear_outcome else payload.outcome or self.existing.outcome,
            version=expected_version + 1,
            content_hash=content_hash,
            created_at=self.existing.created_at,
            updated_at=now,
        )

    async def soft_delete_experience(self, user_id: UUID, experience_id: UUID) -> bool:
        self.deleted = self.existing is not None and self.existing.user_id == user_id
        return self.deleted

    async def commit(self) -> None:
        self.committed = True


class InMemoryEmbeddingRunScheduler:
    def __init__(self) -> None:
        self.created: list[tuple[ExperienceRecord, str, str, UUID]] = []
        self.superseded: list[tuple[UUID, UUID]] = []

    async def create_run(
        self,
        experience: ExperienceRecord,
        model_name: str,
        input_version: str,
    ) -> UUID:
        run_id = uuid4()
        self.created.append((experience, model_name, input_version, run_id))
        return run_id

    async def supersede_active_runs(self, user_id: UUID, experience_id: UUID) -> None:
        self.superseded.append((user_id, experience_id))


class RecordingDispatcher:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.dispatched: list[UUID] = []

    async def dispatch(self, run_id: UUID) -> None:
        if self.fail:
            raise EmbeddingRunDispatchError()
        self.dispatched.append(run_id)


def make_service(
    store: InMemoryExperienceStore,
    scheduler: InMemoryEmbeddingRunScheduler | None = None,
    dispatcher: RecordingDispatcher | None = None,
) -> ExperienceService:
    return ExperienceService(
        store,
        scheduler or InMemoryEmbeddingRunScheduler(),
        dispatcher or RecordingDispatcher(),
    )


def make_create(user_id: UUID) -> ExperienceCreate:
    return ExperienceCreate(
        user_id=user_id,
        title="CareerOps AI",
        kind=ExperienceKind.PROJECT,
        description="Built auth and database migrations.",
        skills=("Python", "FastAPI"),
        outcome="Passed strict checks.",
    )


def make_record(user_id: UUID) -> ExperienceRecord:
    now = datetime.now(UTC)
    payload = make_create(user_id)
    return ExperienceRecord(
        id=uuid4(),
        user_id=user_id,
        title=payload.title,
        kind=payload.kind,
        description=payload.description,
        skills=payload.skills,
        outcome=payload.outcome,
        version=2,
        content_hash=compute_experience_content_hash(payload),
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_create_experience_computes_hash_and_commits() -> None:
    store = InMemoryExperienceStore()
    scheduler = InMemoryEmbeddingRunScheduler()
    dispatcher = RecordingDispatcher()
    service = make_service(store, scheduler, dispatcher)
    payload = make_create(uuid4())

    experience = await service.create_experience(payload)

    assert experience.content_hash == compute_experience_content_hash(payload)
    assert store.created_hash == experience.content_hash
    assert store.committed
    assert scheduler.created[0][:3] == (
        experience,
        FAKE_EMBEDDING_MODEL_NAME,
        EMBEDDING_INPUT_VERSION,
    )
    assert dispatcher.dispatched == [scheduler.created[0][3]]


@pytest.mark.asyncio
async def test_create_experience_keeps_committed_work_when_dispatch_fails() -> None:
    store = InMemoryExperienceStore()
    service = make_service(store, dispatcher=RecordingDispatcher(fail=True))

    experience = await service.create_experience(make_create(uuid4()))

    assert experience.version == 1
    assert store.committed


@pytest.mark.asyncio
async def test_get_experience_raises_not_found_when_store_returns_none() -> None:
    service = make_service(InMemoryExperienceStore())

    with pytest.raises(ExperienceNotFoundError):
        await service.get_experience(uuid4(), uuid4())


@pytest.mark.asyncio
async def test_update_experience_rejects_stale_version() -> None:
    user_id = uuid4()
    existing = make_record(user_id)
    service = make_service(InMemoryExperienceStore(existing))

    with pytest.raises(ExperienceVersionConflictError):
        await service.update_experience(
            user_id=user_id,
            experience_id=existing.id,
            expected_version=1,
            payload=ExperienceUpdate(title="Updated title"),
        )


@pytest.mark.asyncio
async def test_delete_experience_commits_soft_delete() -> None:
    user_id = uuid4()
    store = InMemoryExperienceStore(make_record(user_id))
    scheduler = InMemoryEmbeddingRunScheduler()
    service = make_service(store, scheduler)

    await service.delete_experience(user_id, store.existing.id if store.existing else uuid4())

    assert store.deleted
    assert store.committed
    assert store.existing is not None
    assert scheduler.superseded == [(user_id, store.existing.id)]


@pytest.mark.asyncio
async def test_update_supersedes_old_run_and_schedules_new_version() -> None:
    user_id = uuid4()
    existing = make_record(user_id)
    store = InMemoryExperienceStore(existing)
    scheduler = InMemoryEmbeddingRunScheduler()
    dispatcher = RecordingDispatcher()
    service = make_service(store, scheduler, dispatcher)

    updated = await service.update_experience(
        user_id=user_id,
        experience_id=existing.id,
        expected_version=existing.version,
        payload=ExperienceUpdate(title="Updated title"),
    )

    assert updated.version == existing.version + 1
    assert scheduler.superseded == [(user_id, existing.id)]
    assert scheduler.created[0][0] == updated
    assert dispatcher.dispatched == [scheduler.created[0][3]]
