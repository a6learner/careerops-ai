import argparse
import asyncio
from datetime import UTC, datetime
from pathlib import Path

from careerops.adapters.factory import create_requirement_parser
from careerops.core.config import get_settings
from careerops.evaluation.requirement_parser import (
    RequirementEvalReport,
    evaluate_dataset,
    load_dataset,
    summarize_results,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate requirement parsing on labeled cases.")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--git-revision", required=True)
    return parser.parse_args()


async def run(dataset_path: Path, output_path: Path, git_revision: str) -> None:
    if output_path.exists():
        raise FileExistsError(f"Refusing to overwrite evaluation evidence: {output_path}")
    settings = get_settings()
    if settings.llm_provider != "groq":
        raise RuntimeError("Live evaluation requires CAREEROPS_LLM_PROVIDER=groq.")
    dataset, dataset_hash = load_dataset(dataset_path)
    results = await evaluate_dataset(dataset, create_requirement_parser(settings))
    report = RequirementEvalReport(
        created_at=datetime.now(UTC),
        git_revision=git_revision,
        dataset_name=dataset.name,
        dataset_version=dataset.version,
        dataset_sha256=dataset_hash,
        provider=settings.llm_provider,
        configured_model=settings.llm_model,
        summary=summarize_results(results),
        cases=results,
        limitations=[
            "Small synthetic dataset; results do not establish production accuracy.",
            "Exact-source-text scoring penalizes semantically equivalent spans.",
            "Provider behavior can change even when the model identifier stays constant.",
            "Provider billing charge was not measured.",
        ],
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    print(report.summary.model_dump_json(indent=2))


def main() -> None:
    args = parse_args()
    asyncio.run(run(args.dataset, args.output, args.git_revision))


if __name__ == "__main__":
    main()
