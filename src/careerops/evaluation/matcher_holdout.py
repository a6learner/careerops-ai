import json
import os
from collections.abc import Callable
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from time import perf_counter
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from careerops.adapters.evidence_matcher_schema import evidence_matcher_instructions
from careerops.adapters.groq_evidence_matcher import groq_matcher_response_json_schema
from careerops.domain.evidence_matching import (
    MATCHER_PROMPT_VERSION_V4,
    MATCHER_SCHEMA_VERSION,
)
from careerops.evaluation.evidence_matcher import (
    MatcherCaseResult,
    MatcherEvalCase,
    MatcherEvalSummary,
    evaluate_matcher_case,
    failed_matcher_case_result,
    load_matcher_dataset,
    summarize_matcher_results,
    validate_matcher_acceptance_dataset,
)
from careerops.evaluation.evidence_matcher_coverage import (
    CoverageCaseResult,
    CoverageSummary,
    score_coverage_cases,
)
from careerops.evaluation.evidence_retrieval_v2 import (
    RetrievalSplit,
    ReviewStatus,
    load_corpus,
)
from careerops.evaluation.rescore_evidence_matcher_coverage import (
    COVERAGE_EVALUATION_VERSION,
    MatcherCoverageRescoreReport,
)
from careerops.evaluation.run_evidence_matcher import MatcherEvalReport
from careerops.evaluation.run_real_evidence_matcher import (
    validate_development_run_manifest,
)
from careerops.services.analysis_run_execution import EvidenceMatcher

MATCHER_HOLDOUT_POLICY_VERSION = "evidence-matcher-holdout-safety-v1"
MATCHER_HOLDOUT_REQUEST_BUDGET = 8
MATCHER_HOLDOUT_MODEL = "openai/gpt-oss-20b"
MATCHER_HOLDOUT_MINIMUM_REQUEST_INTERVAL_SECONDS = 11.0
MATCHER_HOLDOUT_MAX_OUTPUT_TOKENS = 800
DEVELOPMENT_POLICY_OVERRIDE_ID = "author-accepted-prompt-v4-underclaim-2026-10-05"


class MatcherHoldoutManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal[1]
    status: ReviewStatus
    reviewer: str | None
    reviewed_at: datetime | None
    corpus_sha256: str = Field(min_length=64, max_length=64)
    development_cases_sha256: str = Field(min_length=64, max_length=64)
    holdout_cases_sha256: str = Field(min_length=64, max_length=64)
    selected_development_manifest_sha256: str = Field(min_length=64, max_length=64)
    development_report_sha256: str = Field(min_length=64, max_length=64)
    development_coverage_report_sha256: str = Field(min_length=64, max_length=64)
    prompt_version: Literal["evidence-matcher-prompt-v4"]
    prompt_sha256: str = Field(min_length=64, max_length=64)
    schema_version: Literal["evidence-matcher-schema-v1"]
    response_schema_sha256: str = Field(min_length=64, max_length=64)
    coverage_evaluation_version: str
    coverage_evaluator_sha256: str = Field(min_length=64, max_length=64)
    matcher_evaluator_sha256: str = Field(min_length=64, max_length=64)
    holdout_runner_sha256: str = Field(min_length=64, max_length=64)
    holdout_cli_sha256: str = Field(min_length=64, max_length=64)
    holdout_policy_version: str
    development_policy_override_id: str
    provider: Literal["groq"]
    model: str
    request_budget: int
    max_attempts_per_case: int
    minimum_request_interval_seconds: float
    max_output_tokens: int
    reasoning_effort: Literal["low"]
    temperature: float
    checkpoint_filename: str
    output_filename: str
    notes: list[str]


class HoldoutSafetyGate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    passed: bool
    observed: str
    required: str


class HoldoutSafetyAcceptance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy_version: str
    passed: bool
    gates: tuple[HoldoutSafetyGate, ...]


class MatcherHoldoutCheckpoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal[1]
    created_at: datetime
    updated_at: datetime
    manifest_sha256: str
    corpus_sha256: str
    holdout_cases_sha256: str
    prompt_version: str
    schema_version: str
    provider: str
    model: str
    case_ids: tuple[str, ...]
    results: list[MatcherCaseResult]
    in_progress_case_id: str | None
    request_slots_consumed: int
    resume_count: int
    cumulative_provider_request_attempt_count: int


class MatcherHoldoutReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    created_at: datetime
    git_revision: str
    manifest_sha256: str
    checkpoint_sha256: str
    corpus_sha256: str
    development_cases_sha256: str
    holdout_cases_sha256: str
    selected_development_manifest_sha256: str
    development_report_sha256: str
    development_coverage_report_sha256: str
    provider: str
    configured_model: str
    actual_model_names: tuple[str, ...]
    schema_version: str
    prompt_version: str
    coverage_evaluation_version: str
    holdout_policy_version: str
    provider_request_attempt_count: int
    cumulative_provider_request_attempt_count: int
    request_slots_consumed: int
    indeterminate_attempt_count: int
    resume_count: int
    provider_request_budget: int
    summary: MatcherEvalSummary
    coverage: CoverageSummary
    safety_acceptance: HoldoutSafetyAcceptance
    quality_metrics_are_diagnostic: Literal[True]
    cases: list[MatcherCaseResult]
    coverage_cases: list[CoverageCaseResult]
    limitations: tuple[str, ...]


def validate_holdout_manifest(
    path: Path,
    *,
    experiences_path: Path,
    development_cases_path: Path,
    holdout_cases_path: Path,
    selected_development_manifest_path: Path,
    development_report_path: Path,
    development_coverage_report_path: Path,
    checkpoint_path: Path,
    output_path: Path,
) -> tuple[MatcherHoldoutManifest, str]:
    content = path.read_bytes()
    manifest = MatcherHoldoutManifest.model_validate_json(content)
    if manifest.status is not ReviewStatus.APPROVED_FROZEN:
        raise ValueError("Matcher holdout labels and run policy await author review.")
    if manifest.reviewer is None or not manifest.reviewer.strip():
        raise ValueError("Approved holdout manifest requires a reviewer.")
    if manifest.reviewed_at is None:
        raise ValueError("Approved holdout manifest requires a review timestamp.")

    development_report_content = development_report_path.read_bytes()
    development_coverage_content = development_coverage_report_path.read_bytes()
    selected_development_manifest_content = selected_development_manifest_path.read_bytes()
    validate_development_run_manifest(
        selected_development_manifest_path,
        experiences_path=experiences_path,
        cases_path=development_cases_path,
    )
    development_report = MatcherEvalReport.model_validate_json(development_report_content)
    development_coverage = MatcherCoverageRescoreReport.model_validate_json(
        development_coverage_content
    )
    expected = {
        "corpus_sha256": _file_sha256(experiences_path),
        "development_cases_sha256": _file_sha256(development_cases_path),
        "holdout_cases_sha256": _file_sha256(holdout_cases_path),
        "selected_development_manifest_sha256": sha256(
            selected_development_manifest_content
        ).hexdigest(),
        "development_report_sha256": sha256(development_report_content).hexdigest(),
        "development_coverage_report_sha256": sha256(
            development_coverage_content
        ).hexdigest(),
        "prompt_version": MATCHER_PROMPT_VERSION_V4,
        "prompt_sha256": sha256(
            evidence_matcher_instructions(MATCHER_PROMPT_VERSION_V4).encode("utf-8")
        ).hexdigest(),
        "schema_version": MATCHER_SCHEMA_VERSION,
        "response_schema_sha256": sha256(
            json.dumps(
                groq_matcher_response_json_schema(),
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest(),
        "coverage_evaluation_version": COVERAGE_EVALUATION_VERSION,
        "coverage_evaluator_sha256": _file_sha256(
            Path(__file__).with_name("evidence_matcher_coverage.py")
        ),
        "matcher_evaluator_sha256": _file_sha256(
            Path(__file__).with_name("evidence_matcher.py")
        ),
        "holdout_runner_sha256": _file_sha256(Path(__file__)),
        "holdout_cli_sha256": _file_sha256(
            Path(__file__).with_name("run_evidence_matcher_holdout.py")
        ),
        "holdout_policy_version": MATCHER_HOLDOUT_POLICY_VERSION,
        "development_policy_override_id": DEVELOPMENT_POLICY_OVERRIDE_ID,
        "model": MATCHER_HOLDOUT_MODEL,
        "request_budget": MATCHER_HOLDOUT_REQUEST_BUDGET,
        "max_attempts_per_case": 1,
        "minimum_request_interval_seconds": (
            MATCHER_HOLDOUT_MINIMUM_REQUEST_INTERVAL_SECONDS
        ),
        "max_output_tokens": MATCHER_HOLDOUT_MAX_OUTPUT_TOKENS,
        "reasoning_effort": "low",
        "temperature": 0.0,
        "checkpoint_filename": checkpoint_path.name,
        "output_filename": output_path.name,
    }
    if manifest.model_dump(include=set(expected)) != expected:
        raise ValueError("Holdout manifest does not match the frozen run configuration.")
    if (
        development_report.split is not RetrievalSplit.DEVELOPMENT
        or development_report.prompt_version != MATCHER_PROMPT_VERSION_V4
        or development_report.provider != "groq"
        or development_report.model_name != MATCHER_HOLDOUT_MODEL
        or development_coverage.source_report_sha256
        != manifest.development_report_sha256
        or development_coverage.source_prompt_version != MATCHER_PROMPT_VERSION_V4
        or not development_coverage.acceptance.safety_passed
    ):
        raise ValueError("Frozen development evidence does not support holdout readiness.")
    return manifest, sha256(content).hexdigest()


async def run_holdout(
    *,
    experiences_path: Path,
    development_cases_path: Path,
    holdout_cases_path: Path,
    manifest_path: Path,
    selected_development_manifest_path: Path,
    development_report_path: Path,
    development_coverage_report_path: Path,
    checkpoint_path: Path,
    output_path: Path,
    git_revision: str,
    matcher: EvidenceMatcher,
    request_attempt_count: Callable[[], int],
) -> MatcherHoldoutReport:
    if output_path.exists():
        raise FileExistsError(f"Refusing to overwrite holdout evidence: {output_path}")
    manifest, manifest_hash = validate_holdout_manifest(
        manifest_path,
        experiences_path=experiences_path,
        development_cases_path=development_cases_path,
        holdout_cases_path=holdout_cases_path,
        selected_development_manifest_path=selected_development_manifest_path,
        development_report_path=development_report_path,
        development_coverage_report_path=development_coverage_report_path,
        checkpoint_path=checkpoint_path,
        output_path=output_path,
    )
    corpus, corpus_hash = load_corpus(experiences_path)
    development, development_hash = load_matcher_dataset(development_cases_path, corpus)
    holdout, holdout_hash = load_matcher_dataset(holdout_cases_path, corpus)
    _validate_strict_v2_holdout(holdout.cases)
    validate_matcher_acceptance_dataset(development, holdout)
    if holdout.split is not RetrievalSplit.HOLDOUT:
        raise ValueError("Matcher holdout file has the wrong split.")

    checkpoint = _load_or_create_checkpoint(
        checkpoint_path,
        manifest_hash=manifest_hash,
        manifest=manifest,
        corpus_sha256=corpus_hash,
        holdout_cases_sha256=holdout_hash,
        case_ids=tuple(case.case_id for case in holdout.cases),
    )
    _validate_checkpoint(checkpoint, manifest_hash, holdout.cases)
    if checkpoint.in_progress_case_id is not None:
        ambiguous_case = holdout.cases[len(checkpoint.results)]
        if checkpoint.in_progress_case_id != ambiguous_case.case_id:
            raise ValueError("Holdout checkpoint in-progress case is out of order.")
        checkpoint.results.append(
            failed_matcher_case_result(
                ambiguous_case,
                matcher_eligible=True,
                error_type="provider_outcome_unknown_after_local_interruption",
                started=perf_counter(),
            )
        )
        checkpoint.in_progress_case_id = None
        checkpoint.resume_count += 1
        checkpoint.updated_at = datetime.now(UTC)
        _write_atomic(checkpoint_path, checkpoint)

    profiles = {profile.profile_id: profile for profile in corpus.profiles}
    if matcher.model_name != manifest.model:
        raise ValueError("Configured matcher model does not match the holdout manifest.")
    invocation_start_attempts = request_attempt_count()
    prior_confirmed_attempts = checkpoint.cumulative_provider_request_attempt_count
    for case in holdout.cases[len(checkpoint.results) :]:
        if checkpoint.request_slots_consumed >= manifest.request_budget:
            raise RuntimeError("Matcher holdout exhausted its frozen request budget.")
        checkpoint.in_progress_case_id = case.case_id
        checkpoint.request_slots_consumed += 1
        checkpoint.updated_at = datetime.now(UTC)
        _write_atomic(checkpoint_path, checkpoint)

        attempts_before = request_attempt_count()
        result = await evaluate_matcher_case(
            case,
            profiles[case.profile_id],
            matcher,
            prompt_version=manifest.prompt_version,
        )
        attempt_delta = request_attempt_count() - attempts_before
        if attempt_delta != manifest.max_attempts_per_case:
            raise RuntimeError("Matcher holdout did not use exactly one attempt per case.")
        cumulative_attempts = (
            prior_confirmed_attempts
            + request_attempt_count()
            - invocation_start_attempts
        )
        if cumulative_attempts > manifest.request_budget:
            raise RuntimeError("Matcher holdout exceeded its frozen request budget.")
        checkpoint.results.append(result)
        checkpoint.in_progress_case_id = None
        checkpoint.cumulative_provider_request_attempt_count = cumulative_attempts
        checkpoint.updated_at = datetime.now(UTC)
        _write_atomic(checkpoint_path, checkpoint)

    results = checkpoint.results
    actual_model_names = tuple(
        sorted({result.model_name for result in results if result.model_name is not None})
    )
    if any(model_name != manifest.model for model_name in actual_model_names):
        raise RuntimeError("Holdout result model does not match the frozen manifest.")
    coverage_cases, coverage = score_coverage_cases(holdout.cases, results)
    summary = summarize_matcher_results(results)
    safety_acceptance = evaluate_holdout_safety(coverage)
    checkpoint_content = checkpoint_path.read_bytes()
    report = MatcherHoldoutReport(
        created_at=datetime.now(UTC),
        git_revision=git_revision,
        manifest_sha256=manifest_hash,
        checkpoint_sha256=sha256(checkpoint_content).hexdigest(),
        corpus_sha256=corpus_hash,
        development_cases_sha256=development_hash,
        holdout_cases_sha256=holdout_hash,
        selected_development_manifest_sha256=(
            manifest.selected_development_manifest_sha256
        ),
        development_report_sha256=manifest.development_report_sha256,
        development_coverage_report_sha256=(
            manifest.development_coverage_report_sha256
        ),
        provider=manifest.provider,
        configured_model=manifest.model,
        actual_model_names=actual_model_names,
        schema_version=manifest.schema_version,
        prompt_version=manifest.prompt_version,
        coverage_evaluation_version=manifest.coverage_evaluation_version,
        holdout_policy_version=manifest.holdout_policy_version,
        provider_request_attempt_count=request_attempt_count()
        - invocation_start_attempts,
        cumulative_provider_request_attempt_count=(
            checkpoint.cumulative_provider_request_attempt_count
        ),
        request_slots_consumed=checkpoint.request_slots_consumed,
        indeterminate_attempt_count=sum(
            result.error_type == "provider_outcome_unknown_after_local_interruption"
            for result in results
        ),
        resume_count=checkpoint.resume_count,
        provider_request_budget=manifest.request_budget,
        summary=summary,
        coverage=coverage,
        safety_acceptance=safety_acceptance,
        quality_metrics_are_diagnostic=True,
        cases=results,
        coverage_cases=coverage_cases,
        limitations=(
            "Synthetic holdout results do not establish production accuracy.",
            "Coverage, four-class exact accuracy, and partial-to-gap are quality "
            "diagnostics, not safety gates under the author-approved MVP policy.",
            "Provider or output failures remain failures and are never inferred as gaps.",
            "A checkpointed in-progress attempt becomes an indeterminate provider failure "
            "and is never automatically repeated.",
        ),
    )
    _write_immutable(output_path, report)
    return report


def evaluate_holdout_safety(coverage: CoverageSummary) -> HoldoutSafetyAcceptance:
    gates = (
        _safety_gate(
            "schema_pass",
            coverage.schema_valid_case_count == coverage.case_count,
            f"{coverage.schema_valid_case_count}/{coverage.case_count}",
            f"{coverage.case_count}/{coverage.case_count}",
        ),
        _safety_gate(
            "provider_failures",
            coverage.provider_failure_count == 0,
            str(coverage.provider_failure_count),
            "0",
        ),
        _safety_gate(
            "output_failures",
            coverage.output_failure_count == 0,
            str(coverage.output_failure_count),
            "0",
        ),
        _safety_gate(
            "citation_grounding",
            coverage.citation_validity_rate.numerator
            == coverage.citation_validity_rate.denominator,
            _rate_text(
                coverage.citation_validity_rate.numerator,
                coverage.citation_validity_rate.denominator,
            ),
            "100% of emitted positives",
        ),
        _safety_gate(
            "unsupported_positive",
            coverage.unsupported_positive_rate.numerator == 0,
            _rate_text(
                coverage.unsupported_positive_rate.numerator,
                coverage.unsupported_positive_rate.denominator,
            ),
            "0",
        ),
        _safety_gate(
            "gap_to_positive",
            coverage.gap_to_positive_rate.numerator == 0,
            _rate_text(
                coverage.gap_to_positive_rate.numerator,
                coverage.gap_to_positive_rate.denominator,
            ),
            "0",
        ),
        _safety_gate(
            "partial_to_matched",
            coverage.partial_to_matched_rate.numerator == 0,
            _rate_text(
                coverage.partial_to_matched_rate.numerator,
                coverage.partial_to_matched_rate.denominator,
            ),
            "0",
        ),
    )
    return HoldoutSafetyAcceptance(
        policy_version=MATCHER_HOLDOUT_POLICY_VERSION,
        passed=all(gate.passed for gate in gates),
        gates=gates,
    )


def _load_or_create_checkpoint(
    path: Path,
    *,
    manifest_hash: str,
    manifest: MatcherHoldoutManifest,
    corpus_sha256: str,
    holdout_cases_sha256: str,
    case_ids: tuple[str, ...],
) -> MatcherHoldoutCheckpoint:
    if path.exists():
        return MatcherHoldoutCheckpoint.model_validate_json(path.read_bytes())
    now = datetime.now(UTC)
    checkpoint = MatcherHoldoutCheckpoint(
        version=1,
        created_at=now,
        updated_at=now,
        manifest_sha256=manifest_hash,
        corpus_sha256=corpus_sha256,
        holdout_cases_sha256=holdout_cases_sha256,
        prompt_version=manifest.prompt_version,
        schema_version=manifest.schema_version,
        provider=manifest.provider,
        model=manifest.model,
        case_ids=case_ids,
        results=[],
        in_progress_case_id=None,
        request_slots_consumed=0,
        resume_count=0,
        cumulative_provider_request_attempt_count=0,
    )
    _write_atomic(path, checkpoint)
    return checkpoint


def _validate_checkpoint(
    checkpoint: MatcherHoldoutCheckpoint,
    manifest_hash: str,
    cases: list[MatcherEvalCase],
) -> None:
    case_ids = tuple(case.case_id for case in cases)
    result_ids = tuple(result.case_id for result in checkpoint.results)
    if (
        checkpoint.manifest_sha256 != manifest_hash
        or checkpoint.prompt_version != MATCHER_PROMPT_VERSION_V4
        or checkpoint.schema_version != MATCHER_SCHEMA_VERSION
        or checkpoint.provider != "groq"
        or checkpoint.model != MATCHER_HOLDOUT_MODEL
        or checkpoint.case_ids != case_ids
        or result_ids != case_ids[: len(result_ids)]
        or len(result_ids) != len(set(result_ids))
        or checkpoint.request_slots_consumed
        != len(checkpoint.results) + int(checkpoint.in_progress_case_id is not None)
        or checkpoint.request_slots_consumed > MATCHER_HOLDOUT_REQUEST_BUDGET
        or checkpoint.cumulative_provider_request_attempt_count
        > MATCHER_HOLDOUT_REQUEST_BUDGET
    ):
        raise ValueError("Holdout checkpoint does not match the frozen run identity.")


def _validate_strict_v2_holdout(cases: list[MatcherEvalCase]) -> None:
    if any(
        case.expected is not None
        or case.oracle_verdict is None
        or case.candidate_conditioned_verdict is None
        for case in cases
    ):
        raise ValueError(
            "Matcher holdout requires rubric-v2 dual verdicts and cannot use legacy labels."
        )


def _write_atomic(path: Path, model: BaseModel) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(model.model_dump_json(indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _write_immutable(path: Path, model: BaseModel) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(model.model_dump_json(indent=2), encoding="utf-8")
    try:
        os.link(temporary, path)
    except FileExistsError:
        raise
    finally:
        temporary.unlink(missing_ok=True)


def _file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _safety_gate(
    name: str,
    passed: bool,
    observed: str,
    required: str,
) -> HoldoutSafetyGate:
    return HoldoutSafetyGate(
        name=name,
        passed=passed,
        observed=observed,
        required=required,
    )


def _rate_text(numerator: int, denominator: int) -> str:
    return f"{numerator}/{denominator}"
