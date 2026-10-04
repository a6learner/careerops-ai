import subprocess
from hashlib import sha256
from pathlib import Path

import pytest

from careerops.evaluation.embedding_holdout_v2 import (
    EXPECTED_DOCUMENT_VECTOR_COUNT,
    FROZEN_DEVELOPMENT_CACHE_SHA256,
    FROZEN_DEVELOPMENT_REPORT_SHA256,
    FROZEN_HYBRID_ALPHA,
    FROZEN_HYBRID_THRESHOLD,
    FROZEN_VECTOR_THRESHOLD,
    FrozenDevelopmentEvidence,
    evaluate_frozen_holdout,
    fill_holdout_cache,
    load_frozen_development_evidence,
    load_holdout_cache,
    new_holdout_cache,
    normalized_text_sha256,
    validate_frozen_development_commit,
    validate_frozen_manifest_development_hash,
    validate_holdout_cache,
)
from careerops.evaluation.embedding_retrieval_v2 import (
    DOCUMENT_INPUT_VERSION,
    EmbeddingRole,
    FakeEmbeddingEvaluationProvider,
    build_holdout_query_plan,
    make_input,
    render_document_input,
)
from careerops.evaluation.evidence_retrieval_v2 import (
    RetrievalSplit,
    RetrievalV2Corpus,
    RetrievalV2QuerySet,
    load_corpus,
    load_query_set,
)
from careerops.evaluation.gemini_embedding_provider import (
    EmbeddingProviderBatch,
    EmbeddingProviderFailure,
    EmbeddingProviderFailureCode,
    EmbeddingProviderInput,
)
from careerops.evaluation.run_embedding_holdout_v2 import (
    create_holdout_provider,
    run,
)


def development_fixture() -> tuple[RetrievalV2Corpus, RetrievalV2QuerySet, str]:
    corpus, corpus_hash = load_corpus(Path("evals/evidence_retrieval_v2/experiences.json"))
    development, _ = load_query_set(
        Path("evals/evidence_retrieval_v2/development_queries.json"),
        corpus,
    )
    holdout_shaped = development.model_copy(
        update={
            "name": "test-holdout-derived-from-development",
            "split": RetrievalSplit.HOLDOUT,
            "queries": development.queries[:2],
        }
    )
    return corpus, holdout_shaped, corpus_hash


class RateLimitedProvider:
    @property
    def model_name(self) -> str:
        return "test-holdout-model"

    async def embed_batch(
        self,
        inputs: tuple[EmbeddingProviderInput, ...],
    ) -> EmbeddingProviderBatch:
        del inputs
        raise EmbeddingProviderFailure(
            EmbeddingProviderFailureCode.RATE_LIMITED,
            attempts=1,
            status_code=429,
        )


class RecordingFakeProvider(FakeEmbeddingEvaluationProvider):
    def __init__(self) -> None:
        super().__init__()
        self.call_sizes: list[int] = []

    async def embed_batch(
        self,
        inputs: tuple[EmbeddingProviderInput, ...],
    ) -> EmbeddingProviderBatch:
        self.call_sizes.append(len(inputs))
        return await super().embed_batch(inputs)


def test_holdout_plan_contains_only_queries_and_has_frozen_document_hashes() -> None:
    corpus, query_set, _ = development_fixture()

    plan = build_holdout_query_plan(corpus, query_set)

    assert len(plan.inputs) == 2
    assert all(item.role is EmbeddingRole.QUERY for item in plan.inputs)
    assert len(plan.query_hashes) == 2
    assert len(plan.document_hashes) == EXPECTED_DOCUMENT_VECTOR_COUNT

    development = query_set.model_copy(update={"split": RetrievalSplit.DEVELOPMENT})
    with pytest.raises(RuntimeError, match="requires the frozen holdout"):
        build_holdout_query_plan(corpus, development)

    full_development, _ = load_query_set(
        Path("evals/evidence_retrieval_v2/development_queries.json"),
        corpus,
    )
    over_budget = full_development.model_copy(
        update={"split": RetrievalSplit.HOLDOUT, "queries": full_development.queries[:21]}
    )
    with pytest.raises(ValueError, match="exceeds 20"):
        build_holdout_query_plan(corpus, over_budget)


def test_frozen_development_evidence_matches_committed_artifacts(tmp_path: Path) -> None:
    corpus, query_set, corpus_hash = development_fixture()
    plan = build_holdout_query_plan(corpus, query_set)
    report_path = Path(
        "docs/metrics/2026-10-01-gemini-embedding-2-development-comparison.json"
    )
    cache_path = Path(
        "docs/metrics/2026-10-01-gemini-embedding-2-development-vectors.json.gz"
    )

    frozen = load_frozen_development_evidence(
        report_path=report_path,
        cache_path=cache_path,
        corpus_sha256=corpus_hash,
        input_plan=plan,
    )

    assert len(frozen.document_vectors) == EXPECTED_DOCUMENT_VECTOR_COUNT
    assert frozen.report.vector.vector_threshold == FROZEN_VECTOR_THRESHOLD
    assert frozen.report.hybrid.vector_threshold == FROZEN_HYBRID_THRESHOLD
    assert frozen.report.hybrid.lexical_weight == FROZEN_HYBRID_ALPHA
    assert frozen.report.cache_sha256 == FROZEN_DEVELOPMENT_CACHE_SHA256
    assert normalized_text_sha256(report_path) == FROZEN_DEVELOPMENT_REPORT_SHA256

    changed = tmp_path / "changed-report.json"
    changed.write_bytes(report_path.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="not the frozen P1-3a artifact"):
        load_frozen_development_evidence(
            report_path=changed,
            cache_path=cache_path,
            corpus_sha256=corpus_hash,
            input_plan=plan,
        )


def test_frozen_commit_and_manifest_hash_are_required(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing_commit(*args: object, **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        del args, kwargs
        return subprocess.CompletedProcess(args=[], returncode=1)

    monkeypatch.setattr(
        "careerops.evaluation.embedding_holdout_v2.subprocess.run",
        missing_commit,
    )
    with pytest.raises(ValueError, match="not an ancestor"):
        validate_frozen_development_commit()

    with pytest.raises(ValueError, match="development-query hash"):
        validate_frozen_manifest_development_hash("0" * 64)


@pytest.mark.asyncio
async def test_fake_provider_fills_one_query_only_cache_and_reuses_it(tmp_path: Path) -> None:
    corpus, query_set, corpus_hash = development_fixture()
    plan = build_holdout_query_plan(corpus, query_set)
    provider = RecordingFakeProvider()
    cache_path = tmp_path / "holdout-query-cache.json.gz"
    cache = new_holdout_cache(
        git_revision="test",
        provider="fake",
        model_name=provider.model_name,
        corpus_sha256=corpus_hash,
        holdout_queries_sha256="a" * 64,
        input_plan=plan,
    )

    completed = await fill_holdout_cache(cache, plan, provider, cache_path)
    validate_holdout_cache(
        completed,
        provider="fake",
        model_name=provider.model_name,
        corpus_sha256=corpus_hash,
        holdout_queries_sha256="a" * 64,
        input_plan=plan,
    )

    assert completed.status == "complete"
    assert completed.holdout_input_count == 2
    assert len(completed.embeddings) == 2
    assert len(completed.usage) == 1
    assert completed.usage[0].role is EmbeddingRole.QUERY
    assert completed.usage[0].unique_input_count == 2
    assert provider.call_sizes == [2]

    loaded = load_holdout_cache(cache_path)
    original_hash = sha256(cache_path.read_bytes()).hexdigest()
    reused = await fill_holdout_cache(loaded, plan, provider, cache_path)
    assert len(reused.usage) == 1
    assert provider.call_sizes == [2]
    assert sha256(cache_path.read_bytes()).hexdigest() == original_hash


@pytest.mark.asyncio
async def test_holdout_provider_failure_saves_incomplete_cache(tmp_path: Path) -> None:
    corpus, query_set, corpus_hash = development_fixture()
    plan = build_holdout_query_plan(corpus, query_set)
    provider = RateLimitedProvider()
    cache_path = tmp_path / "failed-cache.json.gz"
    cache = new_holdout_cache(
        git_revision="test",
        provider="test",
        model_name=provider.model_name,
        corpus_sha256=corpus_hash,
        holdout_queries_sha256="c" * 64,
        input_plan=plan,
    )

    with pytest.raises(EmbeddingProviderFailure) as captured:
        await fill_holdout_cache(cache, plan, provider, cache_path)

    saved = load_holdout_cache(cache_path)
    assert captured.value.code is EmbeddingProviderFailureCode.RATE_LIMITED
    assert saved.status == "incomplete"
    assert saved.embeddings == []
    assert saved.usage == []
    assert saved.last_error_code == EmbeddingProviderFailureCode.RATE_LIMITED.value


@pytest.mark.asyncio
async def test_fixed_holdout_evaluation_uses_frozen_parameters(tmp_path: Path) -> None:
    corpus, query_set, corpus_hash = development_fixture()
    plan = build_holdout_query_plan(corpus, query_set)
    provider = FakeEmbeddingEvaluationProvider()
    document_inputs = []
    for profile in corpus.profiles:
        for experience in profile.experiences:
            item = make_input(
                input_id=f"document:{experience.id}",
                role=EmbeddingRole.DOCUMENT,
                input_version=DOCUMENT_INPUT_VERSION,
                rendered_text=render_document_input(experience),
            )
            document_inputs.append(
                EmbeddingProviderInput(item.input_sha256, item.rendered_text)
            )
    document_batch = await provider.embed_batch(tuple(document_inputs))
    document_vectors = {
        item.input_sha256: vector
        for item, vector in zip(document_inputs, document_batch.vectors, strict=True)
    }
    real_frozen = load_frozen_development_evidence(
        report_path=Path(
            "docs/metrics/2026-10-01-gemini-embedding-2-development-comparison.json"
        ),
        cache_path=Path(
            "docs/metrics/2026-10-01-gemini-embedding-2-development-vectors.json.gz"
        ),
        corpus_sha256=corpus_hash,
        input_plan=plan,
    )
    frozen = FrozenDevelopmentEvidence(
        report=real_frozen.report,
        cache=real_frozen.cache,
        document_vectors=document_vectors,
    )
    cache_path = tmp_path / "query-cache.json.gz"
    cache = new_holdout_cache(
        git_revision="test",
        provider="fake",
        model_name=provider.model_name,
        corpus_sha256=corpus_hash,
        holdout_queries_sha256="b" * 64,
        input_plan=plan,
    )
    cache = await fill_holdout_cache(cache, plan, provider, cache_path)

    _, vector, hybrid = evaluate_frozen_holdout(
        corpus=corpus,
        query_set=query_set,
        input_plan=plan,
        frozen=frozen,
        holdout_cache=cache,
    )

    assert vector.threshold == FROZEN_VECTOR_THRESHOLD
    assert vector.alpha is None
    assert hybrid.threshold == FROZEN_HYBRID_THRESHOLD
    assert hybrid.alpha == FROZEN_HYBRID_ALPHA


def test_holdout_provider_requires_distinct_explicit_opt_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CAREEROPS_RUN_EMBEDDING_HOLDOUT", raising=False)
    monkeypatch.setenv("CAREEROPS_RUN_EMBEDDING_EVAL", "1")

    with pytest.raises(RuntimeError, match="CAREEROPS_RUN_EMBEDDING_HOLDOUT"):
        create_holdout_provider()


@pytest.mark.asyncio
async def test_holdout_run_refuses_existing_output_before_reading_inputs(
    tmp_path: Path,
) -> None:
    output = tmp_path / "existing.json"
    output.write_text("do not overwrite", encoding="utf-8")

    with pytest.raises(FileExistsError, match="overwrite holdout evidence"):
        await run(
            experiences_path=tmp_path / "missing-experiences.json",
            holdout_queries_path=tmp_path / "missing-holdout.json",
            review_manifest_path=tmp_path / "missing-manifest.json",
            frozen_development_report_path=tmp_path / "missing-development.json",
            frozen_development_cache_path=tmp_path / "missing-development.json.gz",
            cache_path=tmp_path / "holdout-cache.json.gz",
            output_path=output,
            git_revision="test",
            provider=FakeEmbeddingEvaluationProvider(),
        )
