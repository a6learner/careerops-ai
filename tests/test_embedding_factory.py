from pathlib import Path

import pytest

from careerops.adapters.embedding_factory import (
    LIVE_EMBEDDING_ENV,
    ConfiguredEmbeddingProviderResolver,
)
from careerops.adapters.fake_embedding_provider import FakeEmbeddingProvider
from careerops.core.config import Settings
from careerops.domain.embeddings import FAKE_EMBEDDING_SPACE, GEMINI_EMBEDDING_SPACE
from careerops.domain.errors import EmbeddingProviderError, EmbeddingProviderFailureReason


def test_durable_fake_run_resolves_fake_after_global_provider_switch() -> None:
    resolver = ConfiguredEmbeddingProviderResolver(
        Settings(_env_file=None, embedding_provider="gemini")
    )

    provider = resolver.resolve(
        FAKE_EMBEDDING_SPACE.model_name,
        FAKE_EMBEDDING_SPACE.document_input_version,
    )

    assert isinstance(provider, FakeEmbeddingProvider)


@pytest.mark.asyncio
async def test_dotenv_cannot_enable_gemini(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(LIVE_EMBEDDING_ENV, raising=False)
    (tmp_path / ".env").write_text(
        "CAREEROPS_RUN_EMBEDDING_INTEGRATION=1\nCAREEROPS_GEMINI_API_KEY=test-key\n",
        encoding="utf-8",
    )
    resolver = ConfiguredEmbeddingProviderResolver(
        Settings(embedding_provider="gemini")
    )
    provider = resolver.resolve(
        GEMINI_EMBEDDING_SPACE.model_name,
        GEMINI_EMBEDDING_SPACE.document_input_version,
    )

    with pytest.raises(EmbeddingProviderError) as captured:
        await provider.embed("offline test")

    assert captured.value.reason is EmbeddingProviderFailureReason.DISABLED


@pytest.mark.asyncio
async def test_enabled_gemini_without_key_is_misconfigured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(LIVE_EMBEDDING_ENV, "1")
    resolver = ConfiguredEmbeddingProviderResolver(
        Settings(_env_file=None, embedding_provider="gemini", gemini_api_key=None)
    )
    provider = resolver.resolve(
        GEMINI_EMBEDDING_SPACE.model_name,
        GEMINI_EMBEDDING_SPACE.document_input_version,
    )

    with pytest.raises(EmbeddingProviderError) as captured:
        await provider.embed("offline test")

    assert captured.value.reason is EmbeddingProviderFailureReason.MISCONFIGURED
