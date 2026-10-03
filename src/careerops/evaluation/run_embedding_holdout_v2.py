import argparse
import asyncio
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from careerops.domain.embeddings import EMBEDDING_DIMENSIONS
from careerops.evaluation.embedding_holdout_v2 import (
    EXPECTED_DOCUMENT_VECTOR_COUNT,
    EXPECTED_HOLDOUT_QUERY_COUNT,
    FROZEN_DEVELOPMENT_CACHE_SHA256,
    FROZEN_DEVELOPMENT_COMMIT,
    FROZEN_DEVELOPMENT_REPORT_SHA256,
    HOLDOUT_SUCCESS_POLICY,
    EmbeddingHoldoutReport,
    evaluate_frozen_holdout,
    fill_holdout_cache,
    hybrid_holdout_report,
    lexical_holdout_report,
    load_frozen_development_evidence,
    load_holdout_cache,
    new_holdout_cache,
    validate_holdout_cache,
    vector_holdout_report,
)
from careerops.evaluation.embedding_retrieval_v2 import (
    DOCUMENT_INPUT_VERSION,
    GEMINI_EMBEDDING_MODEL,
    QUERY_INPUT_VERSION,
    EmbeddingEvaluationProvider,
    build_holdout_query_plan,
    file_sha256,
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
from careerops.evaluation.run_embedding_retrieval_v2 import EmbeddingEvaluationSecrets


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the one-time frozen Gemini embedding holdout evaluation."
    )
    parser.add_argument("--experiences", type=Path, required=True)
    parser.add_argument("--holdout-queries", type=Path, required=True)
    parser.add_argument("--review-manifest", type=Path, required=True)
    parser.add_argument("--frozen-development-report", type=Path, required=True)
    parser.add_argument("--frozen-development-cache", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--git-revision", required=True)
    return parser.parse_args()


async def run(
    *,
    experiences_path: Path,
    holdout_queries_path: Path,
    review_manifest_path: Path,
    frozen_development_report_path: Path,
    frozen_development_cache_path: Path,
    cache_path: Path,
    output_path: Path,
    git_revision: str,
    provider: EmbeddingEvaluationProvider,
) -> EmbeddingHoldoutReport:
    if output_path.exists():
        raise FileExistsError(f"Refusing to overwrite holdout evidence: {output_path}")
    corpus, corpus_hash = load_corpus(experiences_path)
    query_set, query_set_hash = load_query_set(holdout_queries_path, corpus)
    if query_set.split is not RetrievalSplit.HOLDOUT:
        raise RuntimeError("The one-time holdout runner accepts only the holdout split.")
    if len(query_set.queries) != EXPECTED_HOLDOUT_QUERY_COUNT:
        raise ValueError("The frozen holdout must contain exactly 20 queries.")
    manifest = load_review_manifest(review_manifest_path)
    validate_review_manifest(
        manifest,
        corpus_sha256=corpus_hash,
        query_set_sha256=query_set_hash,
        split=query_set.split,
    )
    input_plan = build_holdout_query_plan(corpus, query_set)
    frozen = load_frozen_development_evidence(
        report_path=frozen_development_report_path,
        cache_path=frozen_development_cache_path,
        corpus_sha256=corpus_hash,
        input_plan=input_plan,
    )
    if cache_path.exists():
        cache = load_holdout_cache(cache_path)
    else:
        cache = new_holdout_cache(
            git_revision=git_revision,
            provider="gemini",
            model_name=provider.model_name,
            corpus_sha256=corpus_hash,
            holdout_queries_sha256=query_set_hash,
            input_plan=input_plan,
        )
    validate_holdout_cache(
        cache,
        provider="gemini",
        model_name=provider.model_name,
        corpus_sha256=corpus_hash,
        holdout_queries_sha256=query_set_hash,
        input_plan=input_plan,
    )
    cache = await fill_holdout_cache(cache, input_plan, provider, cache_path)
    lexical, vector, hybrid = evaluate_frozen_holdout(
        corpus=corpus,
        query_set=query_set,
        input_plan=input_plan,
        frozen=frozen,
        holdout_cache=cache,
    )
    report = EmbeddingHoldoutReport(
        created_at=datetime.now(UTC),
        git_revision=git_revision,
        frozen_development_commit=FROZEN_DEVELOPMENT_COMMIT,
        frozen_development_report_sha256=FROZEN_DEVELOPMENT_REPORT_SHA256,
        frozen_development_cache_sha256=FROZEN_DEVELOPMENT_CACHE_SHA256,
        corpus_sha256=corpus_hash,
        holdout_queries_sha256=query_set_hash,
        query_cache_sha256=file_sha256(cache_path),
        provider="gemini",
        model_name=provider.model_name,
        output_dimensionality=EMBEDDING_DIMENSIONS,
        query_input_version=QUERY_INPUT_VERSION,
        document_input_version=DOCUMENT_INPUT_VERSION,
        cache_created_at=cache.created_at,
        cache_completed_at=cache.updated_at,
        reused_document_input_count=EXPECTED_DOCUMENT_VECTOR_COUNT,
        requested_input_count=cache.requested_input_count,
        unique_input_count=cache.unique_input_count,
        holdout_input_count=cache.holdout_input_count,
        provider_request_attempt_count=sum(item.request_attempt_count for item in cache.usage),
        usage=cache.usage,
        pre_registered_success_policy=HOLDOUT_SUCCESS_POLICY,
        lexical=lexical_holdout_report(lexical),
        vector=vector_holdout_report(vector),
        hybrid=hybrid_holdout_report(hybrid),
        limitations=[
            "Synthetic holdout labels do not establish production accuracy.",
            "One project author reviewed the labels; inter-annotator agreement is not measured.",
            "The Gemini stable model alias may differ from its P1-3a implementation date.",
            "The holdout is evaluated once with frozen parameters and is not used for retuning.",
            "No production Analysis Run retrieval behavior changed.",
        ],
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_name(f".{output_path.name}.tmp")
    temporary.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    os.rename(temporary, output_path)
    return report


def create_holdout_provider() -> EmbeddingEvaluationProvider:
    if os.environ.get("CAREEROPS_RUN_EMBEDDING_HOLDOUT") != "1":
        raise RuntimeError(
            "Set CAREEROPS_RUN_EMBEDDING_HOLDOUT=1 for the separately authorized run."
        )
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
    provider = create_holdout_provider()
    report = asyncio.run(
        run(
            experiences_path=args.experiences,
            holdout_queries_path=args.holdout_queries,
            review_manifest_path=args.review_manifest,
            frozen_development_report_path=args.frozen_development_report,
            frozen_development_cache_path=args.frozen_development_cache,
            cache_path=args.cache,
            output_path=args.output,
            git_revision=args.git_revision,
            provider=provider,
        )
    )
    print(
        json.dumps(
            {
                "unique_input_count": report.unique_input_count,
                "holdout_input_count": report.holdout_input_count,
                "provider_request_attempt_count": report.provider_request_attempt_count,
                "lexical": report.lexical.summary.model_dump(),
                "vector": {
                    "holdout_success": report.vector.holdout_success,
                    "summary": report.vector.summary.model_dump(),
                },
                "hybrid": {
                    "holdout_success": report.hybrid.holdout_success,
                    "summary": report.hybrid.summary.model_dump(),
                },
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
