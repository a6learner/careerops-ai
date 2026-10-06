import json
from collections.abc import Callable
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import pytest

from careerops.adapters.evidence_matcher_schema import evidence_matcher_instructions
from careerops.adapters.fake_evidence_matcher import FakeEvidenceMatcher
from careerops.adapters.groq_evidence_matcher import groq_matcher_response_json_schema
from careerops.domain.analysis_runs import EvidenceMatcherOutput
from careerops.domain.errors import (
    EvidenceMatcherError,
    EvidenceMatcherFailureReason,
    MatcherOutputFailureReason,
    MatcherOutputValidationError,
)
from careerops.domain.evidence_matching import (
    MATCHER_PROMPT_VERSION_V4,
    EvidenceMatcherInput,
)
from careerops.evaluation.evidence_matcher import MatcherEvalDataset
from careerops.evaluation.evidence_retrieval_v2 import RetrievalSplit, ReviewStatus
from careerops.evaluation.matcher_holdout import (
    DEVELOPMENT_POLICY_OVERRIDE_ID,
    MATCHER_HOLDOUT_MAX_OUTPUT_TOKENS,
    MATCHER_HOLDOUT_MINIMUM_REQUEST_INTERVAL_SECONDS,
    MATCHER_HOLDOUT_MODEL,
    MATCHER_HOLDOUT_POLICY_VERSION,
    MATCHER_HOLDOUT_REQUEST_BUDGET,
    MatcherHoldoutCheckpoint,
    MatcherHoldoutManifest,
    evaluate_holdout_safety,
    run_holdout,
)
from careerops.evaluation.rescore_evidence_matcher_coverage import (
    COVERAGE_EVALUATION_VERSION,
    MatcherCoverageRescoreReport,
)
from careerops.evaluation.run_evidence_matcher_holdout import create_holdout_matcher

ROOT = Path(__file__).parents[1]
CORPUS = ROOT / "evals/evidence_retrieval_v2/experiences.json"
DEVELOPMENT = ROOT / "evals/evidence_matcher_v1/development_cases.json"
SELECTED_DEVELOPMENT_MANIFEST = (
    ROOT / "evals/evidence_matcher_v1/prompt_v4_selected_development_manifest.json"
)
DEVELOPMENT_REPORT = (
    ROOT / "docs/metrics/2026-10-05-groq-evidence-matcher-development-prompt-v4.json"
)
DEVELOPMENT_COVERAGE_REPORT = ROOT / (
    "docs/metrics/"
    "2026-10-05-groq-evidence-matcher-development-prompt-v4-coverage-v2-gates-v4.json"
)
TOY_CASE_IDS = (
    "matcher-dev-005",
    "matcher-dev-009",
    "matcher-dev-002",
    "matcher-dev-006",
    "matcher-dev-003",
    "matcher-dev-011",
    "matcher-dev-004",
    "matcher-dev-008",
)


class CountingMatcher:
    def __init__(
        self,
        failure_for_call: dict[int, Exception] | None = None,
        *,
        model_name: str = MATCHER_HOLDOUT_MODEL,
    ) -> None:
        self._fake = FakeEvidenceMatcher()
        self._model_name = model_name
        self.failure_for_call = failure_for_call or {}
        self.request_attempt_count = 0
        self.case_ids: list[str] = []
        self.prompt_versions: list[str] = []

    @property
    def model_name(self) -> str:
        return self._model_name

    async def match(self, matcher_input: EvidenceMatcherInput) -> EvidenceMatcherOutput:
        self.request_attempt_count += 1
        self.case_ids.append(str(matcher_input.requirements[0].requirement_id))
        self.prompt_versions.append(matcher_input.prompt_version)
        failure = self.failure_for_call.get(self.request_attempt_count)
        if failure is not None:
            raise failure
        output = await self._fake.match(matcher_input)
        return EvidenceMatcherOutput(
            model_name=self.model_name,
            matches=output.matches,
            input_tokens=output.input_tokens,
            output_tokens=output.output_tokens,
        )


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _write_toy_holdout(path: Path) -> MatcherEvalDataset:
    path.parent.mkdir(parents=True, exist_ok=True)
    development = MatcherEvalDataset.model_validate_json(DEVELOPMENT.read_bytes())
    by_id = {case.case_id: case for case in development.cases}
    cases = []
    for index, source_case_id in enumerate(TOY_CASE_IDS, start=1):
        case_id = f"matcher-toy-holdout-{index:03d}"
        source_case = by_id[source_case_id]
        cases.append(
            source_case.model_copy(
                update={
                    "case_id": case_id,
                    "requirement": source_case.requirement.model_copy(
                        update={"id": uuid5(NAMESPACE_URL, case_id)}
                    ),
                }
            )
        )
    toy = MatcherEvalDataset(
        name="Matcher Holdout Runner Toy Fixture",
        version=2,
        split=RetrievalSplit.HOLDOUT,
        cases=cases,
    )
    path.write_text(toy.model_dump_json(indent=2), encoding="utf-8")
    return toy


def _write_manifest(
    path: Path,
    *,
    holdout_path: Path,
    checkpoint_path: Path,
    output_path: Path,
    status: ReviewStatus = ReviewStatus.APPROVED_FROZEN,
) -> None:
    evaluation_dir = ROOT / "src/careerops/evaluation"
    manifest = MatcherHoldoutManifest(
        version=1,
        status=status,
        reviewer="test-author" if status is ReviewStatus.APPROVED_FROZEN else None,
        reviewed_at=(
            datetime.fromisoformat("2026-10-05T12:00:00-07:00")
            if status is ReviewStatus.APPROVED_FROZEN
            else None
        ),
        corpus_sha256=_sha256(CORPUS),
        development_cases_sha256=_sha256(DEVELOPMENT),
        holdout_cases_sha256=_sha256(holdout_path),
        selected_development_manifest_sha256=_sha256(
            SELECTED_DEVELOPMENT_MANIFEST
        ),
        development_report_sha256=_sha256(DEVELOPMENT_REPORT),
        development_coverage_report_sha256=_sha256(
            DEVELOPMENT_COVERAGE_REPORT
        ),
        prompt_version="evidence-matcher-prompt-v4",
        prompt_sha256=sha256(
            evidence_matcher_instructions(MATCHER_PROMPT_VERSION_V4).encode("utf-8")
        ).hexdigest(),
        schema_version="evidence-matcher-schema-v1",
        response_schema_sha256=sha256(
            json.dumps(
                groq_matcher_response_json_schema(),
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest(),
        coverage_evaluation_version=COVERAGE_EVALUATION_VERSION,
        coverage_evaluator_sha256=_sha256(
            evaluation_dir / "evidence_matcher_coverage.py"
        ),
        matcher_evaluator_sha256=_sha256(evaluation_dir / "evidence_matcher.py"),
        holdout_runner_sha256=_sha256(evaluation_dir / "matcher_holdout.py"),
        holdout_cli_sha256=_sha256(
            evaluation_dir / "run_evidence_matcher_holdout.py"
        ),
        holdout_policy_version=MATCHER_HOLDOUT_POLICY_VERSION,
        development_policy_override_id=DEVELOPMENT_POLICY_OVERRIDE_ID,
        provider="groq",
        model=MATCHER_HOLDOUT_MODEL,
        request_budget=MATCHER_HOLDOUT_REQUEST_BUDGET,
        max_attempts_per_case=1,
        minimum_request_interval_seconds=(
            MATCHER_HOLDOUT_MINIMUM_REQUEST_INTERVAL_SECONDS
        ),
        max_output_tokens=MATCHER_HOLDOUT_MAX_OUTPUT_TOKENS,
        reasoning_effort="low",
        temperature=0.0,
        checkpoint_filename=checkpoint_path.name,
        output_filename=output_path.name,
        notes=["Toy fixture only; no provider request is made by this manifest."],
    )
    path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")


async def _run(
    tmp_path: Path,
    matcher: CountingMatcher,
    *,
    prepare: Callable[[Path, Path, Path], None] | None = None,
    status: ReviewStatus = ReviewStatus.APPROVED_FROZEN,
) -> tuple[Path, Path, Path]:
    holdout_path = tmp_path / "toy-holdout.json"
    manifest_path = tmp_path / "manifest.json"
    checkpoint_path = tmp_path / "checkpoint.json"
    output_path = tmp_path / "report.json"
    _write_toy_holdout(holdout_path)
    _write_manifest(
        manifest_path,
        holdout_path=holdout_path,
        checkpoint_path=checkpoint_path,
        output_path=output_path,
        status=status,
    )
    if prepare is not None:
        prepare(manifest_path, checkpoint_path, output_path)
    await run_holdout(
        experiences_path=CORPUS,
        development_cases_path=DEVELOPMENT,
        holdout_cases_path=holdout_path,
        manifest_path=manifest_path,
        selected_development_manifest_path=SELECTED_DEVELOPMENT_MANIFEST,
        development_report_path=DEVELOPMENT_REPORT,
        development_coverage_report_path=DEVELOPMENT_COVERAGE_REPORT,
        checkpoint_path=checkpoint_path,
        output_path=output_path,
        git_revision="test-revision",
        matcher=matcher,
        request_attempt_count=lambda: matcher.request_attempt_count,
    )
    return manifest_path, checkpoint_path, output_path


@pytest.mark.asyncio
async def test_holdout_runner_is_one_attempt_per_case_and_immutable(
    tmp_path: Path,
) -> None:
    matcher = CountingMatcher()
    _, checkpoint_path, output_path = await _run(tmp_path, matcher)

    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert matcher.request_attempt_count == MATCHER_HOLDOUT_REQUEST_BUDGET
    assert set(matcher.prompt_versions) == {MATCHER_PROMPT_VERSION_V4}
    assert report["provider_request_attempt_count"] == 8
    assert report["cumulative_provider_request_attempt_count"] == 8
    assert report["request_slots_consumed"] == 8
    assert report["actual_model_names"] == [MATCHER_HOLDOUT_MODEL]

    second_matcher = CountingMatcher()
    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        await _run(tmp_path, second_matcher)
    assert second_matcher.request_attempt_count == 0

    output_path.unlink()
    resumed_matcher = CountingMatcher()
    await _run(tmp_path, resumed_matcher)
    resumed_report = json.loads(output_path.read_text(encoding="utf-8"))
    assert resumed_matcher.request_attempt_count == 0
    assert resumed_report["provider_request_attempt_count"] == 0
    assert resumed_report["cumulative_provider_request_attempt_count"] == 8
    assert MatcherHoldoutCheckpoint.model_validate_json(
        checkpoint_path.read_bytes()
    ).request_slots_consumed == 8


@pytest.mark.asyncio
async def test_holdout_resume_skips_checkpointed_cases(tmp_path: Path) -> None:
    first_matcher = CountingMatcher()
    _, checkpoint_path, output_path = await _run(tmp_path, first_matcher)
    checkpoint = MatcherHoldoutCheckpoint.model_validate_json(
        checkpoint_path.read_bytes()
    )
    checkpoint.results = checkpoint.results[:3]
    checkpoint.request_slots_consumed = 3
    checkpoint.cumulative_provider_request_attempt_count = 3
    checkpoint_path.write_text(checkpoint.model_dump_json(indent=2), encoding="utf-8")
    output_path.unlink()

    resumed_matcher = CountingMatcher()
    await _run(tmp_path, resumed_matcher)
    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert resumed_matcher.request_attempt_count == 5
    assert report["provider_request_attempt_count"] == 5
    assert report["cumulative_provider_request_attempt_count"] == 8
    assert len({case["case_id"] for case in report["cases"]}) == 8


@pytest.mark.asyncio
async def test_ambiguous_in_progress_case_is_failed_without_recall(
    tmp_path: Path,
) -> None:
    first_matcher = CountingMatcher()
    _, checkpoint_path, output_path = await _run(tmp_path, first_matcher)
    checkpoint = MatcherHoldoutCheckpoint.model_validate_json(
        checkpoint_path.read_bytes()
    )
    ambiguous_case_id = checkpoint.case_ids[2]
    checkpoint.results = checkpoint.results[:2]
    checkpoint.in_progress_case_id = ambiguous_case_id
    checkpoint.request_slots_consumed = 3
    checkpoint.cumulative_provider_request_attempt_count = 2
    checkpoint_path.write_text(checkpoint.model_dump_json(indent=2), encoding="utf-8")
    output_path.unlink()

    resumed_matcher = CountingMatcher()
    await _run(tmp_path, resumed_matcher)
    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert resumed_matcher.request_attempt_count == 5
    assert report["cases"][2]["case_id"] == ambiguous_case_id
    assert report["cases"][2]["error_type"] == (
        "provider_outcome_unknown_after_local_interruption"
    )
    assert report["indeterminate_attempt_count"] == 1
    assert report["safety_acceptance"]["passed"] is False


@pytest.mark.asyncio
async def test_provider_and_output_failures_are_not_retried_or_converted_to_gap(
    tmp_path: Path,
) -> None:
    matcher = CountingMatcher(
        {
            2: EvidenceMatcherError(EvidenceMatcherFailureReason.RATE_LIMITED),
            4: MatcherOutputValidationError(
                MatcherOutputFailureReason.INVALID_SCHEMA,
                diagnostic="toy invalid field",
            ),
        }
    )
    _, _, output_path = await _run(tmp_path, matcher)
    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert matcher.request_attempt_count == 8
    assert report["coverage"]["provider_failure_count"] == 1
    assert report["coverage"]["output_failure_count"] == 1
    assert report["cases"][1]["raw_verdict"] is None
    assert report["cases"][3]["raw_verdict"] is None
    assert report["safety_acceptance"]["passed"] is False


@pytest.mark.asyncio
async def test_pending_manifest_and_wrong_model_are_rejected_before_calls(
    tmp_path: Path,
) -> None:
    pending_matcher = CountingMatcher()
    with pytest.raises(ValueError, match="await author review"):
        await _run(
            tmp_path / "pending",
            pending_matcher,
            status=ReviewStatus.PENDING_AUTHOR_REVIEW,
        )
    assert pending_matcher.request_attempt_count == 0

    wrong_model_matcher = CountingMatcher(model_name="wrong-model")
    with pytest.raises(ValueError, match="model does not match"):
        await _run(tmp_path / "wrong-model", wrong_model_matcher)
    assert wrong_model_matcher.request_attempt_count == 0


def test_holdout_provider_requires_separate_invocation_authorization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CAREEROPS_RUN_MATCHER_HOLDOUT", raising=False)
    monkeypatch.setenv("CAREEROPS_RUN_REAL_MATCHER_EVAL", "1")
    with pytest.raises(RuntimeError, match="CAREEROPS_RUN_MATCHER_HOLDOUT=1"):
        create_holdout_matcher()


def test_partial_to_gap_is_quality_diagnostic_not_safety_failure() -> None:
    development = MatcherCoverageRescoreReport.model_validate_json(
        DEVELOPMENT_COVERAGE_REPORT.read_bytes()
    )

    acceptance = evaluate_holdout_safety(development.summary)

    assert development.summary.partial_to_gap_rate.numerator == 1
    assert acceptance.passed is True
    assert {gate.name: gate.passed for gate in acceptance.gates} == {
        "schema_pass": True,
        "provider_failures": True,
        "output_failures": True,
        "citation_grounding": True,
        "unsupported_positive": True,
        "gap_to_positive": True,
        "partial_to_matched": True,
    }


def test_toy_runner_tests_do_not_reference_the_real_holdout() -> None:
    source = Path(__file__).read_text(encoding="utf-8")
    forbidden = "evals/evidence_matcher_v1/" + "holdout_cases.json"
    assert forbidden not in source
