import os
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from careerops.evaluation.evidence_matcher import load_matcher_dataset
from careerops.evaluation.evidence_matcher_coverage import (
    CoverageAcceptance,
    CoverageCaseResult,
    CoverageSummary,
    evaluate_coverage_acceptance,
    score_coverage_cases,
)
from careerops.evaluation.evidence_retrieval_v2 import RetrievalSplit, load_corpus
from careerops.evaluation.run_evidence_matcher import MatcherEvalReport

COVERAGE_EVALUATION_VERSION = "evidence-matcher-coverage-v2"


class MatcherCoverageRescoreReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    created_at: datetime
    git_revision: str
    evaluation_version: str
    source_report_sha256: str
    source_provider: str
    source_model_name: str
    source_prompt_version: str
    corpus_sha256: str
    development_cases_sha256: str
    provider_request_attempt_count: int
    summary: CoverageSummary
    acceptance: CoverageAcceptance
    cases: list[CoverageCaseResult]
    limitations: tuple[str, ...]


def run_coverage_rescore(
    *,
    experiences_path: Path,
    development_cases_path: Path,
    source_report_path: Path,
    output_path: Path,
    git_revision: str,
) -> MatcherCoverageRescoreReport:
    if output_path.exists():
        raise FileExistsError(f"Refusing to overwrite evaluation evidence: {output_path}")

    corpus, corpus_hash = load_corpus(experiences_path)
    dataset, dataset_hash = load_matcher_dataset(development_cases_path, corpus)
    if dataset.split is not RetrievalSplit.DEVELOPMENT:
        raise RuntimeError("Coverage rescoring accepts development data only.")
    source_content = source_report_path.read_bytes()
    source_report = MatcherEvalReport.model_validate_json(source_content)
    if (
        source_report.split is not RetrievalSplit.DEVELOPMENT
        or source_report.corpus_sha256 != corpus_hash
        or source_report.dataset_sha256 != dataset_hash
        or [case.case_id for case in source_report.cases]
        != [case.case_id for case in dataset.cases]
    ):
        raise ValueError("Source matcher report does not match the frozen development data.")

    cases, summary = score_coverage_cases(dataset.cases, source_report.cases)
    acceptance = evaluate_coverage_acceptance(
        summary,
        acceptable_evidence_accuracy=(
            source_report.summary.matcher_only_acceptable_evidence_accuracy
        ),
    )
    limitations = [
        "This report rescored saved development output and made zero provider calls.",
        "Synthetic development coverage does not establish holdout or production quality.",
        "The matcher holdout was not read, run, or used for tuning.",
    ]
    if any(case.error_type == "invalid_schema" for case in source_report.cases):
        limitations.insert(
            1,
            "A source invalid_schema case may lack raw response or field diagnostic data; "
            "when absent, its exact validation failure is unknown.",
        )
    report = MatcherCoverageRescoreReport(
        created_at=datetime.now(UTC),
        git_revision=git_revision,
        evaluation_version=COVERAGE_EVALUATION_VERSION,
        source_report_sha256=sha256(source_content).hexdigest(),
        source_provider=source_report.provider,
        source_model_name=source_report.model_name,
        source_prompt_version=source_report.prompt_version,
        corpus_sha256=corpus_hash,
        development_cases_sha256=dataset_hash,
        provider_request_attempt_count=0,
        summary=summary,
        acceptance=acceptance,
        cases=cases,
        limitations=tuple(limitations),
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_name(f".{output_path.name}.tmp")
    temporary.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    os.rename(temporary, output_path)
    return report
