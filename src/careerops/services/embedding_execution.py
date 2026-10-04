import math
from typing import Protocol
from uuid import UUID

from careerops.domain.embeddings import (
    EMBEDDING_DIMENSIONS,
    EmbeddingOutput,
    EmbeddingRunErrorCode,
    EmbeddingRunWorkItem,
    render_document_embedding_input,
)
from careerops.domain.errors import (
    EmbeddingOutputValidationError,
    EmbeddingProviderError,
    EmbeddingProviderFailureReason,
)


class EmbeddingProvider(Protocol):
    @property
    def model_name(self) -> str: ...

    async def embed(self, input_text: str) -> EmbeddingOutput: ...


class EmbeddingProviderResolver(Protocol):
    def resolve(self, model_name: str, document_input_version: str) -> EmbeddingProvider: ...


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
    def __init__(
        self,
        store: EmbeddingExecutionStore,
        providers: EmbeddingProviderResolver,
    ) -> None:
        self._store = store
        self._providers = providers

    async def execute(self, run_id: UUID) -> bool:
        work_item = await self._store.claim_run(run_id)
        await self._store.commit()
        if work_item is None:
            return False

        try:
            provider = self._providers.resolve(work_item.model_name, work_item.input_version)
            output = await provider.embed(render_embedding_input(work_item))
            validate_embedding_output(output, work_item)
        except EmbeddingProviderError as exc:
            await self._fail(work_item, provider_error_code(exc.reason))
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


def provider_error_code(reason: EmbeddingProviderFailureReason) -> EmbeddingRunErrorCode:
    if reason is EmbeddingProviderFailureReason.DISABLED:
        return EmbeddingRunErrorCode.PROVIDER_DISABLED
    if reason is EmbeddingProviderFailureReason.MISCONFIGURED:
        return EmbeddingRunErrorCode.PROVIDER_MISCONFIGURED
    return EmbeddingRunErrorCode.PROVIDER_FAILED


def render_embedding_input(work_item: EmbeddingRunWorkItem) -> str:
    return render_document_embedding_input(work_item.experience, work_item.input_version)


def validate_embedding_output(
    output: EmbeddingOutput,
    work_item: EmbeddingRunWorkItem,
) -> None:
    if (
        output.model_name != work_item.model_name
        or len(output.vector) != EMBEDDING_DIMENSIONS
        or any(not math.isfinite(value) for value in output.vector)
        or not any(value != 0 for value in output.vector)
    ):
        raise EmbeddingOutputValidationError()
