import argparse
import asyncio
import os
from datetime import UTC, datetime
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from careerops.domain.embeddings import EMBEDDING_DIMENSIONS
from careerops.evaluation.embedding_retrieval_v2 import (
    DOCUMENT_INPUT_VERSION,
    GEMINI_EMBEDDING_MODEL,
    HYBRID_ALPHAS,
    HYBRID_RETRIEVER_VERSION,
    QUERY_INPUT_VERSION,
    VECTOR_RETRIEVER_VERSION,
    VECTOR_THRESHOLDS,
    EmbeddingComparisonReport,
    EmbeddingEvaluationProvider,
    FakeEmbeddingEvaluationProvider,
    RetrievalMethodReport,
    SelectedMethod,
    build_input_plan,
    evaluate_comparison,
    file_sha256,
    fill_cache,
    load_cache,
    new_cache,
    validate_cache,
    validate_lexical_baseline,
)
from careerops.evaluation.evidence_retrieval_v2 import (
    RetrievalSplit,
    load_corpus,
    load_query_set,
    load_review_manifest,
    validate_review_manifest,
)
from careerops.evaluation.gemini_embedding_provider import (
    GeminiEmbeddingEvaluationProvider,
)


class EmbeddingEvaluationSecrets(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    gemini_api_key: SecretStr | None = Field(
        default=None,
        validation_alias="CAREEROPS_GEMINI_API_KEY",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare lexical, vector, and hybrid retrieval on development data."
    )
    parser.add_argument("--experiences", type=Path, required=True)
    parser.add_argument("--queries", type=Path, required=True)
    parser.add_argument("--review-manifest", type=Path, required=True)
    parser.add_argument("--lexical-baseline", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--git-revision", required=True)
    parser.add_argument("--provider", choices=("fake", "gemini"), default="fake")
    return parser.parse_args()


async def run(
    *,
    experiences_path: Path,
    queries_path: Path,
    review_manifest_path: Path,
    lexical_baseline_path: Path,
    cache_path: Path,
    output_path: Path,
    git_revision: str,
    provider_name: str,
    provider: EmbeddingEvaluationProvider,
) -> EmbeddingComparisonReport:
    if output_path.exists():
        raise FileExistsError(f"Refusing to overwrite evaluation evidence: {output_path}")
    corpus, corpus_hash = load_corpus(experiences_path)
    query_set, query_set_hash = load_query_set(queries_path, corpus)
    if query_set.split is not RetrievalSplit.DEVELOPMENT:
        raise RuntimeError("Holdout embedding evaluation is sealed.")
    manifest = load_review_manifest(review_manifest_path)
    validate_review_manifest(
        manifest,
        corpus_sha256=corpus_hash,
        query_set_sha256=query_set_hash,
        split=query_set.split,
    )
    input_plan = build_input_plan(corpus, query_set)
    if cache_path.exists():
        cache = load_cache(cache_path)
    else:
        cache = new_cache(
            git_revision=git_revision,
            provider=provider_name,
            model_name=provider.model_name,
            corpus_sha256=corpus_hash,
            development_queries_sha256=query_set_hash,
            input_plan=input_plan,
        )
    validate_cache(
        cache,
        provider=provider_name,
        model_name=provider.model_name,
        corpus_sha256=corpus_hash,
        development_queries_sha256=query_set_hash,
        input_plan=input_plan,
    )
    cache = await fill_cache(cache, input_plan, provider, cache_path)
    lexical, vector, hybrid = evaluate_comparison(
        corpus=corpus,
        query_set=query_set,
        input_plan=input_plan,
        cache=cache,
    )
    lexical_baseline_hash = validate_lexical_baseline(
        lexical_baseline_path,
        lexical,
        corpus_sha256=corpus_hash,
        development_queries_sha256=query_set_hash,
    )
    report = EmbeddingComparisonReport(
        created_at=datetime.now(UTC),
        git_revision=git_revision,
        corpus_sha256=corpus_hash,
        development_queries_sha256=query_set_hash,
        lexical_baseline_sha256=lexical_baseline_hash,
        cache_sha256=file_sha256(cache_path),
        provider=provider_name,
        model_name=provider.model_name,
        output_dimensionality=EMBEDDING_DIMENSIONS,
        query_input_version=QUERY_INPUT_VERSION,
        document_input_version=DOCUMENT_INPUT_VERSION,
        cache_created_at=cache.created_at,
        cache_completed_at=cache.updated_at,
        requested_input_count=cache.requested_input_count,
        unique_input_count=cache.unique_input_count,
        holdout_input_count=cache.holdout_input_count,
        provider_request_attempt_count=sum(item.request_attempt_count for item in cache.usage),
        usage=cache.usage,
        selection_policy=(
            "Require negative accuracy@5 at least lexical; maximize Recall@5, Hit@5, "
            "MRR@5, Precision@5, negative accuracy@5, threshold, then alpha proximity to 0.5."
        ),
        vector_threshold_grid=list(VECTOR_THRESHOLDS),
        hybrid_alpha_grid=list(HYBRID_ALPHAS),
        lexical=lexical,
        vector=method_report(VECTOR_RETRIEVER_VERSION, vector),
        hybrid=method_report(HYBRID_RETRIEVER_VERSION, hybrid),
        limitations=[
            "Synthetic development labels do not establish holdout or production accuracy.",
            "One project author reviewed the labels; inter-annotator agreement is not measured.",
            "The stable provider model alias may change; the saved cache freezes this run.",
            "No production Analysis Run retrieval behavior changed.",
            "Holdout inputs and provider calls are zero.",
        ],
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_name(f".{output_path.name}.tmp")
    temporary.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    os.rename(temporary, output_path)
    return report


def method_report(version: str, selected: SelectedMethod) -> RetrievalMethodReport:
    return RetrievalMethodReport(
        retriever_version=version,
        vector_threshold=selected.threshold,
        lexical_weight=selected.alpha,
        development_gate_passed=selected.gate_passed,
        summary=selected.summary,
        queries=selected.results,
    )


def create_provider(name: str) -> EmbeddingEvaluationProvider:
    if name == "fake":
        return FakeEmbeddingEvaluationProvider()
    if os.environ.get("CAREEROPS_RUN_EMBEDDING_EVAL") != "1":
        raise RuntimeError("Set CAREEROPS_RUN_EMBEDDING_EVAL=1 to enable Gemini evaluation.")
    api_key = EmbeddingEvaluationSecrets().gemini_api_key
    if api_key is None:
        raise RuntimeError(
            "Set CAREEROPS_GEMINI_API_KEY in the ignored repository-root .env file."
        )
    return GeminiEmbeddingEvaluationProvider(
        api_key=api_key.get_secret_value(),
        model=GEMINI_EMBEDDING_MODEL,
        output_dimensionality=EMBEDDING_DIMENSIONS,
        timeout_seconds=30.0,
        max_attempts=1,
    )


def main() -> None:
    args = parse_args()
    provider = create_provider(args.provider)
    report = asyncio.run(
        run(
            experiences_path=args.experiences,
            queries_path=args.queries,
            review_manifest_path=args.review_manifest,
            lexical_baseline_path=args.lexical_baseline,
            cache_path=args.cache,
            output_path=args.output,
            git_revision=args.git_revision,
            provider_name=args.provider,
            provider=provider,
        )
    )
    print(
        report.model_dump_json(
            indent=2,
            include={"lexical", "vector", "hybrid", "unique_input_count", "holdout_input_count"},
        )
    )


if __name__ == "__main__":
    main()
