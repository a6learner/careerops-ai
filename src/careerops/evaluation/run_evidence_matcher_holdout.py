import argparse
import asyncio
import os
from pathlib import Path

from careerops.adapters.groq_evidence_matcher import GroqEvidenceMatcher
from careerops.evaluation.matcher_holdout import (
    MATCHER_HOLDOUT_MAX_OUTPUT_TOKENS,
    MATCHER_HOLDOUT_MINIMUM_REQUEST_INTERVAL_SECONDS,
    MATCHER_HOLDOUT_MODEL,
    MatcherHoldoutReport,
    run_holdout,
)
from careerops.evaluation.run_real_evidence_matcher import (
    GROQ_BASE_URL,
    MatcherEvaluationSecrets,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the separately authorized one-time matcher holdout."
    )
    parser.add_argument("--experiences", type=Path, required=True)
    parser.add_argument("--development-cases", type=Path, required=True)
    parser.add_argument("--holdout-cases", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--selected-development-manifest", type=Path, required=True)
    parser.add_argument("--development-report", type=Path, required=True)
    parser.add_argument("--development-coverage-report", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--git-revision", required=True)
    return parser.parse_args()


def create_holdout_matcher() -> GroqEvidenceMatcher:
    if os.environ.get("CAREEROPS_RUN_MATCHER_HOLDOUT") != "1":
        raise RuntimeError(
            "Set CAREEROPS_RUN_MATCHER_HOLDOUT=1 for this invocation to authorize "
            "the one-time Groq holdout."
        )
    api_key = MatcherEvaluationSecrets().groq_api_key
    if api_key is None or not api_key.get_secret_value().strip():
        raise RuntimeError("CAREEROPS_LLM_API_KEY is required for the holdout run.")
    return GroqEvidenceMatcher(
        api_key=api_key.get_secret_value(),
        model=MATCHER_HOLDOUT_MODEL,
        base_url=GROQ_BASE_URL,
        timeout_seconds=30.0,
        max_attempts=1,
        retry_base_delay_seconds=0.0,
        max_output_tokens=MATCHER_HOLDOUT_MAX_OUTPUT_TOKENS,
        minimum_request_interval_seconds=(
            MATCHER_HOLDOUT_MINIMUM_REQUEST_INTERVAL_SECONDS
        ),
    )


async def run_from_args(args: argparse.Namespace) -> MatcherHoldoutReport:
    matcher = create_holdout_matcher()
    return await run_holdout(
        experiences_path=args.experiences,
        development_cases_path=args.development_cases,
        holdout_cases_path=args.holdout_cases,
        manifest_path=args.manifest,
        selected_development_manifest_path=args.selected_development_manifest,
        development_report_path=args.development_report,
        development_coverage_report_path=args.development_coverage_report,
        checkpoint_path=args.checkpoint,
        output_path=args.output,
        git_revision=args.git_revision,
        matcher=matcher,
        request_attempt_count=lambda: matcher.request_attempt_count,
    )


def main() -> None:
    report = asyncio.run(run_from_args(parse_args()))
    print(report.safety_acceptance.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
