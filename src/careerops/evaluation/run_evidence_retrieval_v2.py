import argparse
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel

from careerops.evaluation.evidence_retrieval_v2 import (
    DEFAULT_CANDIDATE_LIMIT,
    RETRIEVER_VERSION,
    RetrievalSplit,
    RetrievalV2QueryResult,
    RetrievalV2Summary,
    evaluate_query_set,
    load_corpus,
    load_query_set,
    load_review_manifest,
    summarize_results,
    validate_review_manifest,
)


class RetrievalV2Report(BaseModel):
    created_at: datetime
    git_revision: str
    corpus_name: str
    corpus_version: int
    corpus_sha256: str
    query_set_name: str
    query_set_sha256: str
    split: RetrievalSplit
    retriever_version: str
    candidate_limit: int
    summary: RetrievalV2Summary
    queries: list[RetrievalV2QueryResult]
    limitations: list[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate lexical retrieval on the reviewed P1-2b development split."
    )
    parser.add_argument("--experiences", type=Path, required=True)
    parser.add_argument("--queries", type=Path, required=True)
    parser.add_argument("--review-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--git-revision", required=True)
    return parser.parse_args()


def run(
    experiences_path: Path,
    queries_path: Path,
    review_manifest_path: Path,
    output_path: Path,
    git_revision: str,
) -> RetrievalV2Report:
    if output_path.exists():
        raise FileExistsError(f"Refusing to overwrite evaluation evidence: {output_path}")

    corpus, corpus_hash = load_corpus(experiences_path)
    query_set, query_set_hash = load_query_set(queries_path, corpus)
    manifest = load_review_manifest(review_manifest_path)
    validate_review_manifest(
        manifest,
        corpus_sha256=corpus_hash,
        query_set_sha256=query_set_hash,
        split=query_set.split,
    )
    if query_set.split is not RetrievalSplit.DEVELOPMENT:
        raise RuntimeError(
            "Holdout evaluation is sealed until lexical, vector, and hybrid candidates are frozen."
        )

    query_results = evaluate_query_set(corpus, query_set)
    report = RetrievalV2Report(
        created_at=datetime.now(UTC),
        git_revision=git_revision,
        corpus_name=corpus.name,
        corpus_version=corpus.version,
        corpus_sha256=corpus_hash,
        query_set_name=query_set.name,
        query_set_sha256=query_set_hash,
        split=query_set.split,
        retriever_version=RETRIEVER_VERSION,
        candidate_limit=DEFAULT_CANDIDATE_LIMIT,
        summary=summarize_results(query_results),
        queries=query_results,
        limitations=[
            "Synthetic development labels were reviewed and frozen by the project author.",
            "Development results do not establish holdout or production accuracy.",
            "Full and partial support are both binary-relevant for candidate retrieval metrics.",
            "Precision@5 uses a fixed denominator of five candidate slots.",
            "Latency, throughput, provider behavior, token usage, and cost are not measured.",
        ],
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return report


def main() -> None:
    args = parse_args()
    report = run(
        args.experiences,
        args.queries,
        args.review_manifest,
        args.output,
        args.git_revision,
    )
    print(report.summary.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
