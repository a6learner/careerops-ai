import argparse
from pathlib import Path

from careerops.evaluation.rescore_evidence_matcher_coverage import run_coverage_rescore


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rescore saved matcher development output with coverage v1 offline."
    )
    parser.add_argument("--experiences", type=Path, required=True)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--source-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--git-revision", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = run_coverage_rescore(
        experiences_path=args.experiences,
        development_cases_path=args.cases,
        source_report_path=args.source_report,
        output_path=args.output,
        git_revision=args.git_revision,
    )
    print(report.summary.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
