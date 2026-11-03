"""Measure top-5 retrieval recall of labeled evidence for lexical and hybrid retrieval.

Read-only against the evaluation database. Requirements and experiences are loaded through
AnalysisRunRepository.load_analysis_input, candidates come from the product retrievers.
Query vectors are cached by requirement_id so reruns make no embedding calls.

Usage (env from stack_env_real.sh; CAREEROPS_EMBEDDING_PROVIDER=gemini and
CAREEROPS_RUN_EMBEDDING_INTEGRATION=1 must be set):
    python -m scripts.large_eval.retrieval_check --labels <matcher_labels.json> \
        --state <state.jsonl> --cache <query_vectors.json> --out <report.json>
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import time
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from pydantic import TypeAdapter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from careerops.adapters.embedding_factory import ConfiguredEmbeddingProviderResolver
from careerops.core.config import get_settings
from careerops.db.models import Job
from careerops.db.session import create_session_factory
from careerops.domain.analysis_runs import AnalysisInput, AnalysisRunWorkItem
from careerops.domain.embeddings import (
    GEMINI_EMBEDDING_SPACE,
    EmbeddingOutput,
    EmbeddingSpace,
    analysis_pipeline_version,
    embedding_space_for_analysis_pipeline,
)
from careerops.domain.errors import EmbeddingProviderError
from careerops.domain.evidence_retrieval import (
    RequirementCandidateSet,
    retrieve_evidence_candidates,
)
from careerops.repositories.analysis_runs import AnalysisRunRepository
from careerops.repositories.evidence_retrieval import EvidenceVectorRepository
from careerops.services.embedding_execution import EmbeddingProvider
from careerops.services.hybrid_retrieval import HybridEvidenceRetriever
from scripts.large_eval.drive_pipeline import State
from scripts.large_eval.models import MatcherLabelSet

PACE_SECONDS = 1.5
RATE_LIMIT_BACKOFF_SECONDS = (20.0, 60.0)
CACHE_FLUSH_EVERY = 10
POSITIVE = ("matched", "partial")
GAP = ("insufficient_evidence", "missing")


@dataclass
class CachedVector:
    model_name: str
    text_sha256: str
    vector: list[float]


CACHE_ADAPTER = TypeAdapter(dict[str, CachedVector])


@dataclass
class EmbedStats:
    cache_hits: int = 0
    api_requests: int = 0
    retried_requests: int = 0
    failed_queries: list[str] = field(default_factory=list)


class VectorCache:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.entries: dict[str, CachedVector] = (
            CACHE_ADAPTER.validate_json(path.read_bytes()) if path.exists() else {}
        )
        self.unsaved = 0

    def put(self, requirement_id: str, entry: CachedVector) -> None:
        self.entries[requirement_id] = entry
        self.unsaved += 1
        if self.unsaved >= CACHE_FLUSH_EVERY:
            self.flush()

    def flush(self) -> None:
        if self.unsaved == 0:
            return
        tmp = self.path.with_suffix(".tmp")
        tmp.write_bytes(CACHE_ADAPTER.dump_json(self.entries))
        tmp.replace(self.path)
        self.unsaved = 0


class PacedCachingProvider:
    """Wraps the product provider for one requirement: cache, pacing, rate-limit backoff."""

    last_request = 0.0

    def __init__(
        self,
        inner: EmbeddingProvider,
        cache: VectorCache,
        stats: EmbedStats,
        requirement_id: str,
    ) -> None:
        self._inner = inner
        self._cache = cache
        self._stats = stats
        self._requirement_id = requirement_id
        self.failed = False
        self.embedded = False

    @property
    def model_name(self) -> str:
        return self._inner.model_name

    async def embed(self, input_text: str) -> EmbeddingOutput:
        text_sha = hashlib.sha256(input_text.encode("utf-8")).hexdigest()
        cached = self._cache.entries.get(self._requirement_id)
        if cached and cached.text_sha256 == text_sha and cached.model_name == self.model_name:
            self._stats.cache_hits += 1
            self.embedded = True
            return EmbeddingOutput(model_name=cached.model_name, vector=tuple(cached.vector))
        output = await self._embed_with_backoff(input_text)
        self._cache.put(
            self._requirement_id,
            CachedVector(output.model_name, text_sha, list(output.vector)),
        )
        self.embedded = True
        return output

    async def _embed_with_backoff(self, input_text: str) -> EmbeddingOutput:
        backoffs = (*RATE_LIMIT_BACKOFF_SECONDS, None)
        for attempt, backoff in enumerate(backoffs):
            await self._pace()
            self._stats.api_requests += 1
            if attempt > 0:
                self._stats.retried_requests += 1
            try:
                return await self._inner.embed(input_text)
            except EmbeddingProviderError as exc:
                cause = exc.__cause__
                print(f"embed failed req={self._requirement_id} cause={cause!s}", flush=True)
                if backoff is None:
                    self.failed = True
                    self._stats.failed_queries.append(self._requirement_id)
                    raise
                await asyncio.sleep(backoff)
        raise AssertionError("unreachable")

    @staticmethod
    async def _pace() -> None:
        delay = PacedCachingProvider.last_request + PACE_SECONDS - time.monotonic()
        if delay > 0:
            await asyncio.sleep(delay)
        PacedCachingProvider.last_request = time.monotonic()


class RecordingVectorStore:
    def __init__(self, inner: EvidenceVectorRepository) -> None:
        self._inner = inner
        self.eligible: int | None = None

    async def exact_cosine_scores(
        self,
        *,
        user_id: UUID,
        experience_ids: tuple[UUID, ...],
        query_vector: tuple[float, ...],
        space: EmbeddingSpace,
        available_before: datetime,
    ) -> dict[UUID, float]:
        scores = await self._inner.exact_cosine_scores(
            user_id=user_id,
            experience_ids=experience_ids,
            query_vector=query_vector,
            space=space,
            available_before=available_before,
        )
        self.eligible = len(scores)
        return scores


@dataclass
class RequirementResult:
    pair_id: str
    requirement_id: str
    verdict: str
    user_experience_count: int
    labeled_exp_keys: list[str]
    lexical_top: list[str]
    hybrid_top: list[str]
    hybrid_mode: str
    vector_eligible: int | None
    lexical_hit: bool
    hybrid_hit: bool


def load_labels(path: Path) -> list[MatcherLabelSet]:
    items = json.loads(path.read_text(encoding="utf-8"))
    return [MatcherLabelSet.model_validate(item) for item in items]


def work_item_for(user_id: UUID, job_id: UUID, parse_run_id: UUID) -> AnalysisRunWorkItem:
    return AnalysisRunWorkItem(
        id=uuid4(),
        attempt=1,
        user_id=user_id,
        job_id=job_id,
        parse_run_id=parse_run_id,
        input_fingerprint="",
        model_name="",
        prompt_version=analysis_pipeline_version(GEMINI_EMBEDDING_SPACE),
        created_at=datetime.now(UTC),
    )


def keys_of(candidate_set: RequirementCandidateSet, exp_keys: dict[UUID, str]) -> list[str]:
    return [exp_keys.get(c.experience.id, str(c.experience.id)) for c in candidate_set.candidates]


async def check_pair(
    session: AsyncSession,
    label_set: MatcherLabelSet,
    state: State,
    exp_keys: dict[UUID, str],
    provider: EmbeddingProvider,
    cache: VectorCache,
    stats: EmbedStats,
    problems: list[str],
) -> list[RequirementResult]:
    job = state.get(f"job:{label_set.pair_id}")
    parse = state.get(f"parse:{label_set.pair_id}")
    if job is None or parse is None:
        problems.append(f"{label_set.pair_id}: missing job or parse state")
        return []
    job_id = UUID(job["job_id"])
    user_id = await session.scalar(select(Job.user_id).where(Job.id == job_id))
    if user_id is None:
        problems.append(f"{label_set.pair_id}: job {job_id} not in database")
        return []
    work_item = work_item_for(user_id, job_id, UUID(parse["final"]["id"]))
    analysis_input: AnalysisInput = await AnalysisRunRepository(session).load_analysis_input(
        work_item
    )
    requirements = {str(r.id): r for r in analysis_input.requirements}
    space = embedding_space_for_analysis_pipeline(work_item.prompt_version)
    results: list[RequirementResult] = []
    for label in label_set.labels:
        requirement = requirements.get(label.requirement_id)
        if requirement is None:
            problems.append(f"{label_set.pair_id}: requirement {label.requirement_id} not loaded")
            continue
        (lexical,) = retrieve_evidence_candidates((requirement,), analysis_input.experiences)
        wrapped = PacedCachingProvider(provider, cache, stats, label.requirement_id)
        store = RecordingVectorStore(EvidenceVectorRepository(session))
        retriever = HybridEvidenceRetriever(vectors=store, provider=wrapped, space=space)
        (hybrid,) = await retriever.retrieve(
            user_id=user_id,
            requirements=(requirement,),
            experiences=analysis_input.experiences,
            available_before=datetime.now(UTC),
        )
        labeled = sorted({e.exp_key for e in label.evidence})
        lexical_top = keys_of(lexical, exp_keys)
        hybrid_top = keys_of(hybrid, exp_keys)
        results.append(
            RequirementResult(
                pair_id=label_set.pair_id,
                requirement_id=label.requirement_id,
                verdict=label.verdict,
                user_experience_count=len(analysis_input.experiences),
                labeled_exp_keys=labeled,
                lexical_top=lexical_top,
                hybrid_top=hybrid_top,
                hybrid_mode=hybrid_mode(wrapped, store),
                vector_eligible=store.eligible,
                lexical_hit=bool(set(labeled) & set(lexical_top)),
                hybrid_hit=bool(set(labeled) & set(hybrid_top)),
            )
        )
    return results


def hybrid_mode(provider: PacedCachingProvider, store: RecordingVectorStore) -> str:
    if provider.failed:
        return "fallback_embedding_failed"
    if store.eligible is None:
        return "fallback_query_vector_invalid" if provider.embedded else "fallback_unknown"
    if store.eligible == 0:
        return "lexical_no_vector_eligible"
    return "fused"


def rate(hits: int, n: int) -> float | None:
    return round(hits / n, 4) if n else None


def mean(values: list[int]) -> float | None:
    return round(sum(values) / len(values), 3) if values else None


def positive_metrics(rows: list[RequirementResult]) -> dict[str, object]:
    lexical_hits = sum(r.lexical_hit for r in rows)
    hybrid_hits = sum(r.hybrid_hit for r in rows)
    return {
        "n": len(rows),
        "n_user_has_at_most_5_experiences": sum(r.user_experience_count <= 5 for r in rows),
        "lexical_recall_at_5": rate(lexical_hits, len(rows)),
        "lexical_hits": lexical_hits,
        "hybrid_recall_at_5": rate(hybrid_hits, len(rows)),
        "hybrid_hits": hybrid_hits,
        "hit_only_lexical": sum(r.lexical_hit and not r.hybrid_hit for r in rows),
        "hit_only_hybrid": sum(r.hybrid_hit and not r.lexical_hit for r in rows),
        "miss_both": sum(not r.lexical_hit and not r.hybrid_hit for r in rows),
        "lexical_mean_candidates": mean([len(r.lexical_top) for r in rows]),
        "hybrid_mean_candidates": mean([len(r.hybrid_top) for r in rows]),
    }


def gap_metrics(rows: list[RequirementResult]) -> dict[str, object]:
    return {
        "n": len(rows),
        "lexical_mean_candidates": mean([len(r.lexical_top) for r in rows]),
        "lexical_zero_candidate_share": rate(sum(not r.lexical_top for r in rows), len(rows)),
        "hybrid_mean_candidates": mean([len(r.hybrid_top) for r in rows]),
        "hybrid_zero_candidate_share": rate(sum(not r.hybrid_top for r in rows), len(rows)),
    }


def summarize(rows: list[RequirementResult]) -> dict[str, object]:
    by_verdict: dict[str, list[RequirementResult]] = defaultdict(list)
    for row in rows:
        by_verdict[row.verdict].append(row)
    positives = [r for r in rows if r.verdict in POSITIVE]
    fused_positives = [r for r in positives if r.hybrid_mode == "fused"]
    gaps = [r for r in rows if r.verdict in GAP]
    modes: dict[str, int] = defaultdict(int)
    for row in rows:
        modes[row.hybrid_mode] += 1
    return {
        "n_requirements": len(rows),
        "hybrid_modes": dict(modes),
        "positives": positive_metrics(positives),
        "positives_fused_only": positive_metrics(fused_positives),
        "gaps": gap_metrics(gaps),
        "per_verdict": {
            verdict: (
                positive_metrics(by_verdict[verdict])
                if verdict in POSITIVE
                else gap_metrics(by_verdict[verdict])
            )
            for verdict in (*POSITIVE, *GAP)
        },
    }


def print_summary(summary: dict[str, object], stats: EmbedStats, problems: list[str]) -> None:
    print(json.dumps(summary, indent=2))
    print(
        f"embedding: cache_hits={stats.cache_hits} api_requests={stats.api_requests} "
        f"retried_requests={stats.retried_requests} failed_queries={len(stats.failed_queries)}"
    )
    for problem in problems:
        print(f"PROBLEM: {problem}")


async def run(args: argparse.Namespace) -> int:
    settings = get_settings()
    if settings.embedding_provider != "gemini":
        raise SystemExit("CAREEROPS_EMBEDDING_PROVIDER must be gemini")
    space = GEMINI_EMBEDDING_SPACE
    provider = ConfiguredEmbeddingProviderResolver(settings).resolve(
        space.model_name, space.document_input_version
    )
    state = State.load(args.state)
    exp_keys = {
        UUID(record["experience_id"]): key.removeprefix("experience:")
        for key, record in state.records.items()
        if key.startswith("experience:")
    }
    cache = VectorCache(args.cache)
    stats = EmbedStats()
    problems: list[str] = []
    rows: list[RequirementResult] = []
    session_factory = create_session_factory(settings.database_url)
    try:
        for index, label_set in enumerate(load_labels(args.labels), 1):
            async with session_factory() as session:
                rows.extend(
                    await check_pair(
                        session, label_set, state, exp_keys, provider, cache, stats, problems
                    )
                )
                await session.rollback()
            print(f"[{index}] {label_set.pair_id} done; rows={len(rows)}", flush=True)
    finally:
        cache.flush()
    summary = summarize(rows)
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "embedding_model": space.model_name,
        "candidate_limit": 5,
        "summary": summary,
        "embedding": asdict(stats),
        "problems": problems,
        "requirements": [asdict(row) for row in rows],
    }
    args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print_summary(summary, stats, problems)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    logging.basicConfig(level=logging.WARNING)
    return asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
