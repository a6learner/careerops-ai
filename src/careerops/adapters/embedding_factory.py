import os

from careerops.adapters.fake_embedding_provider import FakeEmbeddingProvider
from careerops.adapters.gemini_embedding_provider import GeminiEmbeddingProvider
from careerops.core.config import Settings
from careerops.domain.embeddings import (
    EMBEDDING_DIMENSIONS,
    FAKE_EMBEDDING_SPACE,
    GEMINI_EMBEDDING_SPACE,
    EmbeddingOutput,
    EmbeddingSpace,
    embedding_space_for_provider,
)
from careerops.domain.errors import EmbeddingProviderError, EmbeddingProviderFailureReason
from careerops.services.embedding_execution import EmbeddingProvider

LIVE_EMBEDDING_ENV = "CAREEROPS_RUN_EMBEDDING_INTEGRATION"


class UnavailableEmbeddingProvider:
    def __init__(self, model_name: str, reason: EmbeddingProviderFailureReason) -> None:
        self._model_name = model_name
        self._reason = reason

    @property
    def model_name(self) -> str:
        return self._model_name

    async def embed(self, input_text: str) -> EmbeddingOutput:
        raise EmbeddingProviderError(self._reason)


class ConfiguredEmbeddingProviderResolver:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def resolve(self, model_name: str, document_input_version: str) -> EmbeddingProvider:
        if (
            model_name == FAKE_EMBEDDING_SPACE.model_name
            and document_input_version == FAKE_EMBEDDING_SPACE.document_input_version
        ):
            return FakeEmbeddingProvider()
        if (
            model_name != GEMINI_EMBEDDING_SPACE.model_name
            or document_input_version != GEMINI_EMBEDDING_SPACE.document_input_version
        ):
            return UnavailableEmbeddingProvider(
                model_name,
                EmbeddingProviderFailureReason.MISCONFIGURED,
            )
        if os.environ.get(LIVE_EMBEDDING_ENV) != "1":
            return UnavailableEmbeddingProvider(
                model_name,
                EmbeddingProviderFailureReason.DISABLED,
            )
        if self._settings.gemini_api_key is None:
            return UnavailableEmbeddingProvider(
                model_name,
                EmbeddingProviderFailureReason.MISCONFIGURED,
            )
        return GeminiEmbeddingProvider(
            api_key=self._settings.gemini_api_key.get_secret_value(),
            model=GEMINI_EMBEDDING_SPACE.model_name,
            output_dimensionality=EMBEDDING_DIMENSIONS,
            timeout_seconds=self._settings.embedding_timeout_seconds,
            max_attempts=self._settings.embedding_max_attempts,
            retry_base_delay_seconds=self._settings.embedding_retry_base_delay_seconds,
            base_url=self._settings.gemini_base_url,
        )


def get_embedding_space(settings: Settings) -> EmbeddingSpace:
    return embedding_space_for_provider(settings.embedding_provider)
