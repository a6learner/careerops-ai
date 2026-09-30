import argparse
from pathlib import Path

from careerops.evaluation.evidence_retrieval_v2 import (
    RetrievalV2ReviewManifest,
    ReviewStatus,
    load_corpus,
    load_query_set,
    validate_acceptance_dataset,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate retrieval v2 drafts and create a pending review manifest."
    )
    parser.add_argument("--experiences", type=Path, required=True)
    parser.add_argument("--development-queries", type=Path, required=True)
    parser.add_argument("--holdout-queries", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def run(
    experiences_path: Path,
    development_queries_path: Path,
    holdout_queries_path: Path,
    output_path: Path,
) -> RetrievalV2ReviewManifest:
    if output_path.exists():
        raise FileExistsError(f"Refusing to overwrite review manifest: {output_path}")

    corpus, corpus_hash = load_corpus(experiences_path)
    development, development_hash = load_query_set(development_queries_path, corpus)
    holdout, holdout_hash = load_query_set(holdout_queries_path, corpus)
    validate_acceptance_dataset(corpus, development, holdout)

    manifest = RetrievalV2ReviewManifest(
        name="careerops-evidence-retrieval-v2-label-review",
        version=corpus.version,
        status=ReviewStatus.PENDING_AUTHOR_REVIEW,
        reviewer=None,
        reviewed_at=None,
        corpus_sha256=corpus_hash,
        development_queries_sha256=development_hash,
        holdout_queries_sha256=holdout_hash,
        notes=[
            "Draft validated structurally; semantic labels are not yet author-approved.",
            "Do not run development or holdout evaluation while review is pending.",
        ],
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    return manifest


def main() -> None:
    args = parse_args()
    manifest = run(
        args.experiences,
        args.development_queries,
        args.holdout_queries,
        args.output,
    )
    print(manifest.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
