from __future__ import annotations

from collections import Counter
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from careerops.domain.evidence_matching import EvidenceVerdict
from careerops.evaluation.evidence_matcher import (
    MatcherCaseResult,
    MatcherEvalCase,
    candidate_conditioned_verdict,
    oracle_verdict,
)


class CoverageClass(StrEnum):
    FULL = "full"
    PARTIAL = "partial"
    GAP = "gap"


class CoverageDirection(StrEnum):
    EXACT = "exact"
    GAP_SUBTYPE_DIFFERENCE = "gap_subtype_difference"
    GAP_TO_PARTIAL = "gap_to_partial"
    GAP_TO_FULL = "gap_to_full"
    PARTIAL_TO_FULL = "partial_to_full"
    PARTIAL_TO_GAP = "partial_to_gap"
    FULL_TO_PARTIAL = "full_to_partial"
    FULL_TO_GAP = "full_to_gap"
    PROVIDER_FAILURE = "provider_failure"
    OUTPUT_FAILURE = "output_failure"


class CountRate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    numerator: int
    denominator: int
    rate: float


class CoverageClassMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    support: int
    correct: int
    recall: float


class CoverageGateResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    category: str
    passed: bool
    observed: str
    required: str


class CoverageAcceptance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy_version: str
    safety_passed: bool
    quality_passed: bool
    passed: bool
    gates: tuple[CoverageGateResult, ...]


class CoverageCaseResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    oracle_verdict: EvidenceVerdict
    candidate_conditioned_verdict: EvidenceVerdict
    predicted_verdict: EvidenceVerdict | None
    oracle_coverage: CoverageClass
    candidate_conditioned_coverage: CoverageClass
    predicted_coverage: CoverageClass | None
    end_to_end_coverage_correct: bool
    matcher_only_coverage_correct: bool
    four_class_exact: bool
    direction: CoverageDirection
    error_type: str | None


class CoverageSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_count: int
    schema_valid_case_count: int
    provider_failure_count: int
    output_failure_count: int
    end_to_end_coverage_accuracy: CountRate
    matcher_only_coverage_accuracy: CountRate
    matcher_only_schema_valid_coverage_accuracy: CountRate
    four_class_exact_accuracy: CountRate
    gap_subtype_difference_rate: CountRate
    overclaim_rate: CountRate
    underclaim_rate: CountRate
    gap_to_positive_rate: CountRate
    partial_to_matched_rate: CountRate
    partial_to_gap_rate: CountRate
    citation_validity_rate: CountRate
    unsupported_positive_rate: CountRate
    per_coverage: dict[CoverageClass, CoverageClassMetrics]
    direction_counts: dict[CoverageDirection, int]
    failure_policy: tuple[str, ...]


def coverage_for_verdict(verdict: EvidenceVerdict) -> CoverageClass:
    if verdict is EvidenceVerdict.MATCHED:
        return CoverageClass.FULL
    if verdict is EvidenceVerdict.PARTIAL:
        return CoverageClass.PARTIAL
    return CoverageClass.GAP


def score_coverage_cases(
    cases: list[MatcherEvalCase],
    results: list[MatcherCaseResult],
) -> tuple[list[CoverageCaseResult], CoverageSummary]:
    if [case.case_id for case in cases] != [result.case_id for result in results]:
        raise ValueError("Coverage rescore cases do not match source result order.")
    scored = [
        score_coverage_case(case, result)
        for case, result in zip(cases, results, strict=True)
    ]
    return scored, summarize_coverage(scored, results)


def score_coverage_case(
    case: MatcherEvalCase,
    result: MatcherCaseResult,
) -> CoverageCaseResult:
    oracle_expected = oracle_verdict(case)
    candidate_expected = candidate_conditioned_verdict(case)
    predicted = result.raw_verdict if result.error_type is None else None
    oracle_coverage = coverage_for_verdict(oracle_expected)
    candidate_coverage = coverage_for_verdict(candidate_expected)
    predicted_coverage = coverage_for_verdict(predicted) if predicted is not None else None
    direction = coverage_direction(
        expected_verdict=candidate_expected,
        predicted_verdict=predicted,
        error_type=result.error_type,
    )
    return CoverageCaseResult(
        case_id=case.case_id,
        oracle_verdict=oracle_expected,
        candidate_conditioned_verdict=candidate_expected,
        predicted_verdict=predicted,
        oracle_coverage=oracle_coverage,
        candidate_conditioned_coverage=candidate_coverage,
        predicted_coverage=predicted_coverage,
        end_to_end_coverage_correct=predicted_coverage is oracle_coverage,
        matcher_only_coverage_correct=predicted_coverage is candidate_coverage,
        four_class_exact=predicted is candidate_expected,
        direction=direction,
        error_type=result.error_type,
    )


def coverage_direction(
    *,
    expected_verdict: EvidenceVerdict,
    predicted_verdict: EvidenceVerdict | None,
    error_type: str | None,
) -> CoverageDirection:
    if error_type is not None:
        if error_type.startswith("provider_"):
            return CoverageDirection.PROVIDER_FAILURE
        return CoverageDirection.OUTPUT_FAILURE
    if predicted_verdict is None:
        raise ValueError("A schema-valid coverage result requires a verdict.")
    if predicted_verdict is expected_verdict:
        return CoverageDirection.EXACT

    expected = coverage_for_verdict(expected_verdict)
    predicted = coverage_for_verdict(predicted_verdict)
    if expected is CoverageClass.GAP and predicted is CoverageClass.GAP:
        return CoverageDirection.GAP_SUBTYPE_DIFFERENCE
    mapping = {
        (CoverageClass.GAP, CoverageClass.PARTIAL): CoverageDirection.GAP_TO_PARTIAL,
        (CoverageClass.GAP, CoverageClass.FULL): CoverageDirection.GAP_TO_FULL,
        (CoverageClass.PARTIAL, CoverageClass.FULL): CoverageDirection.PARTIAL_TO_FULL,
        (CoverageClass.PARTIAL, CoverageClass.GAP): CoverageDirection.PARTIAL_TO_GAP,
        (CoverageClass.FULL, CoverageClass.PARTIAL): CoverageDirection.FULL_TO_PARTIAL,
        (CoverageClass.FULL, CoverageClass.GAP): CoverageDirection.FULL_TO_GAP,
    }
    return mapping[(expected, predicted)]


def summarize_coverage(
    scored: list[CoverageCaseResult],
    source_results: list[MatcherCaseResult],
) -> CoverageSummary:
    schema_valid = [item for item in scored if item.error_type is None]
    expected_gap = [
        item for item in scored if item.candidate_conditioned_coverage is CoverageClass.GAP
    ]
    expected_partial = [
        item
        for item in scored
        if item.candidate_conditioned_coverage is CoverageClass.PARTIAL
    ]
    positive_results = [
        result
        for result in source_results
        if result.error_type is None
        and result.raw_verdict in {EvidenceVerdict.MATCHED, EvidenceVerdict.PARTIAL}
    ]
    direction_counts = Counter(item.direction for item in scored)
    overclaim_directions = {
        CoverageDirection.GAP_TO_PARTIAL,
        CoverageDirection.GAP_TO_FULL,
        CoverageDirection.PARTIAL_TO_FULL,
    }
    underclaim_directions = {
        CoverageDirection.PARTIAL_TO_GAP,
        CoverageDirection.FULL_TO_PARTIAL,
        CoverageDirection.FULL_TO_GAP,
    }
    return CoverageSummary(
        case_count=len(scored),
        schema_valid_case_count=len(schema_valid),
        provider_failure_count=direction_counts[CoverageDirection.PROVIDER_FAILURE],
        output_failure_count=direction_counts[CoverageDirection.OUTPUT_FAILURE],
        end_to_end_coverage_accuracy=_count_rate(
            sum(item.end_to_end_coverage_correct for item in scored), len(scored)
        ),
        matcher_only_coverage_accuracy=_count_rate(
            sum(item.matcher_only_coverage_correct for item in scored), len(scored)
        ),
        matcher_only_schema_valid_coverage_accuracy=_count_rate(
            sum(item.matcher_only_coverage_correct for item in schema_valid),
            len(schema_valid),
        ),
        four_class_exact_accuracy=_count_rate(
            sum(item.four_class_exact for item in scored), len(scored)
        ),
        gap_subtype_difference_rate=_count_rate(
            direction_counts[CoverageDirection.GAP_SUBTYPE_DIFFERENCE], len(scored)
        ),
        overclaim_rate=_count_rate(
            sum(direction_counts[item] for item in overclaim_directions), len(scored)
        ),
        underclaim_rate=_count_rate(
            sum(direction_counts[item] for item in underclaim_directions), len(scored)
        ),
        gap_to_positive_rate=_count_rate(
            direction_counts[CoverageDirection.GAP_TO_PARTIAL]
            + direction_counts[CoverageDirection.GAP_TO_FULL],
            len(expected_gap),
        ),
        partial_to_matched_rate=_count_rate(
            direction_counts[CoverageDirection.PARTIAL_TO_FULL],
            len(expected_partial),
        ),
        partial_to_gap_rate=_count_rate(
            direction_counts[CoverageDirection.PARTIAL_TO_GAP],
            len(expected_partial),
        ),
        citation_validity_rate=_count_rate(
            sum(result.citation_valid is True for result in positive_results),
            len(positive_results),
        ),
        unsupported_positive_rate=_count_rate(
            sum(result.unsupported_positive_claim for result in positive_results),
            len(positive_results),
        ),
        per_coverage={
            coverage: _coverage_class_metrics(scored, coverage)
            for coverage in CoverageClass
        },
        direction_counts={
            direction: direction_counts[direction] for direction in CoverageDirection
        },
        failure_policy=(
            "Primary coverage and four-class metrics use every case as the denominator.",
            "Provider and output failures count as incorrect and are never inferred as gaps.",
            "The schema-valid coverage metric excludes failures only as a diagnostic.",
            "Gap subtype differences are coverage-correct but remain four-class diagnostics.",
        ),
    )


def evaluate_coverage_acceptance(
    summary: CoverageSummary,
    *,
    acceptable_evidence_accuracy: float,
) -> CoverageAcceptance:
    gates = (
        _gate(
            "schema_pass",
            "safety",
            summary.schema_valid_case_count == summary.case_count,
            f"{summary.schema_valid_case_count}/{summary.case_count}",
            f"{summary.case_count}/{summary.case_count}",
        ),
        _gate(
            "provider_failures",
            "safety",
            summary.provider_failure_count == 0,
            str(summary.provider_failure_count),
            "0",
        ),
        _gate(
            "output_failures",
            "safety",
            summary.output_failure_count == 0,
            str(summary.output_failure_count),
            "0",
        ),
        _gate(
            "citation_validity",
            "safety",
            summary.citation_validity_rate.denominator > 0
            and summary.citation_validity_rate.numerator
            == summary.citation_validity_rate.denominator,
            _format_rate(summary.citation_validity_rate),
            "all emitted positives",
        ),
        _gate(
            "unsupported_positive",
            "safety",
            summary.unsupported_positive_rate.numerator == 0,
            _format_rate(summary.unsupported_positive_rate),
            "0 unsupported positives",
        ),
        _gate(
            "coverage_overclaim",
            "safety",
            summary.overclaim_rate.numerator == 0,
            _format_rate(summary.overclaim_rate),
            "0 overclaims",
        ),
        _gate(
            "acceptable_evidence",
            "quality",
            acceptable_evidence_accuracy == 1.0,
            f"{acceptable_evidence_accuracy:.4f}",
            "1.0000",
        ),
        _gate(
            "matcher_only_coverage",
            "quality",
            summary.matcher_only_coverage_accuracy.numerator >= 10
            and summary.matcher_only_coverage_accuracy.denominator == 12,
            _format_rate(summary.matcher_only_coverage_accuracy),
            ">=10/12",
        ),
        _gate(
            "partial_to_gap",
            "quality",
            summary.partial_to_gap_rate.numerator == 0,
            _format_rate(summary.partial_to_gap_rate),
            "0 partial-to-gap",
        ),
        *(
            _gate(
                f"{coverage.value}_recall_nonzero",
                "quality",
                metrics.correct > 0,
                f"{metrics.correct}/{metrics.support}",
                ">0 correct",
            )
            for coverage, metrics in summary.per_coverage.items()
        ),
    )
    safety_passed = all(gate.passed for gate in gates if gate.category == "safety")
    quality_passed = all(gate.passed for gate in gates if gate.category == "quality")
    return CoverageAcceptance(
        policy_version="evidence-matcher-development-gates-v4",
        safety_passed=safety_passed,
        quality_passed=quality_passed,
        passed=safety_passed and quality_passed,
        gates=gates,
    )


def _count_rate(numerator: int, denominator: int) -> CountRate:
    return CountRate(
        numerator=numerator,
        denominator=denominator,
        rate=numerator / denominator if denominator else 0.0,
    )


def _coverage_class_metrics(
    scored: list[CoverageCaseResult],
    coverage: CoverageClass,
) -> CoverageClassMetrics:
    expected = [
        item for item in scored if item.candidate_conditioned_coverage is coverage
    ]
    correct = sum(item.matcher_only_coverage_correct for item in expected)
    return CoverageClassMetrics(
        support=len(expected),
        correct=correct,
        recall=correct / len(expected) if expected else 0.0,
    )


def _gate(
    name: str,
    category: str,
    passed: bool,
    observed: str,
    required: str,
) -> CoverageGateResult:
    return CoverageGateResult(
        name=name,
        category=category,
        passed=passed,
        observed=observed,
        required=required,
    )


def _format_rate(value: CountRate) -> str:
    return f"{value.numerator}/{value.denominator} ({value.rate:.4f})"
