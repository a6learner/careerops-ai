from __future__ import annotations

import gzip
import hashlib
import json
import math
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Literal, Protocol, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from careerops.adapters.fake_embedding_provider import FakeEmbeddingProvider
from careerops.domain.embeddings import EMBEDDING_DIMENSIONS, EmbeddingOutput
from careerops.domain.evidence_retrieval import (
    DEFAULT_CANDIDATE_LIMIT,
    retrieve_evidence_candidates,
)
from careerops.evaluation.evidence_retrieval import (
    RetrievalEvalExperience,
    to_experience_record,
    to_requirement_record,
)
from careerops.evaluation.evidence_retrieval_v2 import (
    RetrievalSplit,
    RetrievalV2Corpus,
    RetrievalV2Query,
    RetrievalV2QuerySet,
    RetrievalV2Summary,
    SupportLevel,
)
from careerops.evaluation.gemini_embedding_provider import (
    EmbeddingProviderBatch,
    EmbeddingProviderFailure,
    EmbeddingProviderFailureCode,
    EmbeddingProviderInput,
    EmbeddingProviderUsage,
)

GEMINI_EMBEDDING_MODEL = "gemini-embedding-2"
QUERY_INPUT_VERSION = "gemini-embedding-2-search-query-v1"
DOCUMENT_INPUT_VERSION = "gemini-embedding-2-search-document-v1"
VECTOR_RETRIEVER_VERSION = "gemini-embedding-2-cosine-v1"
HYBRID_RETRIEVER_VERSION = "weighted-rrf-v1"
RRF_K = 60
HYBRID_ALPHAS = (0.25, 0.5, 0.75)
VECTOR_THRESHOLDS = tuple(round(-0.2 + (step * 0.05), 2) for step in range(23))
MAX_LIVE_UNIQUE_INPUTS = 80
MAX_HOLDOUT_QUERY_INPUTS = 20
MetricValue = TypeVar("MetricValue")


class EmbeddingRole(StrEnum):
    DOCUMENT = "document"
    QUERY = "query"


class EmbeddingEvaluationProvider(Protocol):
    @property
    def model_name(self) -> str: ...

    async def embed_batch(
        self,
        inputs: tuple[EmbeddingProviderInput, ...],
    ) -> EmbeddingProviderBatch: ...


class EmbeddingEvalInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    input_id: str
    input_sha256: str = Field(min_length=64, max_length=64)
    role: EmbeddingRole
    input_version: str
    rendered_text: str


class CachedEmbedding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_sha256: str = Field(min_length=64, max_length=64)
    role: EmbeddingRole
    input_version: str
    vector: list[float]


class EmbeddingBatchUsageRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: EmbeddingRole
    unique_input_count: int = Field(ge=0)
    request_attempt_count: int = Field(ge=0)
    token_count: int | None = Field(default=None, ge=0)
    billable_character_count: int | None = Field(default=None, ge=0)


class EmbeddingEvaluationCache(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["incomplete", "complete"]
    created_at: datetime
    updated_at: datetime
    git_revision: str
    provider: str
    model_name: str
    output_dimensionality: int
    corpus_sha256: str
    development_queries_sha256: str
    query_input_version: str
    document_input_version: str
    requested_input_count: int
    unique_input_count: int
    holdout_input_count: int
    embeddings: list[CachedEmbedding]
    usage: list[EmbeddingBatchUsageRecord]
    last_error_code: str | None


class EmbeddingRankedExperience(BaseModel):
    model_config = ConfigDict(extra="forbid")

    experience_id: UUID
    rank: int = Field(ge=1)
    score: float
    relevant: bool
    lexical_score: int | None
    vector_cosine: float | None


class EmbeddingQueryResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query_id: str
    profile_id: str
    description: str
    relevant_experience_ids: list[UUID]
    support_levels: dict[UUID, SupportLevel]
    ranked_experiences: list[EmbeddingRankedExperience]
    returned_candidate_count: int
    recall_at_1: float | None
    recall_at_3: float | None
    recall_at_5: float | None
    precision_at_5: float | None
    hit_at_1: float | None
    hit_at_3: float | None
    hit_at_5: float | None
    reciprocal_rank_at_5: float | None
    no_relevant_returned_at_5: bool | None


class RetrievalMethodReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    retriever_version: str
    vector_threshold: float | None
    lexical_weight: float | None
    development_gate_passed: bool | None
    summary: RetrievalV2Summary
    queries: list[EmbeddingQueryResult]


class EmbeddingComparisonReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    created_at: datetime
    git_revision: str
    corpus_sha256: str
    development_queries_sha256: str
    lexical_baseline_sha256: str
    cache_sha256: str
    provider: str
    model_name: str
    output_dimensionality: int
    query_input_version: str
    document_input_version: str
    cache_created_at: datetime
    cache_completed_at: datetime
    requested_input_count: int
    unique_input_count: int
    holdout_input_count: int
    provider_request_attempt_count: int
    usage: list[EmbeddingBatchUsageRecord]
    selection_policy: str
    vector_threshold_grid: list[float]
    hybrid_alpha_grid: list[float]
    lexical: RetrievalMethodReport
    vector: RetrievalMethodReport
    hybrid: RetrievalMethodReport
    limitations: list[str]


@dataclass(frozen=True)
class InputPlan:
    inputs: tuple[EmbeddingEvalInput, ...]
    document_hashes: dict[UUID, str]
    query_hashes: dict[str, str]


@dataclass(frozen=True)
class SelectedMethod:
    threshold: float
    alpha: float | None
    gate_passed: bool
    results: list[EmbeddingQueryResult]
    summary: RetrievalV2Summary


class FakeEmbeddingEvaluationProvider:
    def __init__(self) -> None:
        self._provider = FakeEmbeddingProvider()

    @property
    def model_name(self) -> str:
        return self._provider.model_name

    async def embed_batch(
        self,
        inputs: tuple[EmbeddingProviderInput, ...],
    ) -> EmbeddingProviderBatch:
        outputs: list[EmbeddingOutput] = []
        for item in inputs:
            outputs.append(await self._provider.embed(item.text))
        return EmbeddingProviderBatch(
            model_name=self.model_name,
            vectors=tuple(output.vector for output in outputs),
            usage=EmbeddingProviderUsage(None, None),
            request_attempt_count=int(bool(inputs)),
        )


def build_input_plan(
    corpus: RetrievalV2Corpus,
    query_set: RetrievalV2QuerySet,
) -> InputPlan:
    if query_set.split is not RetrievalSplit.DEVELOPMENT:
        raise RuntimeError("Holdout embedding evaluation is sealed.")
    inputs: list[EmbeddingEvalInput] = []
    document_hashes: dict[UUID, str] = {}
    query_hashes: dict[str, str] = {}
    for profile in corpus.profiles:
        for experience in profile.experiences:
            rendered = render_document_input(experience)
            item = make_input(
                input_id=f"document:{experience.id}",
                role=EmbeddingRole.DOCUMENT,
                input_version=DOCUMENT_INPUT_VERSION,
                rendered_text=rendered,
            )
            inputs.append(item)
            document_hashes[experience.id] = item.input_sha256
    for query in query_set.queries:
        rendered = render_query_input(query)
        item = make_input(
            input_id=f"query:{query.query_id}",
            role=EmbeddingRole.QUERY,
            input_version=QUERY_INPUT_VERSION,
            rendered_text=rendered,
        )
        inputs.append(item)
        query_hashes[query.query_id] = item.input_sha256
    unique_hashes = {item.input_sha256 for item in inputs}
    if len(unique_hashes) > MAX_LIVE_UNIQUE_INPUTS:
        raise ValueError("Embedding evaluation input budget exceeds 80 unique inputs.")
    return InputPlan(tuple(inputs), document_hashes, query_hashes)


def build_holdout_query_plan(
    corpus: RetrievalV2Corpus,
    query_set: RetrievalV2QuerySet,
) -> InputPlan:
    if query_set.split is not RetrievalSplit.HOLDOUT:
        raise RuntimeError("The holdout runner requires the frozen holdout split.")
    document_hashes: dict[UUID, str] = {}
    for profile in corpus.profiles:
        for experience in profile.experiences:
            item = make_input(
                input_id=f"document:{experience.id}",
                role=EmbeddingRole.DOCUMENT,
                input_version=DOCUMENT_INPUT_VERSION,
                rendered_text=render_document_input(experience),
            )
            document_hashes[experience.id] = item.input_sha256
    inputs: list[EmbeddingEvalInput] = []
    query_hashes: dict[str, str] = {}
    for query in query_set.queries:
        item = make_input(
            input_id=f"query:{query.query_id}",
            role=EmbeddingRole.QUERY,
            input_version=QUERY_INPUT_VERSION,
            rendered_text=render_query_input(query),
        )
        inputs.append(item)
        query_hashes[query.query_id] = item.input_sha256
    unique_hashes = {item.input_sha256 for item in inputs}
    if len(unique_hashes) > MAX_HOLDOUT_QUERY_INPUTS:
        raise ValueError("Holdout input budget exceeds 20 unique queries.")
    return InputPlan(tuple(inputs), document_hashes, query_hashes)


def render_query_input(query: RetrievalV2Query) -> str:
    return f"task: search result | query: {query.requirement.text}"


def render_document_input(experience: RetrievalEvalExperience) -> str:
    payload = {
        "description": experience.description,
        "kind": experience.kind.value,
        "outcome": experience.outcome,
        "skills": experience.skills,
    }
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"title: {experience.title} | text: {text}"


def make_input(
    *,
    input_id: str,
    role: EmbeddingRole,
    input_version: str,
    rendered_text: str,
) -> EmbeddingEvalInput:
    identity = json.dumps(
        {
            "input_version": input_version,
            "rendered_text": rendered_text,
            "role": role.value,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return EmbeddingEvalInput(
        input_id=input_id,
        input_sha256=hashlib.sha256(identity.encode("utf-8")).hexdigest(),
        role=role,
        input_version=input_version,
        rendered_text=rendered_text,
    )


def new_cache(
    *,
    git_revision: str,
    provider: str,
    model_name: str,
    corpus_sha256: str,
    development_queries_sha256: str,
    input_plan: InputPlan,
) -> EmbeddingEvaluationCache:
    now = datetime.now(UTC)
    return EmbeddingEvaluationCache(
        status="incomplete",
        created_at=now,
        updated_at=now,
        git_revision=git_revision,
        provider=provider,
        model_name=model_name,
        output_dimensionality=EMBEDDING_DIMENSIONS,
        corpus_sha256=corpus_sha256,
        development_queries_sha256=development_queries_sha256,
        query_input_version=QUERY_INPUT_VERSION,
        document_input_version=DOCUMENT_INPUT_VERSION,
        requested_input_count=len(input_plan.inputs),
        unique_input_count=len({item.input_sha256 for item in input_plan.inputs}),
        holdout_input_count=0,
        embeddings=[],
        usage=[],
        last_error_code=None,
    )


def validate_cache(
    cache: EmbeddingEvaluationCache,
    *,
    provider: str,
    model_name: str,
    corpus_sha256: str,
    development_queries_sha256: str,
    input_plan: InputPlan,
) -> None:
    expected = (
        provider,
        model_name,
        EMBEDDING_DIMENSIONS,
        corpus_sha256,
        development_queries_sha256,
        QUERY_INPUT_VERSION,
        DOCUMENT_INPUT_VERSION,
        len({item.input_sha256 for item in input_plan.inputs}),
        0,
    )
    actual = (
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
    if actual != expected:
        raise ValueError("Embedding cache identity does not match this evaluation run.")
    expected_hashes = {item.input_sha256 for item in input_plan.inputs}
    cached_hashes = [item.input_sha256 for item in cache.embeddings]
    if len(cached_hashes) != len(set(cached_hashes)) or set(cached_hashes) - expected_hashes:
        raise ValueError("Embedding cache contains duplicate or unknown inputs.")
    for item in cache.embeddings:
        validate_vector(tuple(item.vector))


async def fill_cache(
    cache: EmbeddingEvaluationCache,
    input_plan: InputPlan,
    provider: EmbeddingEvaluationProvider,
    cache_path: Path,
) -> EmbeddingEvaluationCache:
    cached_hashes = {item.input_sha256 for item in cache.embeddings}
    for role in (EmbeddingRole.DOCUMENT, EmbeddingRole.QUERY):
        unique: dict[str, EmbeddingEvalInput] = {}
        for item in input_plan.inputs:
            if item.role is role and item.input_sha256 not in cached_hashes:
                unique.setdefault(item.input_sha256, item)
        missing = tuple(unique.values())
        if not missing:
            continue
        provider_inputs = tuple(
            EmbeddingProviderInput(item.input_sha256, item.rendered_text) for item in missing
        )
        try:
            batch = await provider.embed_batch(provider_inputs)
            validate_batch(batch, len(missing), provider.model_name)
        except EmbeddingProviderFailure as exc:
            cache.last_error_code = exc.code.value
            cache.updated_at = datetime.now(UTC)
            save_cache(cache_path, cache)
            raise
        cache.embeddings.extend(
            CachedEmbedding(
                input_sha256=item.input_sha256,
                role=item.role,
                input_version=item.input_version,
                vector=list(vector),
            )
            for item, vector in zip(missing, batch.vectors, strict=True)
        )
        cache.usage.append(
            EmbeddingBatchUsageRecord(
                role=role,
                unique_input_count=len(missing),
                request_attempt_count=batch.request_attempt_count,
                token_count=batch.usage.token_count,
                billable_character_count=batch.usage.billable_character_count,
            )
        )
        cached_hashes.update(item.input_sha256 for item in missing)
        cache.updated_at = datetime.now(UTC)
        cache.last_error_code = None
        save_cache(cache_path, cache)
    expected_hashes = {item.input_sha256 for item in input_plan.inputs}
    if {item.input_sha256 for item in cache.embeddings} != expected_hashes:
        raise ValueError("Embedding cache is incomplete after provider execution.")
    cache.status = "complete"
    cache.updated_at = datetime.now(UTC)
    save_cache(cache_path, cache)
    return cache


def validate_batch(batch: EmbeddingProviderBatch, expected_count: int, model_name: str) -> None:
    if batch.model_name != model_name or len(batch.vectors) != expected_count:
        raise EmbeddingProviderFailure(
            code=EmbeddingProviderFailureCode.RESPONSE_INVALID,
            attempts=batch.request_attempt_count,
        )
    for vector in batch.vectors:
        if len(vector) != EMBEDDING_DIMENSIONS:
            raise EmbeddingProviderFailure(
                code=EmbeddingProviderFailureCode.DIMENSION_INVALID,
                attempts=batch.request_attempt_count,
            )
        if any(not math.isfinite(value) for value in vector) or not any(vector):
            raise EmbeddingProviderFailure(
                code=EmbeddingProviderFailureCode.VECTOR_INVALID,
                attempts=batch.request_attempt_count,
            )


def validate_vector(vector: tuple[float, ...]) -> None:
    if len(vector) != EMBEDDING_DIMENSIONS:
        raise ValueError("Embedding vector must contain exactly 1536 values.")
    if any(not math.isfinite(value) for value in vector):
        raise ValueError("Embedding vector contains a non-finite value.")
    norm = math.sqrt(math.fsum(value * value for value in vector))
    if norm == 0.0:
        raise ValueError("Embedding vector has zero norm.")


def load_cache(path: Path) -> EmbeddingEvaluationCache:
    with gzip.open(path, "rt", encoding="utf-8") as file:
        return EmbeddingEvaluationCache.model_validate_json(file.read())


def save_cache(path: Path, cache: EmbeddingEvaluationCache) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    with gzip.open(temporary, "wt", encoding="utf-8") as file:
        file.write(cache.model_dump_json())
    os.replace(temporary, path)


def cosine_similarity(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    validate_vector(left)
    validate_vector(right)
    dot = math.fsum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(math.fsum(value * value for value in left))
    right_norm = math.sqrt(math.fsum(value * value for value in right))
    return round(dot / (left_norm * right_norm), 12)


def evaluate_comparison(
    *,
    corpus: RetrievalV2Corpus,
    query_set: RetrievalV2QuerySet,
    input_plan: InputPlan,
    cache: EmbeddingEvaluationCache,
) -> tuple[RetrievalMethodReport, SelectedMethod, SelectedMethod]:
    if cache.status != "complete":
        raise ValueError("A complete embedding cache is required for evaluation.")
    vectors = {item.input_sha256: tuple(item.vector) for item in cache.embeddings}
    lexical_rankings = build_lexical_rankings(corpus, query_set)
    lexical_results = score_rankings(query_set, lexical_rankings)
    lexical_summary = summarize_results(lexical_results)
    lexical = RetrievalMethodReport(
        retriever_version="lexical-skill-v1",
        vector_threshold=None,
        lexical_weight=None,
        development_gate_passed=None,
        summary=lexical_summary,
        queries=lexical_results,
    )
    vector_scores = build_vector_scores(corpus, query_set, input_plan, vectors)
    selected_vector = select_vector_method(query_set, vector_scores, lexical_summary)
    selected_hybrid = select_hybrid_method(
        query_set,
        lexical_rankings,
        vector_scores,
        lexical_summary,
    )
    return lexical, selected_vector, selected_hybrid


def evaluate_fixed_comparison(
    *,
    corpus: RetrievalV2Corpus,
    query_set: RetrievalV2QuerySet,
    input_plan: InputPlan,
    vectors: dict[str, tuple[float, ...]],
    vector_threshold: float,
    hybrid_threshold: float,
    hybrid_alpha: float,
) -> tuple[RetrievalMethodReport, SelectedMethod, SelectedMethod]:
    lexical_rankings = build_lexical_rankings(corpus, query_set)
    lexical_results = score_rankings(query_set, lexical_rankings)
    lexical_summary = summarize_results(lexical_results)
    lexical = RetrievalMethodReport(
        retriever_version="lexical-skill-v1",
        vector_threshold=None,
        lexical_weight=None,
        development_gate_passed=None,
        summary=lexical_summary,
        queries=lexical_results,
    )
    vector_scores = build_vector_scores(corpus, query_set, input_plan, vectors)
    vector = selected_candidate(
        threshold=vector_threshold,
        alpha=None,
        results=score_rankings(
            query_set,
            vector_rankings(query_set, vector_scores, vector_threshold),
        ),
        lexical_summary=lexical_summary,
    )
    hybrid = selected_candidate(
        threshold=hybrid_threshold,
        alpha=hybrid_alpha,
        results=score_rankings(
            query_set,
            hybrid_rankings(
                query_set,
                lexical_rankings,
                vector_scores,
                threshold=hybrid_threshold,
                alpha=hybrid_alpha,
            ),
        ),
        lexical_summary=lexical_summary,
    )
    return lexical, vector, hybrid


def build_lexical_rankings(
    corpus: RetrievalV2Corpus,
    query_set: RetrievalV2QuerySet,
) -> dict[str, list[EmbeddingRankedExperience]]:
    profiles = {
        profile.profile_id: tuple(to_experience_record(item) for item in profile.experiences)
        for profile in corpus.profiles
    }
    rankings: dict[str, list[EmbeddingRankedExperience]] = {}
    for query in query_set.queries:
        requirement = to_requirement_record(query.requirement)
        candidates = retrieve_evidence_candidates(
            (requirement,),
            profiles[query.profile_id],
            limit=DEFAULT_CANDIDATE_LIMIT,
        )[0].candidates
        relevant = {label.experience_id for label in query.labels}
        rankings[query.query_id] = [
            EmbeddingRankedExperience(
                experience_id=candidate.experience.id,
                rank=index,
                score=float(candidate.score),
                relevant=candidate.experience.id in relevant,
                lexical_score=candidate.score,
                vector_cosine=None,
            )
            for index, candidate in enumerate(candidates, start=1)
        ]
    return rankings


def build_vector_scores(
    corpus: RetrievalV2Corpus,
    query_set: RetrievalV2QuerySet,
    input_plan: InputPlan,
    vectors: dict[str, tuple[float, ...]],
) -> dict[str, dict[UUID, float]]:
    experiences_by_profile = {
        profile.profile_id: profile.experiences for profile in corpus.profiles
    }
    scores: dict[str, dict[UUID, float]] = {}
    for query in query_set.queries:
        query_vector = vectors[input_plan.query_hashes[query.query_id]]
        scores[query.query_id] = {
            experience.id: cosine_similarity(
                query_vector,
                vectors[input_plan.document_hashes[experience.id]],
            )
            for experience in experiences_by_profile[query.profile_id]
        }
    return scores


def vector_rankings(
    query_set: RetrievalV2QuerySet,
    vector_scores: dict[str, dict[UUID, float]],
    threshold: float,
) -> dict[str, list[EmbeddingRankedExperience]]:
    rankings: dict[str, list[EmbeddingRankedExperience]] = {}
    for query in query_set.queries:
        relevant = {label.experience_id for label in query.labels}
        candidates = [
            (experience_id, cosine)
            for experience_id, cosine in vector_scores[query.query_id].items()
            if cosine >= threshold
        ]
        candidates.sort(key=lambda item: (-item[1], str(item[0])))
        rankings[query.query_id] = [
            EmbeddingRankedExperience(
                experience_id=experience_id,
                rank=index,
                score=cosine,
                relevant=experience_id in relevant,
                lexical_score=None,
                vector_cosine=cosine,
            )
            for index, (experience_id, cosine) in enumerate(
                candidates[:DEFAULT_CANDIDATE_LIMIT], start=1
            )
        ]
    return rankings


def hybrid_rankings(
    query_set: RetrievalV2QuerySet,
    lexical_rankings: dict[str, list[EmbeddingRankedExperience]],
    vector_scores: dict[str, dict[UUID, float]],
    *,
    threshold: float,
    alpha: float,
) -> dict[str, list[EmbeddingRankedExperience]]:
    vector = vector_rankings(query_set, vector_scores, threshold)
    rankings: dict[str, list[EmbeddingRankedExperience]] = {}
    for query in query_set.queries:
        lexical_items = lexical_rankings[query.query_id]
        vector_items = vector[query.query_id]
        lexical_by_id = {item.experience_id: item for item in lexical_items}
        vector_by_id = {item.experience_id: item for item in vector_items}
        relevant = {label.experience_id for label in query.labels}
        candidates: list[tuple[UUID, float, float | None, int | None]] = []
        for experience_id in set(lexical_by_id) | set(vector_by_id):
            lexical = lexical_by_id.get(experience_id)
            semantic = vector_by_id.get(experience_id)
            score = 0.0
            if lexical is not None:
                score += alpha / (RRF_K + lexical.rank)
            if semantic is not None:
                score += (1.0 - alpha) / (RRF_K + semantic.rank)
            candidates.append(
                (
                    experience_id,
                    round(score, 12),
                    semantic.vector_cosine if semantic is not None else None,
                    lexical.lexical_score if lexical is not None else None,
                )
            )
        candidates.sort(
            key=lambda item: (
                -item[1],
                -(item[2] if item[2] is not None else -math.inf),
                -(item[3] if item[3] is not None else -1),
                str(item[0]),
            )
        )
        rankings[query.query_id] = [
            EmbeddingRankedExperience(
                experience_id=experience_id,
                rank=index,
                score=score,
                relevant=experience_id in relevant,
                lexical_score=lexical_score,
                vector_cosine=cosine,
            )
            for index, (experience_id, score, cosine, lexical_score) in enumerate(
                candidates[:DEFAULT_CANDIDATE_LIMIT], start=1
            )
        ]
    return rankings


def select_vector_method(
    query_set: RetrievalV2QuerySet,
    scores: dict[str, dict[UUID, float]],
    lexical_summary: RetrievalV2Summary,
) -> SelectedMethod:
    candidates = [
        selected_candidate(
            threshold=threshold,
            alpha=None,
            results=score_rankings(query_set, vector_rankings(query_set, scores, threshold)),
            lexical_summary=lexical_summary,
        )
        for threshold in VECTOR_THRESHOLDS
    ]
    return choose_candidate(candidates, lexical_summary)


def select_hybrid_method(
    query_set: RetrievalV2QuerySet,
    lexical: dict[str, list[EmbeddingRankedExperience]],
    scores: dict[str, dict[UUID, float]],
    lexical_summary: RetrievalV2Summary,
) -> SelectedMethod:
    candidates = [
        selected_candidate(
            threshold=threshold,
            alpha=alpha,
            results=score_rankings(
                query_set,
                hybrid_rankings(
                    query_set,
                    lexical,
                    scores,
                    threshold=threshold,
                    alpha=alpha,
                ),
            ),
            lexical_summary=lexical_summary,
        )
        for alpha in HYBRID_ALPHAS
        for threshold in VECTOR_THRESHOLDS
    ]
    return choose_candidate(candidates, lexical_summary)


def selected_candidate(
    *,
    threshold: float,
    alpha: float | None,
    results: list[EmbeddingQueryResult],
    lexical_summary: RetrievalV2Summary,
) -> SelectedMethod:
    summary = summarize_results(results)
    return SelectedMethod(
        threshold=threshold,
        alpha=alpha,
        gate_passed=development_gate_passed(summary, lexical_summary),
        results=results,
        summary=summary,
    )


def choose_candidate(
    candidates: list[SelectedMethod],
    lexical_summary: RetrievalV2Summary,
) -> SelectedMethod:
    eligible = [
        candidate
        for candidate in candidates
        if candidate.summary.no_relevant_returned_accuracy_at_5
        >= lexical_summary.no_relevant_returned_accuracy_at_5
    ]
    pool = eligible or candidates
    return max(pool, key=selection_key if eligible else fallback_selection_key)


def selection_key(candidate: SelectedMethod) -> tuple[float, ...]:
    alpha_distance = abs((candidate.alpha if candidate.alpha is not None else 0.5) - 0.5)
    summary = candidate.summary
    return (
        summary.recall_at_5,
        summary.hit_at_5,
        summary.mrr_at_5,
        summary.precision_at_5,
        summary.no_relevant_returned_accuracy_at_5,
        candidate.threshold,
        -alpha_distance,
    )


def fallback_selection_key(candidate: SelectedMethod) -> tuple[float, ...]:
    return (
        candidate.summary.no_relevant_returned_accuracy_at_5,
        *selection_key(candidate),
    )


def development_gate_passed(
    candidate: RetrievalV2Summary,
    lexical: RetrievalV2Summary,
) -> bool:
    comparisons = (
        candidate.recall_at_5 >= lexical.recall_at_5,
        candidate.no_relevant_returned_accuracy_at_5
        >= lexical.no_relevant_returned_accuracy_at_5,
        candidate.hit_at_5 >= lexical.hit_at_5,
        candidate.mrr_at_5 >= lexical.mrr_at_5,
    )
    strict_improvement = (
        candidate.recall_at_5 > lexical.recall_at_5
        or candidate.no_relevant_returned_accuracy_at_5
        > lexical.no_relevant_returned_accuracy_at_5
        or candidate.hit_at_5 > lexical.hit_at_5
        or candidate.mrr_at_5 > lexical.mrr_at_5
    )
    return all(comparisons) and strict_improvement


def score_rankings(
    query_set: RetrievalV2QuerySet,
    rankings: dict[str, list[EmbeddingRankedExperience]],
) -> list[EmbeddingQueryResult]:
    return [score_query(query, rankings[query.query_id]) for query in query_set.queries]


def score_query(
    query: RetrievalV2Query,
    ranked: list[EmbeddingRankedExperience],
) -> EmbeddingQueryResult:
    support_levels = {label.experience_id: label.support_level for label in query.labels}
    relevant_ids = set(support_levels)
    if not relevant_ids:
        return EmbeddingQueryResult(
            query_id=query.query_id,
            profile_id=query.profile_id,
            description=query.description,
            relevant_experience_ids=[],
            support_levels={},
            ranked_experiences=ranked,
            returned_candidate_count=len(ranked),
            recall_at_1=None,
            recall_at_3=None,
            recall_at_5=None,
            precision_at_5=None,
            hit_at_1=None,
            hit_at_3=None,
            hit_at_5=None,
            reciprocal_rank_at_5=None,
            no_relevant_returned_at_5=len(ranked) == 0,
        )
    first_relevant_rank = next((item.rank for item in ranked if item.relevant), None)
    return EmbeddingQueryResult(
        query_id=query.query_id,
        profile_id=query.profile_id,
        description=query.description,
        relevant_experience_ids=list(support_levels),
        support_levels=support_levels,
        ranked_experiences=ranked,
        returned_candidate_count=len(ranked),
        recall_at_1=recall_at_k(ranked, relevant_ids, 1),
        recall_at_3=recall_at_k(ranked, relevant_ids, 3),
        recall_at_5=recall_at_k(ranked, relevant_ids, 5),
        precision_at_5=relevant_count_at_k(ranked, relevant_ids, 5) / 5,
        hit_at_1=float(relevant_count_at_k(ranked, relevant_ids, 1) > 0),
        hit_at_3=float(relevant_count_at_k(ranked, relevant_ids, 3) > 0),
        hit_at_5=float(relevant_count_at_k(ranked, relevant_ids, 5) > 0),
        reciprocal_rank_at_5=0.0 if first_relevant_rank is None else 1 / first_relevant_rank,
        no_relevant_returned_at_5=None,
    )


def summarize_results(results: list[EmbeddingQueryResult]) -> RetrievalV2Summary:
    positive = [result for result in results if result.recall_at_5 is not None]
    negative = [result for result in results if result.no_relevant_returned_at_5 is not None]
    return RetrievalV2Summary(
        query_count=len(results),
        positive_query_count=len(positive),
        negative_query_count=len(negative),
        recall_at_1=mean([required(item.recall_at_1) for item in positive]),
        recall_at_3=mean([required(item.recall_at_3) for item in positive]),
        recall_at_5=mean([required(item.recall_at_5) for item in positive]),
        precision_at_5=mean([required(item.precision_at_5) for item in positive]),
        hit_at_1=mean([required(item.hit_at_1) for item in positive]),
        hit_at_3=mean([required(item.hit_at_3) for item in positive]),
        hit_at_5=mean([required(item.hit_at_5) for item in positive]),
        mrr_at_5=mean([required(item.reciprocal_rank_at_5) for item in positive]),
        no_relevant_returned_accuracy_at_5=mean(
            [float(required(item.no_relevant_returned_at_5)) for item in negative]
        ),
        mean_returned_candidate_count=mean(
            [float(item.returned_candidate_count) for item in results]
        ),
    )


def recall_at_k(
    ranked: list[EmbeddingRankedExperience], relevant_ids: set[UUID], k: int
) -> float:
    return relevant_count_at_k(ranked, relevant_ids, k) / len(relevant_ids)


def relevant_count_at_k(
    ranked: list[EmbeddingRankedExperience], relevant_ids: set[UUID], k: int
) -> int:
    return sum(item.experience_id in relevant_ids for item in ranked[:k])


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def required(value: MetricValue | None) -> MetricValue:
    if value is None:
        raise ValueError("Expected a defined evaluation metric.")
    return value


def validate_lexical_baseline(
    baseline_path: Path,
    lexical: RetrievalMethodReport,
    *,
    corpus_sha256: str,
    development_queries_sha256: str,
) -> str:
    content = baseline_path.read_bytes()
    payload = json.loads(content)
    if (
        payload.get("corpus_sha256") != corpus_sha256
        or payload.get("query_set_sha256") != development_queries_sha256
        or payload.get("split") != RetrievalSplit.DEVELOPMENT.value
        or payload.get("retriever_version") != "lexical-skill-v1"
    ):
        raise ValueError("Lexical baseline identity does not match the frozen development set.")
    if payload.get("summary") != lexical.summary.model_dump():
        raise ValueError("Recomputed lexical summary differs from the immutable baseline.")
    expected_queries = payload.get("queries")
    if not isinstance(expected_queries, list) or len(expected_queries) != len(lexical.queries):
        raise ValueError("Lexical baseline query count differs from recomputed output.")
    for expected, actual in zip(expected_queries, lexical.queries, strict=True):
        expected_ranked = [
            (item["experience_id"], float(item["score"]))
            for item in expected["ranked_experiences"]
        ]
        actual_ranked = [
            (str(item.experience_id), item.score) for item in actual.ranked_experiences
        ]
        if expected.get("query_id") != actual.query_id or expected_ranked != actual_ranked:
            raise ValueError("Recomputed lexical ranking differs from the immutable baseline.")
    return hashlib.sha256(content).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
