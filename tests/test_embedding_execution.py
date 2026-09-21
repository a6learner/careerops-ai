from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from careerops.adapters.fake_embedding_provider import FakeEmbeddingProvider
from careerops.domain.embeddings import (
    EMBEDDING_DIMENSIONS,
    EMBEDDING_INPUT_VERSION,
    FAKE_EMBEDDING_MODEL_NAME,
    EmbeddingOutput,
    EmbeddingRunErrorCode,
    EmbeddingRunWorkItem,
)
from careerops.domain.errors import EmbeddingProviderError
from careerops.domain.experiences import ExperienceKind, ExperienceRecord
from careerops.services.embedding_execution import (
    EmbeddingExecutionService,
    render_embedding_input,
)


class ExecutionStore:
    def __init__(self, work_item: EmbeddingRunWorkItem | None) -> None:
        self.work_item = work_item
        self.completed_vector: tuple[float, ...] | None = None
        self.failed_code: EmbeddingRunErrorCode | None = None
        self.commit_count = 0

    async def claim_run(self, run_id: UUID) -> EmbeddingRunWorkItem | None:
        if self.work_item is None or self.work_item.id != run_id:
            return None
        return self.work_item

    async def complete_run(
        self,
        work_item: EmbeddingRunWorkItem,
        vector: tuple[float, ...],
    ) -> bool:
        self.completed_vector = vector
        return True

    async def fail_run(
        self,
        work_item: EmbeddingRunWorkItem,
        error_code: EmbeddingRunErrorCode,
    ) -> bool:
        self.failed_code = error_code
        return True

    async def commit(self) -> None:
        self.commit_count += 1


class InvalidProvider:
    @property
    def model_name(self) -> str:
        return FAKE_EMBEDDING_MODEL_NAME

    async def embed(self, input_text: str) -> EmbeddingOutput:
        return EmbeddingOutput(self.model_name, (float("nan"),) * EMBEDDING_DIMENSIONS)


class FailingProvider:
    @property
    def model_name(self) -> str:
        return FAKE_EMBEDDING_MODEL_NAME

    async def embed(self, input_text: str) -> EmbeddingOutput:
        raise EmbeddingProviderError()


def make_work_item() -> EmbeddingRunWorkItem:
    now = datetime.now(UTC)
    experience = ExperienceRecord(
        id=uuid4(),
        user_id=uuid4(),
        title="CareerOps AI",
        kind=ExperienceKind.PROJECT,
        description="Built a reliable backend.",
        skills=("Python", "PostgreSQL"),
        outcome="Passed strict checks.",
        version=2,
        content_hash="a" * 64,
        created_at=now,
        updated_at=now,
    )
    return EmbeddingRunWorkItem(
        id=uuid4(),
        attempt=1,
        experience=experience,
        model_name=FAKE_EMBEDDING_MODEL_NAME,
        input_version=EMBEDDING_INPUT_VERSION,
    )


@pytest.mark.asyncio
async def test_fake_embedding_is_deterministic_and_fixed_dimension() -> None:
    provider = FakeEmbeddingProvider()

    first = await provider.embed("same input")
    second = await provider.embed("same input")
    different = await provider.embed("different input")

    assert first == second
    assert first.vector != different.vector
    assert len(first.vector) == EMBEDDING_DIMENSIONS


def test_embedding_input_is_stable_and_contains_meaningful_fields() -> None:
    work_item = make_work_item()

    rendered = render_embedding_input(work_item)

    assert rendered == (
        '{"description":"Built a reliable backend.","kind":"project",'
        '"outcome":"Passed strict checks.","skills":["Python","PostgreSQL"],'
        '"title":"CareerOps AI"}'
    )


@pytest.mark.asyncio
async def test_execution_commits_valid_vector() -> None:
    work_item = make_work_item()
    store = ExecutionStore(work_item)

    service = EmbeddingExecutionService(store, FakeEmbeddingProvider())

    completed = await service.execute(work_item.id)

    assert completed
    assert store.completed_vector is not None
    assert len(store.completed_vector) == EMBEDDING_DIMENSIONS
    assert store.failed_code is None
    assert store.commit_count == 2


@pytest.mark.asyncio
async def test_execution_rejects_non_finite_vector() -> None:
    work_item = make_work_item()
    store = ExecutionStore(work_item)

    handled = await EmbeddingExecutionService(store, InvalidProvider()).execute(work_item.id)

    assert handled
    assert store.completed_vector is None
    assert store.failed_code is EmbeddingRunErrorCode.OUTPUT_INVALID


@pytest.mark.asyncio
async def test_execution_records_provider_failure() -> None:
    work_item = make_work_item()
    store = ExecutionStore(work_item)

    handled = await EmbeddingExecutionService(store, FailingProvider()).execute(work_item.id)

    assert handled
    assert store.failed_code is EmbeddingRunErrorCode.PROVIDER_FAILED


@pytest.mark.asyncio
async def test_duplicate_delivery_without_claim_is_noop() -> None:
    store = ExecutionStore(None)

    completed = await EmbeddingExecutionService(store, FakeEmbeddingProvider()).execute(uuid4())

    assert not completed
    assert store.completed_vector is None
    assert store.commit_count == 1
