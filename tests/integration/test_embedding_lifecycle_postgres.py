import asyncio
import os
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select, update

from careerops.adapters.fake_embedding_provider import FakeEmbeddingProvider
from careerops.api.dependencies import get_current_user
from careerops.api.experiences import get_embedding_run_dispatcher
from careerops.core.config import Settings
from careerops.db.models import Experience, ExperienceEmbeddingRun, User
from careerops.db.session import create_session_factory
from careerops.domain.embeddings import (
    EMBEDDING_INPUT_VERSION,
    FAKE_EMBEDDING_MODEL_NAME,
    EmbeddingRunStatus,
    EmbeddingRunWorkItem,
)
from careerops.domain.users import UserAccount
from careerops.main import create_app
from careerops.repositories.embedding_runs import EmbeddingRunRepository
from careerops.repositories.experiences import to_record
from careerops.services.embedding_execution import EmbeddingExecutionService

pytestmark = pytest.mark.integration


class RecordingDispatcher:
    def __init__(self) -> None:
        self.ids: list[UUID] = []

    async def dispatch(self, run_id: UUID) -> None:
        self.ids.append(run_id)


@pytest.mark.skipif(
    os.getenv("CAREEROPS_RUN_INTEGRATION") != "1",
    reason="requires local PostgreSQL container",
)
@pytest.mark.asyncio
async def test_embedding_lifecycle_rejects_stale_completion_and_writes_current_vector() -> None:
    session_factory = create_session_factory(Settings().database_url)
    user_id = uuid4()
    now = datetime.now(UTC)
    async with session_factory() as setup_session:
        setup_session.add(
            User(
                id=user_id,
                email=f"embedding-{uuid4()}@example.com",
                password_hash="x",
            )
        )
        await setup_session.commit()

    app = create_app()
    dispatcher = RecordingDispatcher()

    async def current_user() -> UserAccount:
        return UserAccount(id=user_id, email="student@example.com", created_at=now)

    app.dependency_overrides[get_current_user] = current_user
    app.dependency_overrides[get_embedding_run_dispatcher] = lambda: dispatcher

    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            created = await client.post(
                "/api/v1/experiences",
                json={
                    "title": "CareerOps AI",
                    "kind": "project",
                    "description": "Built reliable APIs.",
                    "skills": ["Python", "PostgreSQL"],
                    "outcome": "Passed strict checks.",
                },
            )
            assert created.status_code == 201
            experience_id = UUID(created.json()["id"])
            old_run_id = dispatcher.ids[-1]

            async with session_factory() as unauthorized_session:
                unauthorized_repository = EmbeddingRunRepository(unauthorized_session)
                await unauthorized_repository.supersede_active_runs(uuid4(), experience_id)
                await unauthorized_repository.commit()

            async with session_factory() as old_worker_session:
                old_repository = EmbeddingRunRepository(old_worker_session)
                old_work_item = await old_repository.claim_run(old_run_id)
                assert old_work_item is not None
                await old_repository.commit()

            updated = await client.patch(
                f"/api/v1/experiences/{experience_id}",
                headers={"If-Match": "1"},
                json={"description": "Built reliable async APIs."},
            )
            assert updated.status_code == 200
            assert updated.json()["version"] == 2
            updated_at = updated.json()["updated_at"]
            new_run_id = dispatcher.ids[-1]
            assert new_run_id != old_run_id

            old_output = await FakeEmbeddingProvider().embed("stale input")
            async with session_factory() as stale_completion_session:
                stale_repository = EmbeddingRunRepository(stale_completion_session)
                assert not await stale_repository.complete_run(old_work_item, old_output.vector)
                await stale_repository.commit()

            async with session_factory() as worker_session:
                executed = await EmbeddingExecutionService(
                    EmbeddingRunRepository(worker_session),
                    FakeEmbeddingProvider(),
                ).execute(new_run_id)
                assert executed

    async with session_factory() as verification_session:
        experience = await verification_session.get(Experience, experience_id)
        assert experience is not None
        assert experience.version == 2
        assert experience.content_hash == updated.json()["content_hash"]
        assert experience.updated_at == datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
        assert experience.embedding is not None
        assert len(experience.embedding) == 1536
        assert experience.embedding_content_hash == experience.content_hash
        assert experience.embedding_model == "local-fake-embedding-1536"
        assert experience.embedding_input_version == "experience-embedding-input-v1"
        runs_result = await verification_session.execute(
            select(ExperienceEmbeddingRun)
            .where(ExperienceEmbeddingRun.experience_id == experience_id)
            .order_by(ExperienceEmbeddingRun.created_at.asc())
        )
        runs = list(runs_result.scalars().all())
        assert [run.status for run in runs] == [
            EmbeddingRunStatus.SUPERSEDED.value,
            EmbeddingRunStatus.SUCCEEDED.value,
        ]

    delete_app = create_app()
    delete_app.dependency_overrides[get_current_user] = current_user
    delete_app.dependency_overrides[get_embedding_run_dispatcher] = lambda: dispatcher
    async with delete_app.router.lifespan_context(delete_app):
        transport = ASGITransport(app=delete_app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            deleted = await client.delete(f"/api/v1/experiences/{experience_id}")
            assert deleted.status_code == 204
            assert dispatcher.ids == [old_run_id, new_run_id]

    async with session_factory() as deleted_verification_session:
        experience = await deleted_verification_session.get(Experience, experience_id)
        assert experience is not None
        assert experience.deleted_at is not None
        assert experience.embedding is None
        assert experience.embedding_content_hash is None
        assert experience.embedding_model is None
        assert experience.embedding_input_version is None
        assert experience.embedded_at is None

    async with session_factory() as cleanup_session:
        await cleanup_session.execute(
            delete(ExperienceEmbeddingRun).where(
                ExperienceEmbeddingRun.experience_id == experience_id
            )
        )
        user = await cleanup_session.get(User, user_id)
        assert user is not None
        await cleanup_session.delete(user)
        await cleanup_session.commit()
    await session_factory.kw["bind"].dispose()


@pytest.mark.skipif(
    os.getenv("CAREEROPS_RUN_INTEGRATION") != "1",
    reason="requires local PostgreSQL container",
)
@pytest.mark.asyncio
async def test_reconciliation_backfills_existing_active_experience_once() -> None:
    session_factory = create_session_factory(Settings().database_url)
    user_id = uuid4()
    experience_id = uuid4()
    async with session_factory() as setup_session:
        setup_session.add(
            User(
                id=user_id,
                email=f"embedding-backfill-{uuid4()}@example.com",
                password_hash="x",
            )
        )
        await setup_session.flush()
        setup_session.add(
            Experience(
                id=experience_id,
                user_id=user_id,
                title="Legacy experience",
                kind="project",
                description="Created before embedding lifecycle.",
                skills=["Python"],
                version=1,
                content_hash="b" * 64,
            )
        )
        await setup_session.commit()

    async with session_factory() as recovery_session:
        repository = EmbeddingRunRepository(recovery_session)
        first = await repository.reconcile_missing_runs(
            "local-fake-embedding-1536",
            "experience-embedding-input-v1",
            100,
        )
        await repository.commit()
        second = await repository.reconcile_missing_runs(
            "local-fake-embedding-1536",
            "experience-embedding-input-v1",
            100,
        )
        own_runs_result = await recovery_session.execute(
            select(ExperienceEmbeddingRun).where(
                ExperienceEmbeddingRun.experience_id == experience_id
            )
        )
        own_runs = list(own_runs_result.scalars().all())
        assert len(own_runs) == 1
        assert own_runs[0].id in first
        assert second == []

    async with session_factory() as cleanup_session:
        user = await cleanup_session.get(User, user_id)
        assert user is not None
        await cleanup_session.delete(user)
        await cleanup_session.commit()
    await session_factory.kw["bind"].dispose()


@pytest.mark.skipif(
    os.getenv("CAREEROPS_RUN_INTEGRATION") != "1",
    reason="requires local PostgreSQL container",
)
@pytest.mark.asyncio
async def test_duplicate_claim_and_recovery_attempt_prevent_stale_worker_write() -> None:
    session_factory = create_session_factory(Settings().database_url)
    user_id = uuid4()
    experience_id = uuid4()
    async with session_factory() as setup_session:
        setup_session.add(
            User(
                id=user_id,
                email=f"embedding-claim-{uuid4()}@example.com",
                password_hash="x",
            )
        )
        await setup_session.flush()
        experience = Experience(
            id=experience_id,
            user_id=user_id,
            title="Concurrent worker test",
            kind="project",
            description="Proves one conditional claim.",
            skills=["PostgreSQL"],
            version=1,
            content_hash="c" * 64,
        )
        setup_session.add(experience)
        await setup_session.flush()
        run_id = await EmbeddingRunRepository(setup_session).create_run(
            to_record(experience),
            FAKE_EMBEDDING_MODEL_NAME,
            EMBEDDING_INPUT_VERSION,
        )
        await setup_session.commit()

    async def claim_once() -> EmbeddingRunWorkItem | None:
        async with session_factory() as claim_session:
            repository = EmbeddingRunRepository(claim_session)
            claimed = await repository.claim_run(run_id)
            await repository.commit()
            return claimed

    claims = await asyncio.gather(claim_once(), claim_once())
    claimed_items = [item for item in claims if item is not None]
    assert len(claimed_items) == 1
    old_work_item = claimed_items[0]

    async with session_factory() as stale_session:
        await stale_session.execute(
            update(ExperienceEmbeddingRun)
            .where(ExperienceEmbeddingRun.id == run_id)
            .values(started_at=datetime.now(UTC) - timedelta(minutes=10))
        )
        await stale_session.commit()

    async with session_factory() as recovery_session:
        repository = EmbeddingRunRepository(recovery_session)
        assert await repository.requeue_stale_runs(datetime.now(UTC), 10) == [run_id]
        await repository.commit()

    async with session_factory() as reclaimed_session:
        repository = EmbeddingRunRepository(reclaimed_session)
        new_work_item = await repository.claim_run(run_id)
        assert new_work_item is not None
        assert new_work_item.attempt == 2
        await repository.commit()

    vector = (0.0,) * 1536
    async with session_factory() as old_completion_session:
        repository = EmbeddingRunRepository(old_completion_session)
        assert not await repository.complete_run(old_work_item, vector)
        await repository.commit()

    async with session_factory() as current_completion_session:
        repository = EmbeddingRunRepository(current_completion_session)
        assert await repository.complete_run(new_work_item, vector)
        await repository.commit()

    async with session_factory() as verification_session:
        run = await verification_session.get(ExperienceEmbeddingRun, run_id)
        experience = await verification_session.get(Experience, experience_id)
        assert run is not None
        assert run.status == EmbeddingRunStatus.SUCCEEDED.value
        assert run.attempt == 2
        assert experience is not None
        assert experience.embedding is not None

    async with session_factory() as cleanup_session:
        user = await cleanup_session.get(User, user_id)
        assert user is not None
        await cleanup_session.delete(user)
        await cleanup_session.commit()
    await session_factory.kw["bind"].dispose()
