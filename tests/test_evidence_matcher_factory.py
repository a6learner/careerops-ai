from pathlib import Path

import pytest

from careerops.adapters.evidence_matcher_factory import (
    GROQ_EVIDENCE_MATCHER_MAX_OUTPUT_TOKENS,
    GROQ_EVIDENCE_MATCHER_MODEL,
    LIVE_MATCHER_ENV,
    ConfiguredEvidenceMatcherResolver,
    configured_evidence_matcher_model,
)
from careerops.adapters.fake_evidence_matcher import FakeEvidenceMatcher
from careerops.adapters.groq_evidence_matcher import GroqEvidenceMatcher
from careerops.core.config import Settings
from careerops.domain.analysis_runs import FAKE_ANALYSIS_MODEL_NAME
from careerops.domain.errors import EvidenceMatcherError, EvidenceMatcherFailureReason
from careerops.domain.evidence_matching import (
    MATCHER_PROMPT_VERSION_V1,
    MATCHER_PROMPT_VERSION_V4,
    MATCHER_SCHEMA_VERSION,
    EvidenceMatcherInput,
)


def empty_matcher_input() -> EvidenceMatcherInput:
    return EvidenceMatcherInput(
        schema_version=MATCHER_SCHEMA_VERSION,
        prompt_version=MATCHER_PROMPT_VERSION_V4,
        requirements=(),
        experiences=(),
        candidate_sets=(),
    )


def test_configured_model_defaults_to_fake() -> None:
    settings = Settings(_env_file=None)

    assert configured_evidence_matcher_model(settings) == FAKE_ANALYSIS_MODEL_NAME
    assert isinstance(
        ConfiguredEvidenceMatcherResolver(settings).resolve(
            FAKE_ANALYSIS_MODEL_NAME,
            MATCHER_PROMPT_VERSION_V4,
        ),
        FakeEvidenceMatcher,
    )


def test_durable_fake_run_stays_fake_after_global_provider_switch() -> None:
    resolver = ConfiguredEvidenceMatcherResolver(
        Settings(_env_file=None, evidence_matcher_provider="groq")
    )

    matcher = resolver.resolve(
        FAKE_ANALYSIS_MODEL_NAME,
        MATCHER_PROMPT_VERSION_V4,
    )

    assert isinstance(matcher, FakeEvidenceMatcher)


@pytest.mark.asyncio
async def test_dotenv_cannot_enable_real_worker_matcher(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(LIVE_MATCHER_ENV, raising=False)
    (tmp_path / ".env").write_text(
        "CAREEROPS_RUN_REAL_MATCHER_WORKER=1\n"
        "CAREEROPS_LLM_API_KEY=test-key\n"
        "CAREEROPS_EVIDENCE_MATCHER_PROVIDER=groq\n",
        encoding="utf-8",
    )
    matcher = ConfiguredEvidenceMatcherResolver(Settings()).resolve(
        GROQ_EVIDENCE_MATCHER_MODEL,
        MATCHER_PROMPT_VERSION_V4,
    )

    with pytest.raises(EvidenceMatcherError) as captured:
        await matcher.match(empty_matcher_input())

    assert captured.value.reason is EvidenceMatcherFailureReason.DISABLED


@pytest.mark.asyncio
async def test_enabled_real_worker_without_key_is_misconfigured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(LIVE_MATCHER_ENV, "1")
    matcher = ConfiguredEvidenceMatcherResolver(
        Settings(
            _env_file=None,
            evidence_matcher_provider="groq",
            llm_api_key=None,
        )
    ).resolve(GROQ_EVIDENCE_MATCHER_MODEL, MATCHER_PROMPT_VERSION_V4)

    with pytest.raises(EvidenceMatcherError) as captured:
        await matcher.match(empty_matcher_input())

    assert captured.value.reason is EvidenceMatcherFailureReason.MISCONFIGURED


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("model_name", "prompt_version"),
    [
        ("unreviewed-model", MATCHER_PROMPT_VERSION_V4),
        (GROQ_EVIDENCE_MATCHER_MODEL, MATCHER_PROMPT_VERSION_V1),
    ],
)
async def test_unapproved_real_identity_is_misconfigured(
    model_name: str,
    prompt_version: str,
) -> None:
    matcher = ConfiguredEvidenceMatcherResolver(Settings(_env_file=None)).resolve(
        model_name,
        prompt_version,
    )

    with pytest.raises(EvidenceMatcherError) as captured:
        await matcher.match(empty_matcher_input())

    assert captured.value.reason is EvidenceMatcherFailureReason.MISCONFIGURED


@pytest.mark.asyncio
async def test_malformed_durable_pipeline_is_misconfigured() -> None:
    matcher = ConfiguredEvidenceMatcherResolver(Settings(_env_file=None)).resolve_pipeline(
        GROQ_EVIDENCE_MATCHER_MODEL,
        "malformed-pipeline",
    )

    with pytest.raises(EvidenceMatcherError) as captured:
        await matcher.match(empty_matcher_input())

    assert captured.value.reason is EvidenceMatcherFailureReason.MISCONFIGURED


def test_explicitly_enabled_approved_real_matcher_is_constructed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(LIVE_MATCHER_ENV, "1")
    settings = Settings(
        _env_file=None,
        evidence_matcher_provider="groq",
        llm_api_key="test-key",
    )

    matcher = ConfiguredEvidenceMatcherResolver(settings).resolve(
        GROQ_EVIDENCE_MATCHER_MODEL,
        MATCHER_PROMPT_VERSION_V4,
    )

    assert configured_evidence_matcher_model(settings) == GROQ_EVIDENCE_MATCHER_MODEL
    assert isinstance(matcher, GroqEvidenceMatcher)
    assert matcher.model_name == GROQ_EVIDENCE_MATCHER_MODEL


def real_pipeline(cap_segment: str | None) -> str:
    segments = [
        "match-v2:weighted-rrf-v1:gemini-embedding-2",
        "gemini-embedding-2-search-query-v1:gemini-embedding-2-search-document-v1",
        MATCHER_SCHEMA_VERSION,
        MATCHER_PROMPT_VERSION_V4,
        "matcher-batch-6",
    ]
    if cap_segment is not None:
        segments.append(cap_segment)
    segments.append(GROQ_EVIDENCE_MATCHER_MODEL)
    return ":".join(segments)


@pytest.mark.parametrize(
    ("cap_segment", "expected"),
    [("matcher-cap-2000", 2000), (None, GROQ_EVIDENCE_MATCHER_MAX_OUTPUT_TOKENS)],
)
def test_real_matcher_uses_the_output_cap_recorded_on_the_run(
    monkeypatch: pytest.MonkeyPatch,
    cap_segment: str | None,
    expected: int,
) -> None:
    monkeypatch.setenv(LIVE_MATCHER_ENV, "1")
    resolver = ConfiguredEvidenceMatcherResolver(
        Settings(_env_file=None, evidence_matcher_provider="groq", llm_api_key="test-key")
    )

    matcher = resolver.resolve_pipeline(GROQ_EVIDENCE_MATCHER_MODEL, real_pipeline(cap_segment))

    assert isinstance(matcher, GroqEvidenceMatcher)
    assert matcher.max_output_tokens == expected


@pytest.mark.asyncio
async def test_invalid_output_cap_segment_is_misconfigured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(LIVE_MATCHER_ENV, "1")
    resolver = ConfiguredEvidenceMatcherResolver(
        Settings(_env_file=None, evidence_matcher_provider="groq", llm_api_key="test-key")
    )

    matcher = resolver.resolve_pipeline(
        GROQ_EVIDENCE_MATCHER_MODEL, real_pipeline("matcher-cap-0")
    )

    with pytest.raises(EvidenceMatcherError) as captured:
        await matcher.match(empty_matcher_input())

    assert captured.value.reason is EvidenceMatcherFailureReason.MISCONFIGURED
