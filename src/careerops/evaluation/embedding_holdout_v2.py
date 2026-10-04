from __future__ import annotations

import gzip
import hashlib
import os
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from careerops.domain.embeddings import EMBEDDING_DIMENSIONS
from careerops.evaluation.embedding_retrieval_v2 import (
    DOCUMENT_INPUT_VERSION,
    GEMINI_EMBEDDING_MODEL,
    HYBRID_RETRIEVER_VERSION,
    QUERY_INPUT_VERSION,
    VECTOR_RETRIEVER_VERSION,
    CachedEmbedding,
    EmbeddingBatchUsageRecord,
    EmbeddingComparisonReport,
    EmbeddingEvaluationCache,
    EmbeddingEvaluationProvider,
    EmbeddingQueryResult,
    EmbeddingRole,
    InputPlan,
    RetrievalMethodReport,
    SelectedMethod,
    evaluate_fixed_comparison,
    file_sha256,
    load_cache,
    validate_batch,
    validate_vector,
)
from careerops.evaluation.evidence_retrieval_v2 import (
    RetrievalV2Corpus,
    RetrievalV2QuerySet,
    RetrievalV2Summary,
)
from careerops.evaluation.gemini_embedding_provider import (
    EmbeddingProviderFailure,
    EmbeddingProviderInput,
)

FROZEN_DEVELOPMENT_COMMIT = "0c6d9cd139ae05efa28aa038dc26fae912807d66"
FROZEN_DEVELOPMENT_REPORT_SHA256 = (
    "19aa221b03b6795571407b680c5cadcaa5b1be80a6307253801f4dcee33f40b1"
)
FROZEN_DEVELOPMENT_CACHE_SHA256 = (
    "8b07d9f80dc40d0fa744bab038034f39e4f6a4f9a69f2fe5b44f6419d82ad7b8"
)
FROZEN_CORPUS_SHA256 = "139729a73aa99dc6cd6a9199d8c1b44e901e3d4cb1171ef4abd4990071fd1d0f"
FROZEN_DEVELOPMENT_QUERIES_SHA256 = (
    "ee78882ee3c627d4de1bc1e33e936b5ab4f3a4e615fc88b0002baf1c9c1a0d0e"
)
FROZEN_VECTOR_THRESHOLD = 0.65
FROZEN_HYBRID_THRESHOLD = 0.65
FROZEN_HYBRID_ALPHA = 0.5
EXPECTED_DOCUMENT_VECTOR_COUNT = 40
EXPECTED_HOLDOUT_QUERY_COUNT = 20
HOLDOUT_SUCCESS_POLICY = (
    "Require Recall@5, negative accuracy@5, Hit@5, and MRR@5 no worse than "
    "holdout lexical, with at least one strict improvement."
)


class HoldoutEmbeddingCache(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["incomplete", "complete"]
    created_at: datetime
    updated_at: datetime
    git_revision: str
    provider: str
    model_name: str
    output_dimensionality: int
    frozen_development_commit: str
    frozen_development_report_sha256: str
    frozen_development_cache_sha256: str
    corpus_sha256: str
    holdout_queries_sha256: str
    query_input_version: str
    requested_input_count: int
    unique_input_count: int
    holdout_input_count: int
    embeddings: list[CachedEmbedding]
    usage: list[EmbeddingBatchUsageRecord]
    last_error_code: str | None


class HoldoutMethodReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    retriever_version: str
    vector_threshold: float | None
    lexical_weight: float | None
    holdout_success: bool | None
    summary: RetrievalV2Summary
    queries: list[EmbeddingQueryResult]


class EmbeddingHoldoutReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    created_at: datetime
    git_revision: str
    frozen_development_commit: str
    frozen_development_report_sha256: str
    frozen_development_cache_sha256: str
    corpus_sha256: str
    holdout_queries_sha256: str
    query_cache_sha256: str
    provider: str
    model_name: str
    output_dimensionality: int
    query_input_version: str
    document_input_version: str
    cache_created_at: datetime
    cache_completed_at: datetime
    reused_document_input_count: int
    requested_input_count: int
    unique_input_count: int
    holdout_input_count: int
    provider_request_attempt_count: int
    usage: list[EmbeddingBatchUsageRecord]
    pre_registered_success_policy: str
    lexical: HoldoutMethodReport
    vector: HoldoutMethodReport
    hybrid: HoldoutMethodReport
    limitations: list[str]


@dataclass(frozen=True)
class FrozenDevelopmentEvidence:
    report: EmbeddingComparisonReport
    cache: EmbeddingEvaluationCache
    document_vectors: dict[str, tuple[float, ...]]


def load_frozen_development_evidence(
    *,
    report_path: Path,
    cache_path: Path,
    corpus_sha256: str,
    input_plan: InputPlan,
) -> FrozenDevelopmentEvidence:
    report_hash = normalized_text_sha256(report_path)
    cache_hash = file_sha256(cache_path)
    if report_hash != FROZEN_DEVELOPMENT_REPORT_SHA256:
        raise ValueError("Development comparison report is not the frozen P1-3a artifact.")
    if cache_hash != FROZEN_DEVELOPMENT_CACHE_SHA256:
        raise ValueError("Development vector cache is not the frozen P1-3a artifact.")

    report = EmbeddingComparisonReport.model_validate_json(report_path.read_bytes())
    cache = load_cache(cache_path)
    report_identity = (
        report.corpus_sha256,
        report.development_queries_sha256,
        report.cache_sha256,
        report.provider,
        report.model_name,
        report.output_dimensionality,
        report.query_input_version,
        report.document_input_version,
        report.unique_input_count,
        report.holdout_input_count,
        report.vector.vector_threshold,
        report.hybrid.vector_threshold,
        report.hybrid.lexical_weight,
        report.vector.development_gate_passed,
        report.hybrid.development_gate_passed,
    )
    expected_report_identity = (
        FROZEN_CORPUS_SHA256,
        FROZEN_DEVELOPMENT_QUERIES_SHA256,
        FROZEN_DEVELOPMENT_CACHE_SHA256,
        "gemini",
        GEMINI_EMBEDDING_MODEL,
        EMBEDDING_DIMENSIONS,
        QUERY_INPUT_VERSION,
        DOCUMENT_INPUT_VERSION,
        80,
        0,
        FROZEN_VECTOR_THRESHOLD,
        FROZEN_HYBRID_THRESHOLD,
        FROZEN_HYBRID_ALPHA,
        True,
        True,
    )
    if report_identity != expected_report_identity or corpus_sha256 != FROZEN_CORPUS_SHA256:
        raise ValueError("Frozen development report identity or parameters changed.")

    cache_identity = (
        cache.status,
        cache.provider,
        cache.model_name,
        cache.output_dimensionality,
        cache.corpus_sha256,
        cache.development_queries_sha256,
        cache.query_input_version,
        cache.document_input_version,
        cache.unique_input_count,
        cache.holdout_input_count,
    )
    expected_cache_identity = (
        "complete",
        "gemini",
        GEMINI_EMBEDDING_MODEL,
        EMBEDDING_DIMENSIONS,
        FROZEN_CORPUS_SHA256,
        FROZEN_DEVELOPMENT_QUERIES_SHA256,
        QUERY_INPUT_VERSION,
        DOCUMENT_INPUT_VERSION,
        80,
        0,
    )
    if cache_identity != expected_cache_identity:
        raise ValueError("Frozen development cache identity changed.")

    document_embeddings = [
        item for item in cache.embeddings if item.role is EmbeddingRole.DOCUMENT
    ]
    expected_hashes = set(input_plan.document_hashes.values())
    actual_hashes = {item.input_sha256 for item in document_embeddings}
    if (
        len(document_embeddings) != EXPECTED_DOCUMENT_VECTOR_COUNT
        or len(actual_hashes) != EXPECTED_DOCUMENT_VECTOR_COUNT
        or actual_hashes != expected_hashes
    ):
        raise ValueError("Frozen development cache document vectors do not match the corpus.")
    document_vectors: dict[str, tuple[float, ...]] = {}
    for item in document_embeddings:
        vector = tuple(item.vector)
        validate_vector(vector)
        document_vectors[item.input_sha256] = vector
    return FrozenDevelopmentEvidence(report, cache, document_vectors)


def validate_frozen_development_commit() -> None:
    try:
        result = subprocess.run(
            ["git", "merge-base", "--is-ancestor", FROZEN_DEVELOPMENT_COMMIT, "HEAD"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError as exc:
        raise RuntimeError("Unable to verify the frozen P1-3a commit in Git history.") from exc
    if result.returncode != 0:
        raise ValueError("The frozen P1-3a commit is not an ancestor of the current HEAD.")


def validate_frozen_manifest_development_hash(development_queries_sha256: str) -> None:
    if development_queries_sha256 != FROZEN_DEVELOPMENT_QUERIES_SHA256:
        raise ValueError("Review manifest development-query hash is not frozen P1-3a data.")


def new_holdout_cache(
    *,
    git_revision: str,
    provider: str,
    model_name: str,
    corpus_sha256: str,
    holdout_queries_sha256: str,
    input_plan: InputPlan,
) -> HoldoutEmbeddingCache:
    now = datetime.now(UTC)
    return HoldoutEmbeddingCache(
        status="incomplete",
        created_at=now,
        updated_at=now,
        git_revision=git_revision,
        provider=provider,
        model_name=model_name,
        output_dimensionality=EMBEDDING_DIMENSIONS,
        frozen_development_commit=FROZEN_DEVELOPMENT_COMMIT,
        frozen_development_report_sha256=FROZEN_DEVELOPMENT_REPORT_SHA256,
        frozen_development_cache_sha256=FROZEN_DEVELOPMENT_CACHE_SHA256,
        corpus_sha256=corpus_sha256,
        holdout_queries_sha256=holdout_queries_sha256,
        query_input_version=QUERY_INPUT_VERSION,
        requested_input_count=len(input_plan.inputs),
        unique_input_count=len({item.input_sha256 for item in input_plan.inputs}),
        holdout_input_count=len(input_plan.inputs),
        embeddings=[],
        usage=[],
        last_error_code=None,
    )


def validate_holdout_cache(
    cache: HoldoutEmbeddingCache,
    *,
    provider: str,
    model_name: str,
    corpus_sha256: str,
    holdout_queries_sha256: str,
    input_plan: InputPlan,
) -> None:
    expected_count = len({item.input_sha256 for item in input_plan.inputs})
    expected = (
        provider,
        model_name,
        EMBEDDING_DIMENSIONS,
        FROZEN_DEVELOPMENT_COMMIT,
        FROZEN_DEVELOPMENT_REPORT_SHA256,
        FROZEN_DEVELOPMENT_CACHE_SHA256,
        corpus_sha256,
        holdout_queries_sha256,
        QUERY_INPUT_VERSION,
        expected_count,
        expected_count,
    )
    actual = (
        cache.provider,
        cache.model_name,
        cache.output_dimensionality,
        cache.frozen_development_commit,
        cache.frozen_development_report_sha256,
        cache.frozen_development_cache_sha256,
        cache.corpus_sha256,
        cache.holdout_queries_sha256,
        cache.query_input_version,
        cache.unique_input_count,
        cache.holdout_input_count,
    )
    if actual != expected:
        raise ValueError("Holdout query cache identity does not match this frozen run.")
    expected_hashes = {item.input_sha256 for item in input_plan.inputs}
    cached_hashes = [item.input_sha256 for item in cache.embeddings]
    if (
        len(cached_hashes) != len(set(cached_hashes))
        or set(cached_hashes) - expected_hashes
        or any(item.role is not EmbeddingRole.QUERY for item in cache.embeddings)
    ):
        raise ValueError("Holdout cache contains duplicate, unknown, or non-query inputs.")
    if len(cache.usage) > 1 or any(
        item.role is not EmbeddingRole.QUERY for item in cache.usage
    ):
        raise ValueError("Holdout cache usage must describe at most one query batch.")
    for item in cache.embeddings:
        validate_vector(tuple(item.vector))


async def fill_holdout_cache(
    cache: HoldoutEmbeddingCache,
    input_plan: InputPlan,
    provider: EmbeddingEvaluationProvider,
    cache_path: Path,
) -> HoldoutEmbeddingCache:
    cached_hashes = {item.input_sha256 for item in cache.embeddings}
    unique = {
        item.input_sha256: item
        for item in input_plan.inputs
        if item.input_sha256 not in cached_hashes
    }
    missing = tuple(unique.values())
    if not missing and cache.status == "complete":
        return cache
    if missing:
        provider_inputs = tuple(
            EmbeddingProviderInput(item.input_sha256, item.rendered_text) for item in missing
        )
        try:
            batch = await provider.embed_batch(provider_inputs)
            validate_batch(batch, len(missing), provider.model_name)
        except EmbeddingProviderFailure as exc:
            cache.last_error_code = exc.code.value
            cache.updated_at = datetime.now(UTC)
            save_holdout_cache(cache_path, cache)
            raise
        cache.embeddings.extend(
            CachedEmbedding(
                input_sha256=item.input_sha256,
                role=EmbeddingRole.QUERY,
                input_version=QUERY_INPUT_VERSION,
                vector=list(vector),
            )
            for item, vector in zip(missing, batch.vectors, strict=True)
        )
        cache.usage.append(
            EmbeddingBatchUsageRecord(
                role=EmbeddingRole.QUERY,
                unique_input_count=len(missing),
                request_attempt_count=batch.request_attempt_count,
                token_count=batch.usage.token_count,
                billable_character_count=batch.usage.billable_character_count,
            )
        )
        cache.updated_at = datetime.now(UTC)
        cache.last_error_code = None
        save_holdout_cache(cache_path, cache)
    expected_hashes = {item.input_sha256 for item in input_plan.inputs}
    if {item.input_sha256 for item in cache.embeddings} != expected_hashes:
        raise ValueError("Holdout query cache is incomplete after provider execution.")
    cache.status = "complete"
    cache.updated_at = datetime.now(UTC)
    save_holdout_cache(cache_path, cache)
    return cache


def evaluate_frozen_holdout(
    *,
    corpus: RetrievalV2Corpus,
    query_set: RetrievalV2QuerySet,
    input_plan: InputPlan,
    frozen: FrozenDevelopmentEvidence,
    holdout_cache: HoldoutEmbeddingCache,
) -> tuple[RetrievalMethodReport, SelectedMethod, SelectedMethod]:
    if holdout_cache.status != "complete":
        raise ValueError("A complete holdout query cache is required for evaluation.")
    vectors = dict(frozen.document_vectors)
    for item in holdout_cache.embeddings:
        if item.input_sha256 in vectors:
            raise ValueError("Holdout query hash collides with a frozen document hash.")
        vectors[item.input_sha256] = tuple(item.vector)
    return evaluate_fixed_comparison(
        corpus=corpus,
        query_set=query_set,
        input_plan=input_plan,
        vectors=vectors,
        vector_threshold=FROZEN_VECTOR_THRESHOLD,
        hybrid_threshold=FROZEN_HYBRID_THRESHOLD,
        hybrid_alpha=FROZEN_HYBRID_ALPHA,
    )


def load_holdout_cache(path: Path) -> HoldoutEmbeddingCache:
    with gzip.open(path, "rt", encoding="utf-8") as file:
        return HoldoutEmbeddingCache.model_validate_json(file.read())


def normalized_text_sha256(path: Path) -> str:
    content = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(content).hexdigest()


def save_holdout_cache(path: Path, cache: HoldoutEmbeddingCache) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    with gzip.open(temporary, "wt", encoding="utf-8") as file:
        file.write(cache.model_dump_json())
    os.replace(temporary, path)


def holdout_method_report(
    *,
    version: str,
    method: SelectedMethod,
) -> HoldoutMethodReport:
    return HoldoutMethodReport(
        retriever_version=version,
        vector_threshold=method.threshold,
        lexical_weight=method.alpha,
        holdout_success=method.gate_passed,
        summary=method.summary,
        queries=method.results,
    )


def lexical_holdout_report(method: RetrievalMethodReport) -> HoldoutMethodReport:
    return HoldoutMethodReport(
        retriever_version=method.retriever_version,
        vector_threshold=None,
        lexical_weight=None,
        holdout_success=None,
        summary=method.summary,
        queries=method.queries,
    )


def vector_holdout_report(method: SelectedMethod) -> HoldoutMethodReport:
    return holdout_method_report(version=VECTOR_RETRIEVER_VERSION, method=method)


def hybrid_holdout_report(method: SelectedMethod) -> HoldoutMethodReport:
    return holdout_method_report(version=HYBRID_RETRIEVER_VERSION, method=method)
