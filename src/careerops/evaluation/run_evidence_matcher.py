import argparse
import asyncio
import os
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel

from careerops.adapters.fake_evidence_matcher import FakeEvidenceMatcher
from careerops.domain.evidence_matching import MATCHER_PROMPT_VERSION, MATCHER_SCHEMA_VERSION
from careerops.evaluation.evidence_matcher import (
    MatcherCaseResult,
    MatcherEvalSummary,
    evaluate_matcher_dataset,
    load_matcher_dataset,
    load_matcher_review_manifest,
    summarize_matcher_results,
    validate_matcher_review_manifest,
)
from careerops.evaluation.evidence_retrieval_v2 import RetrievalSplit, load_corpus
from careerops.services.analysis_run_execution import EvidenceMatcher


class MatcherEvalReport(BaseModel):
    created_at: datetime
    git_revision: str
    corpus_name: str
    corpus_sha256: str
    dataset_name: str
    dataset_version: int
    dataset_sha256: str
    split: RetrievalSplit
    provider: str
    model_name: str
    schema_version: str
    prompt_version: str
    provider_request_attempt_count: int = 0
    provider_request_budget: int = 0
    resumed_from_sha256: str | None = None
    cumulative_provider_request_attempt_count: int = 0
    summary: MatcherEvalSummary
    cases: list[MatcherCaseResult]
    limitations: list[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate the fake Evidence Matcher on approved synthetic development data."
    )
    parser.add_argument("--experiences", type=Path, required=True)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--review-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--git-revision", required=True)
    return parser.parse_args()


async def run(
    experiences_path: Path,
    cases_path: Path,
    review_manifest_path: Path,
    output_path: Path,
    git_revision: str,
) -> MatcherEvalReport:
    matcher = FakeEvidenceMatcher()
    return await run_development(
        experiences_path=experiences_path,
        cases_path=cases_path,
        review_manifest_path=review_manifest_path,
        output_path=output_path,
        git_revision=git_revision,
        provider_name="fake",
        matcher=matcher,
        request_attempt_count=lambda: 0,
        provider_request_budget=0,
        prior_report=None,
        resumed_from_sha256=None,
        limitations=[
            "The fake matcher is deterministic test infrastructure, not semantic quality "
            "evidence.",
            "Development results do not establish holdout or production accuracy.",
            "Candidate lists are frozen matcher inputs; retrieval quality is reported "
            "separately.",
            "Latency excludes API, queue, database, and network time.",
        ],
    )


async def run_development(
    *,
    experiences_path: Path,
    cases_path: Path,
    review_manifest_path: Path,
    output_path: Path,
    git_revision: str,
    provider_name: str,
    matcher: EvidenceMatcher,
    request_attempt_count: Callable[[], int],
    provider_request_budget: int,
    prior_report: MatcherEvalReport | None,
    resumed_from_sha256: str | None,
    limitations: list[str],
) -> MatcherEvalReport:
    if output_path.exists():
        raise FileExistsError(f"Refusing to overwrite evaluation evidence: {output_path}")

    corpus, corpus_hash = load_corpus(experiences_path)
    dataset, dataset_hash = load_matcher_dataset(cases_path, corpus)
    if dataset.split is not RetrievalSplit.DEVELOPMENT:
        raise RuntimeError(
            "Matcher holdout is sealed until model, prompt, schema, and success criteria "
            "are frozen after an authorized development run."
        )
    manifest = load_matcher_review_manifest(review_manifest_path)
    validate_matcher_review_manifest(
        manifest,
        corpus_sha256=corpus_hash,
        dataset_sha256=dataset_hash,
        split=dataset.split,
    )

    prior_results: dict[str, MatcherCaseResult] = {}
    evaluation_dataset = dataset
    if prior_report is not None:
        _validate_prior_report(
            prior_report,
            corpus_sha256=corpus_hash,
            dataset_sha256=dataset_hash,
            provider_name=provider_name,
            model_name=matcher.model_name,
            case_ids=[case.case_id for case in dataset.cases],
        )
        prior_results = {case.case_id: case for case in prior_report.cases}
        retry_case_ids = {
            case.case_id for case in prior_report.cases if case.error_type is not None
        }
        if not retry_case_ids:
            raise RuntimeError("The prior matcher report has no failed cases to recover.")
        evaluation_dataset = dataset.model_copy(
            update={
                "cases": [case for case in dataset.cases if case.case_id in retry_case_ids]
            }
        )

    evaluated_results = await evaluate_matcher_dataset(corpus, evaluation_dataset, matcher)
    new_results = {case.case_id: case for case in evaluated_results}
    results = [
        (
            new_results[case.case_id]
            if case.case_id in new_results
            else prior_results[case.case_id]
        )
        for case in dataset.cases
    ]
    attempts = request_attempt_count()
    if attempts > provider_request_budget:
        raise RuntimeError("Matcher evaluation exceeded its provider request budget.")
    report = MatcherEvalReport(
        created_at=datetime.now(UTC),
        git_revision=git_revision,
        corpus_name=corpus.name,
        corpus_sha256=corpus_hash,
        dataset_name=dataset.name,
        dataset_version=dataset.version,
        dataset_sha256=dataset_hash,
        split=dataset.split,
        provider=provider_name,
        model_name=matcher.model_name,
        schema_version=MATCHER_SCHEMA_VERSION,
        prompt_version=MATCHER_PROMPT_VERSION,
        provider_request_attempt_count=attempts,
        provider_request_budget=provider_request_budget,
        resumed_from_sha256=resumed_from_sha256,
        cumulative_provider_request_attempt_count=(
            attempts
            if prior_report is None
            else (
                prior_report.cumulative_provider_request_attempt_count
                or prior_report.provider_request_attempt_count
            )
            + attempts
        ),
        summary=summarize_matcher_results(results),
        cases=results,
        limitations=limitations,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_name(f".{output_path.name}.tmp")
    temporary.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    os.rename(temporary, output_path)
    return report


def _validate_prior_report(
    report: MatcherEvalReport,
    *,
    corpus_sha256: str,
    dataset_sha256: str,
    provider_name: str,
    model_name: str,
    case_ids: list[str],
) -> None:
    report_case_ids = [case.case_id for case in report.cases]
    if (
        report.split is not RetrievalSplit.DEVELOPMENT
        or report.corpus_sha256 != corpus_sha256
        or report.dataset_sha256 != dataset_sha256
        or report.provider != provider_name
        or report.model_name != model_name
        or report.schema_version != MATCHER_SCHEMA_VERSION
        or report.prompt_version != MATCHER_PROMPT_VERSION
        or len(report_case_ids) != len(set(report_case_ids))
        or report_case_ids != case_ids
    ):
        raise ValueError("Prior matcher report does not match the frozen development run.")


def main() -> None:
    args = parse_args()
    report = asyncio.run(
        run(
            args.experiences,
            args.cases,
            args.review_manifest,
            args.output,
            args.git_revision,
        )
    )
    print(report.summary.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
