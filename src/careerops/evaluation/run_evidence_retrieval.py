import argparse
from datetime import UTC, datetime
from pathlib import Path

from careerops.domain.evidence_retrieval import DEFAULT_CANDIDATE_LIMIT
from careerops.evaluation.evidence_retrieval import (
    RETRIEVER_VERSION,
    RetrievalEvalReport,
    evaluate_dataset,
    load_dataset,
    summarize_results,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate evidence retrieval on labeled cases.")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--git-revision", required=True)
    return parser.parse_args()


def run(dataset_path: Path, output_path: Path, git_revision: str) -> RetrievalEvalReport:
    if output_path.exists():
        raise FileExistsError(f"Refusing to overwrite evaluation evidence: {output_path}")
    dataset, dataset_hash = load_dataset(dataset_path)
    results = evaluate_dataset(dataset)
    report = RetrievalEvalReport(
        created_at=datetime.now(UTC),
        git_revision=git_revision,
        dataset_name=dataset.name,
        dataset_version=dataset.version,
        dataset_sha256=dataset_hash,
        retriever_version=RETRIEVER_VERSION,
        candidate_limit=DEFAULT_CANDIDATE_LIMIT,
        summary=summarize_results(results),
        cases=results,
        limitations=[
            "Small synthetic development set; results do not establish production accuracy.",
            "Labels were authored for development and are not an independent holdout set.",
            "The baseline evaluates deterministic lexical and exact-skill ranking only.",
            "Latency, throughput, provider reliability, token usage, and cost were not measured.",
        ],
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return report


def main() -> None:
    args = parse_args()
    report = run(args.dataset, args.output, args.git_revision)
    print(report.summary.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
