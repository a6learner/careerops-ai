from pathlib import Path

import pytest

from careerops.domain.evidence_matching import EvidenceVerdict
from careerops.evaluation.evidence_matcher import load_matcher_dataset
from careerops.evaluation.evidence_matcher_coverage import (
    CoverageDirection,
    coverage_direction,
)
from careerops.evaluation.evidence_retrieval_v2 import RetrievalSplit, load_corpus
from careerops.evaluation.rescore_evidence_matcher_coverage import run_coverage_rescore

CORPUS_PATH = Path("evals/evidence_retrieval_v2/experiences.json")
DEVELOPMENT_PATH = Path("evals/evidence_matcher_v1/development_cases.json")
PROMPT_V2_REPORT_PATH = Path(
    "docs/metrics/2026-10-04-groq-evidence-matcher-development-prompt-v2.json"
)


def test_prompt_v2_coverage_rescore_uses_all_case_denominators(tmp_path: Path) -> None:
    output_path = tmp_path / "coverage.json"

    report = run_coverage_rescore(
        experiences_path=CORPUS_PATH,
        development_cases_path=DEVELOPMENT_PATH,
        source_report_path=PROMPT_V2_REPORT_PATH,
        output_path=output_path,
        git_revision="test-revision",
    )

    assert report.provider_request_attempt_count == 0
    assert report.evaluation_version == "evidence-matcher-coverage-v2"
    assert any("exact validation failure is unknown" in item for item in report.limitations)
    assert report.summary.case_count == 12
    assert report.summary.schema_valid_case_count == 11
    assert report.summary.matcher_only_coverage_accuracy.model_dump() == {
        "numerator": 9,
        "denominator": 12,
        "rate": 0.75,
    }
    assert report.summary.matcher_only_schema_valid_coverage_accuracy.numerator == 9
    assert report.summary.matcher_only_schema_valid_coverage_accuracy.denominator == 11
    assert report.summary.four_class_exact_accuracy.numerator == 8
    assert report.summary.four_class_exact_accuracy.denominator == 12
    assert report.summary.gap_subtype_difference_rate.numerator == 1
    assert report.summary.overclaim_rate.numerator == 1
    assert report.summary.overclaim_rate.denominator == 12
    assert report.summary.underclaim_rate.numerator == 1
    assert report.summary.gap_to_positive_rate.model_dump() == {
        "numerator": 0,
        "denominator": 6,
        "rate": 0.0,
    }
    assert report.summary.partial_to_matched_rate.numerator == 1
    assert report.summary.partial_to_matched_rate.denominator == 4
    assert report.summary.partial_to_gap_rate.numerator == 1
    assert report.summary.partial_to_gap_rate.denominator == 4
    assert report.summary.citation_validity_rate.numerator == 5
    assert report.summary.citation_validity_rate.denominator == 5
    assert report.summary.unsupported_positive_rate.numerator == 0
    assert report.summary.unsupported_positive_rate.denominator == 5
    assert report.summary.per_coverage["full"].support == 2
    assert report.summary.per_coverage["full"].correct == 2
    assert report.summary.per_coverage["partial"].support == 4
    assert report.summary.per_coverage["partial"].correct == 2
    assert report.summary.per_coverage["gap"].support == 6
    assert report.summary.per_coverage["gap"].correct == 5
    assert not report.acceptance.passed
    failed_gates = {gate.name for gate in report.acceptance.gates if not gate.passed}
    assert failed_gates == {
        "schema_pass",
        "output_failures",
        "coverage_overclaim",
        "acceptable_evidence",
        "matcher_only_coverage",
        "partial_to_gap",
    }

    by_id = {case.case_id: case for case in report.cases}
    assert by_id["matcher-dev-004"].matcher_only_coverage_correct
    assert not by_id["matcher-dev-004"].four_class_exact
    assert (
        by_id["matcher-dev-004"].direction
        is CoverageDirection.GAP_SUBTYPE_DIFFERENCE
    )
    assert by_id["matcher-dev-008"].direction is CoverageDirection.OUTPUT_FAILURE
    assert by_id["matcher-dev-008"].predicted_coverage is None
    assert by_id["matcher-dev-009"].direction is CoverageDirection.PARTIAL_TO_GAP
    assert by_id["matcher-dev-010"].direction is CoverageDirection.PARTIAL_TO_FULL
    assert output_path.exists()

    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        run_coverage_rescore(
            experiences_path=CORPUS_PATH,
            development_cases_path=DEVELOPMENT_PATH,
            source_report_path=PROMPT_V2_REPORT_PATH,
            output_path=output_path,
            git_revision="test-revision",
        )


@pytest.mark.parametrize(
    ("expected", "predicted", "direction"),
    [
        (
            EvidenceVerdict.MISSING,
            EvidenceVerdict.PARTIAL,
            CoverageDirection.GAP_TO_PARTIAL,
        ),
        (
            EvidenceVerdict.INSUFFICIENT_EVIDENCE,
            EvidenceVerdict.MATCHED,
            CoverageDirection.GAP_TO_FULL,
        ),
        (
            EvidenceVerdict.PARTIAL,
            EvidenceVerdict.MATCHED,
            CoverageDirection.PARTIAL_TO_FULL,
        ),
        (
            EvidenceVerdict.PARTIAL,
            EvidenceVerdict.MISSING,
            CoverageDirection.PARTIAL_TO_GAP,
        ),
    ],
)
def test_coverage_direction_separates_overclaim_and_underclaim(
    expected: EvidenceVerdict,
    predicted: EvidenceVerdict,
    direction: CoverageDirection,
) -> None:
    assert (
        coverage_direction(
            expected_verdict=expected,
            predicted_verdict=predicted,
            error_type=None,
        )
        is direction
    )


def test_coverage_rescore_refuses_holdout_before_source_read(tmp_path: Path) -> None:
    corpus, _ = load_corpus(CORPUS_PATH)
    development, _ = load_matcher_dataset(DEVELOPMENT_PATH, corpus)
    toy_holdout = development.model_copy(update={"split": RetrievalSplit.HOLDOUT})
    toy_holdout_path = tmp_path / "toy-holdout.json"
    toy_holdout_path.write_text(toy_holdout.model_dump_json(indent=2), encoding="utf-8")

    with pytest.raises(RuntimeError, match="development data only"):
        run_coverage_rescore(
            experiences_path=CORPUS_PATH,
            development_cases_path=toy_holdout_path,
            source_report_path=tmp_path / "missing.json",
            output_path=tmp_path / "report.json",
            git_revision="test-revision",
        )
