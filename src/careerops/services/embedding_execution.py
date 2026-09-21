import json
import math
from typing import Protocol
from uuid import UUID

from careerops.domain.embeddings import (
    EMBEDDING_DIMENSIONS,
    EmbeddingOutput,
    EmbeddingRunErrorCode,
    EmbeddingRunWorkItem,
)
from careerops.domain.errors import EmbeddingOutputValidationError, EmbeddingProviderError


class EmbeddingProvider(Protocol):
    @property
    def model_name(self) -> str: ...

    async def embed(self, input_text: str) -> EmbeddingOutput: ...


class EmbeddingExecutionStore(Protocol):
    async def claim_run(self, run_id: UUID) -> EmbeddingRunWorkItem | None: ...

    async def complete_run(
        self,
        work_item: EmbeddingRunWorkItem,
        vector: tuple[float, ...],
    ) -> bool: ...

    async def fail_run(
        self,
        work_item: EmbeddingRunWorkItem,
        error_code: EmbeddingRunErrorCode,
    ) -> bool: ...

    async def commit(self) -> None: ...


class EmbeddingExecutionService:
    def __init__(self, store: EmbeddingExecutionStore, provider: EmbeddingProvider) -> None:
        self._store = store
        self._provider = provider

    async def execute(self, run_id: UUID) -> bool:
        work_item = await self._store.claim_run(run_id)
        await self._store.commit()
        if work_item is None:
            return False

        try:
            output = await self._provider.embed(render_embedding_input(work_item))
            validate_embedding_output(output, work_item)
        except EmbeddingProviderError:
            await self._fail(work_item, EmbeddingRunErrorCode.PROVIDER_FAILED)
            return True
        except EmbeddingOutputValidationError:
            await self._fail(work_item, EmbeddingRunErrorCode.OUTPUT_INVALID)
            return True

        completed = await self._store.complete_run(work_item, output.vector)
        await self._store.commit()
        return completed

    async def _fail(
        self,
        work_item: EmbeddingRunWorkItem,
        error_code: EmbeddingRunErrorCode,
    ) -> None:
        if await self._store.fail_run(work_item, error_code):
            await self._store.commit()


def render_embedding_input(work_item: EmbeddingRunWorkItem) -> str:
    experience = work_item.experience
    payload = {
        "description": experience.description,
        "kind": experience.kind.value,
        "outcome": experience.outcome,
        "skills": list(experience.skills),
        "title": experience.title,
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def validate_embedding_output(
    output: EmbeddingOutput,
    work_item: EmbeddingRunWorkItem,
) -> None:
    if (
        output.model_name != work_item.model_name
        or len(output.vector) != EMBEDDING_DIMENSIONS
        or any(not math.isfinite(value) for value in output.vector)
    ):
        raise EmbeddingOutputValidationError()
