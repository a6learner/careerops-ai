from pathlib import Path

import pytest

from careerops.evaluation.embedding_retrieval_v2 import (
    DOCUMENT_INPUT_VERSION,
    QUERY_INPUT_VERSION,
    EmbeddingRankedExperience,
    FakeEmbeddingEvaluationProvider,
    build_input_plan,
    cosine_similarity,
    fill_cache,
    load_cache,
    new_cache,
    render_document_input,
    render_query_input,
    score_query,
    validate_batch,
    validate_vector,
)
from careerops.evaluation.evidence_retrieval_v2 import (
    RetrievalSplit,
    load_corpus,
    load_query_set,
)
from careerops.evaluation.gemini_embedding_provider import (
    EmbeddingProviderBatch,
    EmbeddingProviderFailure,
    EmbeddingProviderFailureCode,
    EmbeddingProviderInput,
    EmbeddingProviderUsage,
    GeminiEmbeddingEvaluationProvider,
)
from careerops.evaluation.run_embedding_retrieval_v2 import create_provider, run


class FailSecondBatchProvider:
    def __init__(self) -> None:
        self.call_sizes: list[int] = []

    @property
    def model_name(self) -> str:
        return "test-embedding-model"

    async def embed_batch(
        self,
        inputs: tuple[EmbeddingProviderInput, ...],
    ) -> EmbeddingProviderBatch:
        self.call_sizes.append(len(inputs))
        if len(self.call_sizes) == 2:
            raise EmbeddingProviderFailure(
                EmbeddingProviderFailureCode.RATE_LIMITED,
                attempts=1,
                status_code=429,
            )
        return constant_batch(len(inputs), self.model_name)


class RecordingProvider:
    def __init__(self) -> None:
        self.call_sizes: list[int] = []

    @property
    def model_name(self) -> str:
        return "test-embedding-model"

    async def embed_batch(
        self,
        inputs: tuple[EmbeddingProviderInput, ...],
    ) -> EmbeddingProviderBatch:
        self.call_sizes.append(len(inputs))
        return constant_batch(len(inputs), self.model_name)


def constant_batch(count: int, model_name: str) -> EmbeddingProviderBatch:
    vector = (1.0,) * 1536
    return EmbeddingProviderBatch(
        model_name=model_name,
        vectors=(vector,) * count,
        usage=EmbeddingProviderUsage(None, None),
        request_attempt_count=1,
    )


def evaluation_paths() -> tuple[Path, Path, Path, Path]:
    base = Path("evals/evidence_retrieval_v2")
    return (
        base / "experiences.json",
        base / "development_queries.json",
        base / "review_manifest.json",
        Path("docs/metrics/2026-09-21-lexical-retrieval-v2-development.json"),
    )


def test_input_plan_is_development_only_versioned_and_label_free() -> None:
    experiences_path, queries_path, _, _ = evaluation_paths()
    corpus, _ = load_corpus(experiences_path)
    queries, _ = load_query_set(queries_path, corpus)

    plan = build_input_plan(corpus, queries)

    assert len(plan.inputs) == 80
    assert len({item.input_sha256 for item in plan.inputs}) == 80
    assert plan.inputs[0].input_version == DOCUMENT_INPUT_VERSION
    assert plan.inputs[-1].input_version == QUERY_INPUT_VERSION
    assert render_document_input(corpus.profiles[0].experiences[0]).startswith("title: ")
    query_text = render_query_input(queries.queries[0])
    assert queries.queries[0].requirement.text in query_text
    assert queries.queries[0].query_id not in query_text
    assert "labels" not in query_text

    sealed = queries.model_copy(update={"split": RetrievalSplit.HOLDOUT})
    with pytest.raises(RuntimeError, match="sealed"):
        build_input_plan(corpus, sealed)


def test_cosine_is_rounded_and_vector_validation_is_strict() -> None:
    unit = (1.0,) + (0.0,) * 1535
    close = (0.5, 0.5) + (0.0,) * 1534

    assert cosine_similarity(unit, unit) == 1.0
    assert cosine_similarity(unit, close) == 0.707106781187
    with pytest.raises(ValueError, match="1536"):
        validate_vector((1.0,))
    with pytest.raises(ValueError, match="non-finite"):
        validate_vector((float("nan"),) * 1536)
    with pytest.raises(ValueError, match="zero norm"):
        validate_vector((0.0,) * 1536)


@pytest.mark.parametrize(
    ("vector", "expected"),
    [
        ((1.0,), EmbeddingProviderFailureCode.DIMENSION_INVALID),
        ((float("inf"),) * 1536, EmbeddingProviderFailureCode.VECTOR_INVALID),
        ((0.0,) * 1536, EmbeddingProviderFailureCode.VECTOR_INVALID),
    ],
)
def test_provider_output_validation_has_stable_failure_codes(
    vector: tuple[float, ...],
    expected: EmbeddingProviderFailureCode,
) -> None:
    batch = EmbeddingProviderBatch(
        model_name="model",
        vectors=(vector,),
        usage=EmbeddingProviderUsage(None, None),
        request_attempt_count=1,
    )

    with pytest.raises(EmbeddingProviderFailure) as captured:
        validate_batch(batch, 1, "model")

    assert captured.value.code is expected


def test_negative_accuracy_requires_full_abstention() -> None:
    experiences_path, queries_path, _, _ = evaluation_paths()
    corpus, _ = load_corpus(experiences_path)
    queries, _ = load_query_set(queries_path, corpus)
    negative = next(query for query in queries.queries if not query.labels)
    result = score_query(negative, [])

    assert result.no_relevant_returned_at_5 is True

    experience_id = corpus.profiles[0].experiences[0].id
    noisy = score_query(
        negative,
        [
            EmbeddingRankedExperience(
                experience_id=experience_id,
                rank=1,
                score=0.5,
                relevant=False,
                lexical_score=None,
                vector_cosine=0.5,
            )
        ],
    )
    assert noisy.no_relevant_returned_at_5 is False


@pytest.mark.asyncio
async def test_fake_run_reuses_frozen_lexical_baseline_and_never_reads_holdout(
    tmp_path: Path,
) -> None:
    experiences_path, queries_path, manifest_path, baseline_path = evaluation_paths()
    cache_path = tmp_path / "cache.json.gz"
    output_path = tmp_path / "comparison.json"

    report = await run(
        experiences_path=experiences_path,
        queries_path=queries_path,
        review_manifest_path=manifest_path,
        lexical_baseline_path=baseline_path,
        cache_path=cache_path,
        output_path=output_path,
        git_revision="test-revision",
        provider_name="fake",
        provider=FakeEmbeddingEvaluationProvider(),
    )

    cache = load_cache(cache_path)
    assert output_path.exists()
    assert cache.status == "complete"
    assert cache.unique_input_count == 80
    assert cache.holdout_input_count == 0
    assert report.lexical.summary.recall_at_5 == pytest.approx(0.833333333333333)
    assert report.requested_input_count == 80
    assert report.provider_request_attempt_count == 2
    assert [item.unique_input_count for item in report.usage] == [40, 40]
    assert report.holdout_input_count == 0
    assert report.vector.vector_threshold is not None
    assert report.hybrid.lexical_weight in {0.25, 0.5, 0.75}

    with pytest.raises(FileExistsError, match="overwrite"):
        await run(
            experiences_path=experiences_path,
            queries_path=queries_path,
            review_manifest_path=manifest_path,
            lexical_baseline_path=baseline_path,
            cache_path=cache_path,
            output_path=output_path,
            git_revision="test-revision",
            provider_name="fake",
            provider=FakeEmbeddingEvaluationProvider(),
        )


@pytest.mark.asyncio
async def test_partial_batch_failure_preserves_only_validated_cache_for_resume(
    tmp_path: Path,
) -> None:
    experiences_path, queries_path, _, _ = evaluation_paths()
    corpus, corpus_hash = load_corpus(experiences_path)
    queries, query_hash = load_query_set(queries_path, corpus)
    plan = build_input_plan(corpus, queries)
    cache_path = tmp_path / "resume-cache.json.gz"
    failing = FailSecondBatchProvider()
    cache = new_cache(
        git_revision="test",
        provider="test",
        model_name=failing.model_name,
        corpus_sha256=corpus_hash,
        development_queries_sha256=query_hash,
        input_plan=plan,
    )

    with pytest.raises(EmbeddingProviderFailure) as captured:
        await fill_cache(cache, plan, failing, cache_path)

    partial = load_cache(cache_path)
    assert captured.value.code is EmbeddingProviderFailureCode.RATE_LIMITED
    assert partial.status == "incomplete"
    assert partial.last_error_code == EmbeddingProviderFailureCode.RATE_LIMITED.value
    assert len(partial.embeddings) == 40
    assert failing.call_sizes == [40, 40]

    resumed_provider = RecordingProvider()
    completed = await fill_cache(partial, plan, resumed_provider, cache_path)

    assert completed.status == "complete"
    assert completed.last_error_code is None
    assert len(completed.embeddings) == 80
    assert resumed_provider.call_sizes == [40]


def test_gemini_provider_is_disabled_without_explicit_opt_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CAREEROPS_RUN_EMBEDDING_EVAL", raising=False)
    monkeypatch.delenv("CAREEROPS_GEMINI_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="CAREEROPS_RUN_EMBEDDING_EVAL"):
        create_provider("gemini")


def test_gemini_provider_reads_key_from_ignored_dotenv(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CAREEROPS_RUN_EMBEDDING_EVAL", "1")
    monkeypatch.delenv("CAREEROPS_GEMINI_API_KEY", raising=False)
    (tmp_path / ".env").write_text(
        "CAREEROPS_GEMINI_API_KEY=test-only-secret\n",
        encoding="utf-8",
    )

    provider = create_provider("gemini")

    assert isinstance(provider, GeminiEmbeddingEvaluationProvider)
    assert provider.model_name == "gemini-embedding-2"
