import argparse
import asyncio
from pathlib import Path

from careerops.evaluation.rescore_evidence_matcher import run_offline_rescore


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rescore saved matcher development output with the v2 rubric offline."
    )
    parser.add_argument("--experiences", type=Path, required=True)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--source-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--git-revision", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = asyncio.run(
        run_offline_rescore(
            experiences_path=args.experiences,
            development_cases_path=args.cases,
            source_report_path=args.source_report,
            output_path=args.output,
            git_revision=args.git_revision,
        )
    )
    print(report.summary.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
