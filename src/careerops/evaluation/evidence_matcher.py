from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from datetime import datetime
from enum import StrEnum
from hashlib import sha256
from pathlib import Path
from time import perf_counter
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from careerops.domain.analysis_runs import AnalysisInput
from careerops.domain.errors import EvidenceMatcherError, MatcherOutputValidationError
from careerops.domain.evidence_matching import (
    MATCHER_PROMPT_VERSION,
    EvidenceVerdict,
    ProposedEvidenceMatch,
    derive_quote_span,
)
from careerops.domain.evidence_retrieval import EvidenceCandidate, RequirementCandidateSet
from careerops.evaluation.evidence_retrieval import (
    EVALUATION_USER_ID,
    RetrievalEvalExperience,
    RetrievalEvalRequirement,
    mean,
    to_experience_record,
    to_requirement_record,
)
from careerops.evaluation.evidence_retrieval_v2 import (
    RetrievalProfile,
    RetrievalSplit,
    RetrievalV2Corpus,
    ReviewStatus,
)
from careerops.services.analysis_run_execution import EvidenceMatcher, validate_matcher_output
from careerops.services.evidence_matcher_contract import build_evidence_matcher_input


class MatcherEvalTag(StrEnum):
    HARD_NEGATIVE = "hard_negative"
    COMPOSITE = "composite"
    MULTILINGUAL = "multilingual"
    PROMPT_INJECTION = "prompt_injection"
    RETRIEVAL_MISS = "retrieval_miss"


class GapReasonCode(StrEnum):
    REQUIRED_TECHNOLOGY_ABSENT = "required_technology_absent"
    FUTURE_PLAN_ONLY = "future_plan_only"
    LEARNING_OR_DISCUSSION_ONLY = "learning_or_discussion_only"
    EXPLICIT_NON_IMPLEMENTATION = "explicit_non_implementation"
    METRIC_NOT_PROVEN = "metric_not_proven"


class EvidenceTarget(StrEnum):
    ORACLE = "oracle"
    CANDIDATE_CONDITIONED = "candidate_conditioned"


class CaseShape(StrEnum):
    ATOMIC = "atomic"
    COMPOSITE = "composite"


class ExpectedPositiveMatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verdict: Literal["matched", "partial"]
    experience_id: UUID
    experience_version: int = Field(ge=1)
    source_ref: str = Field(min_length=1)
    quote: str = Field(min_length=1)


class ExpectedGapMatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verdict: Literal["missing", "insufficient_evidence"]


ExpectedMatch = Annotated[
    ExpectedPositiveMatch | ExpectedGapMatch,
    Field(discriminator="verdict"),
]


class EvidenceReferenceLabel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    experience_id: UUID
    experience_version: int = Field(ge=1)
    source_ref: str = Field(min_length=1)
    quote: str = Field(min_length=1)


class AcceptableEvidence(EvidenceReferenceLabel):
    valid_for: list[EvidenceTarget] = Field(min_length=1)


class MatcherEvalCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(min_length=1)
    profile_id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    requirement: RetrievalEvalRequirement
    candidate_experience_ids: list[UUID] = Field(max_length=5)
    expected: ExpectedMatch | None = None
    oracle_verdict: EvidenceVerdict | None = None
    candidate_conditioned_verdict: EvidenceVerdict | None = None
    oracle_gap_reason_code: GapReasonCode | None = None
    candidate_gap_reason_code: GapReasonCode | None = None
    acceptable_evidence: list[AcceptableEvidence] = Field(default_factory=list)
    canonical_evidence: list[AcceptableEvidence] = Field(default_factory=list)
    rationale: str = Field(min_length=1)
    tags: list[MatcherEvalTag] = Field(min_length=1)


class MatcherEvalDataset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    version: int = Field(ge=1)
    split: RetrievalSplit
    cases: list[MatcherEvalCase] = Field(min_length=1)


class MatcherReviewManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    version: int = Field(ge=1)
    status: ReviewStatus
    reviewer: str | None
    reviewed_at: datetime | None
    corpus_sha256: str = Field(min_length=64, max_length=64)
    development_cases_sha256: str = Field(min_length=64, max_length=64)
    holdout_cases_sha256: str = Field(min_length=64, max_length=64)
    notes: list[str]


class VerdictMetrics(BaseModel):
    support: int
    precision: float
    recall: float
    f1: float


class MatcherCaseResult(BaseModel):
    case_id: str
    profile_id: str
    description: str
    tags: list[MatcherEvalTag]
    matcher_eligible: bool
    expected_verdict: EvidenceVerdict
    raw_verdict: EvidenceVerdict | None
    raw_experience_id: UUID | None
    raw_experience_version: int | None
    raw_source_ref: str | None
    raw_quote: str | None
    validated_verdict: EvidenceVerdict | None
    predicted_experience_id: UUID | None
    predicted_experience_version: int | None
    predicted_source_ref: str | None
    predicted_quote: str | None
    confidence: float | None
    exact_match: bool
    positive_evidence_exact: bool | None
    citation_valid: bool | None
    unsupported_positive_claim: bool
    error_type: str | None
    model_name: str | None
    input_tokens: int | None
    output_tokens: int | None
    latency_ms: int
    oracle_expected_verdict: EvidenceVerdict | None = None
    candidate_conditioned_expected_verdict: EvidenceVerdict | None = None
    case_shape: CaseShape = CaseShape.ATOMIC
    end_to_end_verdict_correct: bool = False
    matcher_only_verdict_correct: bool = False
    end_to_end_experience_id_correct: bool | None = None
    matcher_only_experience_id_correct: bool | None = None
    end_to_end_source_correct: bool | None = None
    matcher_only_source_correct: bool | None = None
    end_to_end_acceptable_evidence_correct: bool | None = None
    matcher_only_acceptable_evidence_correct: bool | None = None
    end_to_end_canonical_quote_exact: bool | None = None
    matcher_only_canonical_quote_exact: bool | None = None
    error_diagnostic: str | None = None
    response_sha256: str | None = None
    response_size_bytes: int | None = None


class MatcherEvalSummary(BaseModel):
    case_count: int
    completed_case_count: int
    provider_failure_count: int
    output_failure_count: int
    matcher_eligible_count: int
    retrieval_miss_count: int
    schema_pass_rate: float
    end_to_end_verdict_accuracy: float
    matcher_only_verdict_accuracy: float
    end_to_end_macro_f1: float
    matcher_only_macro_f1: float
    end_to_end_exact_match_rate: float
    matcher_only_exact_match_rate: float
    end_to_end_positive_evidence_exact_accuracy: float
    matcher_only_positive_evidence_exact_accuracy: float
    gap_accuracy: float
    citation_validity_rate: float
    unsupported_positive_claim_rate: float
    confidence_case_count: int
    verdict_confidence_brier_score: float | None
    total_input_tokens: int
    total_output_tokens: int
    mean_latency_ms: float
    per_verdict: dict[EvidenceVerdict, VerdictMetrics]
    end_to_end_per_verdict: dict[EvidenceVerdict, VerdictMetrics] = Field(
        default_factory=dict
    )
    matcher_only_per_verdict: dict[EvidenceVerdict, VerdictMetrics] = Field(
        default_factory=dict
    )
    end_to_end_experience_id_accuracy: float = 0.0
    matcher_only_experience_id_accuracy: float = 0.0
    end_to_end_source_accuracy: float = 0.0
    matcher_only_source_accuracy: float = 0.0
    end_to_end_acceptable_evidence_accuracy: float = 0.0
    matcher_only_acceptable_evidence_accuracy: float = 0.0
    end_to_end_canonical_quote_exact_agreement: float = 0.0
    matcher_only_canonical_quote_exact_agreement: float = 0.0
    end_to_end_atomic_verdict_accuracy: float = 0.0
    matcher_only_atomic_verdict_accuracy: float = 0.0
    end_to_end_composite_verdict_accuracy: float = 0.0
    matcher_only_composite_verdict_accuracy: float = 0.0
    verdict_error_attribution: dict[str, int] = Field(default_factory=dict)


def load_matcher_dataset(
    path: Path,
    corpus: RetrievalV2Corpus,
) -> tuple[MatcherEvalDataset, str]:
    content = path.read_bytes()
    dataset = MatcherEvalDataset.model_validate_json(content)
    validate_matcher_dataset(dataset, corpus)
    return dataset, sha256(content).hexdigest()


def load_matcher_review_manifest(path: Path) -> MatcherReviewManifest:
    return MatcherReviewManifest.model_validate_json(path.read_bytes())


def validate_matcher_review_manifest(
    manifest: MatcherReviewManifest,
    *,
    corpus_sha256: str,
    dataset_sha256: str,
    split: RetrievalSplit,
) -> None:
    if manifest.status is not ReviewStatus.APPROVED_FROZEN:
        raise ValueError("Matcher labels have not been approved and frozen by the author.")
    if manifest.reviewer is None or manifest.reviewer.strip() == "":
        raise ValueError("An approved matcher manifest requires a reviewer.")
    if manifest.reviewed_at is None:
        raise ValueError("An approved matcher manifest requires a review timestamp.")
    if manifest.corpus_sha256 != corpus_sha256:
        raise ValueError("The reviewed matcher corpus hash does not match the current file.")
    expected_hash = (
        manifest.development_cases_sha256
        if split is RetrievalSplit.DEVELOPMENT
        else manifest.holdout_cases_sha256
    )
    if expected_hash != dataset_sha256:
        raise ValueError("The reviewed matcher case hash does not match the current file.")


def validate_matcher_dataset(
    dataset: MatcherEvalDataset,
    corpus: RetrievalV2Corpus,
) -> None:
    case_ids = [case.case_id for case in dataset.cases]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("Matcher case IDs must be unique within a split.")
    requirement_ids = [case.requirement.id for case in dataset.cases]
    if len(requirement_ids) != len(set(requirement_ids)):
        raise ValueError("Matcher requirement IDs must be unique within a split.")

    profiles = {profile.profile_id: profile for profile in corpus.profiles}
    for case in dataset.cases:
        profile = profiles.get(case.profile_id)
        if profile is None:
            raise ValueError(f"Matcher case {case.case_id} references an unknown profile.")
        experiences = {item.id: item for item in profile.experiences}
        if len(case.candidate_experience_ids) != len(set(case.candidate_experience_ids)):
            raise ValueError(f"Matcher candidates must be unique in case {case.case_id}.")
        if set(case.candidate_experience_ids) - set(experiences):
            raise ValueError(f"Matcher case {case.case_id} has a cross-profile candidate.")
        if len(case.tags) != len(set(case.tags)):
            raise ValueError(f"Matcher tags must be unique in case {case.case_id}.")

        if case.oracle_verdict is not None or case.candidate_conditioned_verdict is not None:
            _validate_v2_case(case, experiences)
            continue
        if case.expected is None:
            raise ValueError(f"Matcher case {case.case_id} has no verdict labels.")
        if isinstance(case.expected, ExpectedPositiveMatch):
            expected_experience = experiences.get(case.expected.experience_id)
            if expected_experience is None:
                raise ValueError(f"Matcher case {case.case_id} has cross-profile gold evidence.")
            record = to_experience_record(expected_experience)
            if case.expected.experience_version != record.version:
                raise ValueError(f"Matcher case {case.case_id} has a stale gold version.")
            if (
                derive_quote_span(
                    case.expected.source_ref,
                    case.expected.quote,
                    record,
                )
                is None
            ):
                raise ValueError(f"Matcher case {case.case_id} has an ungrounded gold quote.")
            candidate_has_gold = case.expected.experience_id in case.candidate_experience_ids
            tagged_miss = MatcherEvalTag.RETRIEVAL_MISS in case.tags
            if candidate_has_gold == tagged_miss:
                raise ValueError(
                    f"Matcher case {case.case_id} retrieval-miss tag disagrees with candidates."
                )
        elif MatcherEvalTag.RETRIEVAL_MISS in case.tags:
            raise ValueError(f"Gap case {case.case_id} cannot be a retrieval miss.")


def _validate_v2_case(
    case: MatcherEvalCase,
    experiences: dict[UUID, RetrievalEvalExperience],
) -> None:
    if case.expected is not None:
        raise ValueError(f"Matcher v2 case {case.case_id} cannot retain legacy expected.")
    if case.oracle_verdict is None or case.candidate_conditioned_verdict is None:
        raise ValueError(f"Matcher v2 case {case.case_id} requires both verdict labels.")

    for target, verdict, reason in (
        (EvidenceTarget.ORACLE, case.oracle_verdict, case.oracle_gap_reason_code),
        (
            EvidenceTarget.CANDIDATE_CONDITIONED,
            case.candidate_conditioned_verdict,
            case.candidate_gap_reason_code,
        ),
    ):
        positive = verdict in {EvidenceVerdict.MATCHED, EvidenceVerdict.PARTIAL}
        target_evidence = [
            evidence for evidence in case.acceptable_evidence if target in evidence.valid_for
        ]
        if positive and not target_evidence:
            raise ValueError(
                f"Matcher v2 case {case.case_id} positive {target.value} label needs evidence."
            )
        if not positive and target_evidence:
            raise ValueError(
                f"Matcher v2 case {case.case_id} gap {target.value} label has evidence."
            )
        if positive and reason is not None:
            raise ValueError(
                f"Matcher v2 case {case.case_id} positive {target.value} label has gap reason."
            )
        if not positive and reason is None:
            raise ValueError(
                f"Matcher v2 case {case.case_id} gap {target.value} label needs reason."
            )

    for evidence in (*case.acceptable_evidence, *case.canonical_evidence):
        experience = experiences.get(evidence.experience_id)
        if experience is None:
            raise ValueError(f"Matcher v2 case {case.case_id} has cross-profile evidence.")
        record = to_experience_record(experience)
        if evidence.experience_version != record.version:
            raise ValueError(f"Matcher v2 case {case.case_id} has stale evidence version.")
        if derive_quote_span(evidence.source_ref, evidence.quote, record) is None:
            raise ValueError(f"Matcher v2 case {case.case_id} has an ungrounded evidence quote.")
        if len(evidence.valid_for) != len(set(evidence.valid_for)):
            raise ValueError(f"Matcher v2 case {case.case_id} has duplicate evidence targets.")
        if (
            EvidenceTarget.CANDIDATE_CONDITIONED in evidence.valid_for
            and evidence.experience_id not in case.candidate_experience_ids
        ):
            raise ValueError(
                f"Matcher v2 case {case.case_id} candidate evidence is not a candidate."
            )

    acceptable_keys = {
        (
            evidence.experience_id,
            evidence.experience_version,
            evidence.source_ref,
            evidence.quote,
            target,
        )
        for evidence in case.acceptable_evidence
        for target in evidence.valid_for
    }
    for evidence in case.canonical_evidence:
        for target in evidence.valid_for:
            if (
                evidence.experience_id,
                evidence.experience_version,
                evidence.source_ref,
                evidence.quote,
                target,
            ) not in acceptable_keys:
                raise ValueError(
                    f"Matcher v2 case {case.case_id} canonical evidence is not acceptable."
                )

    retrieval_miss = MatcherEvalTag.RETRIEVAL_MISS in case.tags
    oracle_candidate_ids = {
        evidence.experience_id
        for evidence in case.acceptable_evidence
        if EvidenceTarget.ORACLE in evidence.valid_for
    }
    oracle_evidence_available = bool(
        oracle_candidate_ids.intersection(case.candidate_experience_ids)
    )
    oracle_positive = case.oracle_verdict in {
        EvidenceVerdict.MATCHED,
        EvidenceVerdict.PARTIAL,
    }
    should_be_retrieval_miss = oracle_positive and not oracle_evidence_available
    if retrieval_miss != should_be_retrieval_miss:
        raise ValueError(
            f"Matcher v2 case {case.case_id} retrieval-miss tag disagrees with oracle evidence."
        )


def validate_matcher_acceptance_dataset(
    development: MatcherEvalDataset,
    holdout: MatcherEvalDataset,
) -> None:
    if development.split is not RetrievalSplit.DEVELOPMENT:
        raise ValueError("Matcher development file has the wrong split.")
    if holdout.split is not RetrievalSplit.HOLDOUT:
        raise ValueError("Matcher holdout file has the wrong split.")
    if len(development.cases) != 12 or len(holdout.cases) != 8:
        raise ValueError("Matcher v1 requires 12 development and 8 holdout cases.")

    all_case_ids = [case.case_id for case in (*development.cases, *holdout.cases)]
    if len(all_case_ids) != len(set(all_case_ids)):
        raise ValueError("Matcher case IDs must be unique across splits.")
    all_requirement_ids = [
        case.requirement.id for case in (*development.cases, *holdout.cases)
    ]
    if len(all_requirement_ids) != len(set(all_requirement_ids)):
        raise ValueError("Matcher requirement IDs must be unique across splits.")

    _validate_split_balance(development, per_verdict=3, multilingual=2, retrieval_misses=1)
    _validate_split_balance(holdout, per_verdict=2, multilingual=1, retrieval_misses=1)


def _validate_split_balance(
    dataset: MatcherEvalDataset,
    *,
    per_verdict: int,
    multilingual: int,
    retrieval_misses: int,
) -> None:
    verdicts = Counter(oracle_verdict(case) for case in dataset.cases)
    if any(verdicts[verdict] != per_verdict for verdict in EvidenceVerdict):
        raise ValueError("Matcher split must be balanced across all four verdicts.")
    if sum(MatcherEvalTag.MULTILINGUAL in case.tags for case in dataset.cases) < multilingual:
        raise ValueError("Matcher split has insufficient multilingual coverage.")
    if (
        sum(MatcherEvalTag.RETRIEVAL_MISS in case.tags for case in dataset.cases)
        != retrieval_misses
    ):
        raise ValueError("Matcher split has the wrong retrieval-miss count.")
    if not any(MatcherEvalTag.PROMPT_INJECTION in case.tags for case in dataset.cases):
        raise ValueError("Matcher split requires a prompt-injection case.")


def oracle_verdict(case: MatcherEvalCase) -> EvidenceVerdict:
    if case.oracle_verdict is not None:
        return case.oracle_verdict
    if case.expected is None:
        raise ValueError(f"Matcher case {case.case_id} has no oracle verdict.")
    return EvidenceVerdict(case.expected.verdict)


def candidate_conditioned_verdict(case: MatcherEvalCase) -> EvidenceVerdict:
    if case.candidate_conditioned_verdict is not None:
        return case.candidate_conditioned_verdict
    return oracle_verdict(case)


def case_shape(case: MatcherEvalCase) -> CaseShape:
    if MatcherEvalTag.COMPOSITE in case.tags:
        return CaseShape.COMPOSITE
    return CaseShape.ATOMIC


async def evaluate_matcher_dataset(
    corpus: RetrievalV2Corpus,
    dataset: MatcherEvalDataset,
    matcher: EvidenceMatcher,
    *,
    prompt_version: str = MATCHER_PROMPT_VERSION,
) -> list[MatcherCaseResult]:
    profiles = {profile.profile_id: profile for profile in corpus.profiles}
    return [
        await evaluate_matcher_case(
            case,
            profiles[case.profile_id],
            matcher,
            prompt_version=prompt_version,
        )
        for case in dataset.cases
    ]


async def evaluate_matcher_case(
    case: MatcherEvalCase,
    profile: RetrievalProfile,
    matcher: EvidenceMatcher,
    *,
    prompt_version: str = MATCHER_PROMPT_VERSION,
) -> MatcherCaseResult:
    profile_experiences = profile.experiences
    experiences = {
        item.id: to_experience_record(item) for item in profile_experiences
    }
    requirement = to_requirement_record(case.requirement)
    candidates = tuple(
        EvidenceCandidate(
            experience=experiences[experience_id],
            score=float(len(case.candidate_experience_ids) - rank),
        )
        for rank, experience_id in enumerate(case.candidate_experience_ids)
    )
    candidate_set = RequirementCandidateSet(requirement=requirement, candidates=candidates)
    matcher_eligible = True
    started = perf_counter()
    try:
        output = await matcher.match(
            build_evidence_matcher_input(
                (candidate_set,),
                prompt_version=prompt_version,
            )
        )
        validated = validate_matcher_output(
            output,
            (candidate_set,),
            EVALUATION_USER_ID,
            AnalysisInput(
                parse_input_fingerprint="evaluation",
                requirements=(requirement,),
                experiences=tuple(experiences.values()),
            ),
        )[0]
    except EvidenceMatcherError as exc:
        return failed_matcher_case_result(
            case,
            matcher_eligible=matcher_eligible,
            error_type=exc.reason.value,
            started=started,
        )
    except MatcherOutputValidationError as exc:
        return failed_matcher_case_result(
            case,
            matcher_eligible=matcher_eligible,
            error_type=exc.reason.value,
            started=started,
            error_diagnostic=exc.diagnostic,
            response_sha256=exc.response_sha256,
            response_size_bytes=exc.response_size_bytes,
            input_tokens=exc.input_tokens,
            output_tokens=exc.output_tokens,
        )

    proposal = output.matches[0]
    oracle_expected = oracle_verdict(case)
    candidate_expected = candidate_conditioned_verdict(case)
    predicted_positive = proposal.verdict in {EvidenceVerdict.MATCHED, EvidenceVerdict.PARTIAL}
    citation_valid = validated.quote_valid if predicted_positive else None
    end_to_end_experience_id_correct = _experience_id_correct(
        case, proposal, EvidenceTarget.ORACLE
    )
    matcher_only_experience_id_correct = _experience_id_correct(
        case, proposal, EvidenceTarget.CANDIDATE_CONDITIONED
    )
    end_to_end_source_correct = _source_correct(case, proposal, EvidenceTarget.ORACLE)
    matcher_only_source_correct = _source_correct(
        case, proposal, EvidenceTarget.CANDIDATE_CONDITIONED
    )
    end_to_end_acceptable = _acceptable_evidence_correct(
        case, proposal, EvidenceTarget.ORACLE
    )
    matcher_only_acceptable = _acceptable_evidence_correct(
        case, proposal, EvidenceTarget.CANDIDATE_CONDITIONED
    )
    end_to_end_canonical = _canonical_quote_exact(case, proposal, EvidenceTarget.ORACLE)
    matcher_only_canonical = _canonical_quote_exact(
        case, proposal, EvidenceTarget.CANDIDATE_CONDITIONED
    )
    matcher_only_verdict_correct = proposal.verdict is candidate_expected
    exact_match = matcher_only_verdict_correct and matcher_only_acceptable is not False
    return MatcherCaseResult(
        case_id=case.case_id,
        profile_id=case.profile_id,
        description=case.description,
        tags=case.tags,
        matcher_eligible=matcher_eligible,
        expected_verdict=oracle_expected,
        raw_verdict=proposal.verdict,
        raw_experience_id=proposal.experience_id,
        raw_experience_version=proposal.experience_version,
        raw_source_ref=proposal.source_ref,
        raw_quote=proposal.quote,
        validated_verdict=validated.verdict,
        predicted_experience_id=validated.experience_id,
        predicted_experience_version=validated.experience_version,
        predicted_source_ref=proposal.source_ref if validated.quote_valid else None,
        predicted_quote=validated.quote,
        confidence=proposal.confidence,
        exact_match=exact_match,
        positive_evidence_exact=matcher_only_canonical,
        citation_valid=citation_valid,
        unsupported_positive_claim=predicted_positive and validated.validation_failed,
        error_type=None,
        model_name=output.model_name,
        input_tokens=output.input_tokens,
        output_tokens=output.output_tokens,
        latency_ms=elapsed_milliseconds(started),
        oracle_expected_verdict=oracle_expected,
        candidate_conditioned_expected_verdict=candidate_expected,
        case_shape=case_shape(case),
        end_to_end_verdict_correct=proposal.verdict is oracle_expected,
        matcher_only_verdict_correct=matcher_only_verdict_correct,
        end_to_end_experience_id_correct=end_to_end_experience_id_correct,
        matcher_only_experience_id_correct=matcher_only_experience_id_correct,
        end_to_end_source_correct=end_to_end_source_correct,
        matcher_only_source_correct=matcher_only_source_correct,
        end_to_end_acceptable_evidence_correct=end_to_end_acceptable,
        matcher_only_acceptable_evidence_correct=matcher_only_acceptable,
        end_to_end_canonical_quote_exact=end_to_end_canonical,
        matcher_only_canonical_quote_exact=matcher_only_canonical,
    )


def failed_matcher_case_result(
    case: MatcherEvalCase,
    *,
    matcher_eligible: bool,
    error_type: str,
    started: float,
    error_diagnostic: str | None = None,
    response_sha256: str | None = None,
    response_size_bytes: int | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
) -> MatcherCaseResult:
    return MatcherCaseResult(
        case_id=case.case_id,
        profile_id=case.profile_id,
        description=case.description,
        tags=case.tags,
        matcher_eligible=matcher_eligible,
        expected_verdict=oracle_verdict(case),
        raw_verdict=None,
        raw_experience_id=None,
        raw_experience_version=None,
        raw_source_ref=None,
        raw_quote=None,
        validated_verdict=None,
        predicted_experience_id=None,
        predicted_experience_version=None,
        predicted_source_ref=None,
        predicted_quote=None,
        confidence=None,
        exact_match=False,
        positive_evidence_exact=(
            False
            if candidate_conditioned_verdict(case)
            in {EvidenceVerdict.MATCHED, EvidenceVerdict.PARTIAL}
            else None
        ),
        citation_valid=None,
        unsupported_positive_claim=False,
        error_type=error_type,
        model_name=None,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=elapsed_milliseconds(started),
        oracle_expected_verdict=oracle_verdict(case),
        candidate_conditioned_expected_verdict=candidate_conditioned_verdict(case),
        case_shape=case_shape(case),
        end_to_end_experience_id_correct=(
            False
            if oracle_verdict(case) in {EvidenceVerdict.MATCHED, EvidenceVerdict.PARTIAL}
            else None
        ),
        matcher_only_experience_id_correct=(
            False
            if candidate_conditioned_verdict(case)
            in {EvidenceVerdict.MATCHED, EvidenceVerdict.PARTIAL}
            else None
        ),
        end_to_end_source_correct=(
            False
            if oracle_verdict(case) in {EvidenceVerdict.MATCHED, EvidenceVerdict.PARTIAL}
            else None
        ),
        matcher_only_source_correct=(
            False
            if candidate_conditioned_verdict(case)
            in {EvidenceVerdict.MATCHED, EvidenceVerdict.PARTIAL}
            else None
        ),
        end_to_end_acceptable_evidence_correct=(
            False
            if oracle_verdict(case) in {EvidenceVerdict.MATCHED, EvidenceVerdict.PARTIAL}
            else None
        ),
        matcher_only_acceptable_evidence_correct=(
            False
            if candidate_conditioned_verdict(case)
            in {EvidenceVerdict.MATCHED, EvidenceVerdict.PARTIAL}
            else None
        ),
        end_to_end_canonical_quote_exact=(
            False
            if oracle_verdict(case) in {EvidenceVerdict.MATCHED, EvidenceVerdict.PARTIAL}
            else None
        ),
        matcher_only_canonical_quote_exact=(
            False
            if candidate_conditioned_verdict(case)
            in {EvidenceVerdict.MATCHED, EvidenceVerdict.PARTIAL}
            else None
        ),
        error_diagnostic=error_diagnostic,
        response_sha256=response_sha256,
        response_size_bytes=response_size_bytes,
    )


def summarize_matcher_results(results: list[MatcherCaseResult]) -> MatcherEvalSummary:
    completed = [result for result in results if result.error_type is None]
    raw_positive = [result for result in completed if result.citation_valid is not None]
    oracle_positive_expected = [
        result
        for result in results
        if _result_expected_verdict(result, EvidenceTarget.ORACLE)
        in {EvidenceVerdict.MATCHED, EvidenceVerdict.PARTIAL}
    ]
    candidate_positive_expected = [
        result
        for result in results
        if _result_expected_verdict(result, EvidenceTarget.CANDIDATE_CONDITIONED)
        in {EvidenceVerdict.MATCHED, EvidenceVerdict.PARTIAL}
    ]
    gap_expected = [
        result
        for result in results
        if _result_expected_verdict(result, EvidenceTarget.CANDIDATE_CONDITIONED)
        in {EvidenceVerdict.MISSING, EvidenceVerdict.INSUFFICIENT_EVIDENCE}
    ]
    confidence_results = [
        result
        for result in completed
        if result.confidence is not None and result.raw_verdict is not None
    ]
    return MatcherEvalSummary(
        case_count=len(results),
        completed_case_count=len(completed),
        provider_failure_count=sum(
            result.error_type is not None and result.error_type.startswith("provider_")
            for result in results
        ),
        output_failure_count=sum(
            result.error_type in {"invalid_json", "invalid_schema", "invalid_contract"}
            for result in results
        ),
        matcher_eligible_count=len(results),
        retrieval_miss_count=sum(
            MatcherEvalTag.RETRIEVAL_MISS in result.tags for result in results
        ),
        schema_pass_rate=_ratio(len(completed), len(results)),
        end_to_end_verdict_accuracy=_verdict_accuracy(results, EvidenceTarget.ORACLE),
        matcher_only_verdict_accuracy=_verdict_accuracy(
            results, EvidenceTarget.CANDIDATE_CONDITIONED
        ),
        end_to_end_macro_f1=_macro_f1(results, EvidenceTarget.ORACLE),
        matcher_only_macro_f1=_macro_f1(
            results, EvidenceTarget.CANDIDATE_CONDITIONED
        ),
        end_to_end_exact_match_rate=_ratio(
            sum(
                result.end_to_end_verdict_correct
                and result.end_to_end_acceptable_evidence_correct is not False
                for result in results
            ),
            len(results),
        ),
        matcher_only_exact_match_rate=_ratio(
            sum(
                result.matcher_only_verdict_correct
                and result.matcher_only_acceptable_evidence_correct is not False
                for result in results
            ),
            len(results),
        ),
        end_to_end_positive_evidence_exact_accuracy=_ratio(
            sum(
                result.end_to_end_canonical_quote_exact is True
                for result in oracle_positive_expected
            ),
            len(oracle_positive_expected),
        ),
        matcher_only_positive_evidence_exact_accuracy=_ratio(
            sum(
                result.matcher_only_canonical_quote_exact is True
                for result in candidate_positive_expected
            ),
            len(candidate_positive_expected),
        ),
        gap_accuracy=_ratio(
            sum(result.matcher_only_verdict_correct for result in gap_expected),
            len(gap_expected),
        ),
        citation_validity_rate=_ratio(
            sum(result.citation_valid is True for result in raw_positive),
            len(raw_positive),
        ),
        unsupported_positive_claim_rate=_ratio(
            sum(result.unsupported_positive_claim for result in raw_positive),
            len(raw_positive),
        ),
        confidence_case_count=len(confidence_results),
        verdict_confidence_brier_score=(
            mean(
                [
                    (
                        result.confidence
                        - float(
                            result.raw_verdict
                            is _result_expected_verdict(
                                result, EvidenceTarget.CANDIDATE_CONDITIONED
                            )
                        )
                    )
                    ** 2
                    for result in confidence_results
                    if result.confidence is not None
                ]
            )
            if confidence_results
            else None
        ),
        total_input_tokens=sum(result.input_tokens or 0 for result in results),
        total_output_tokens=sum(result.output_tokens or 0 for result in results),
        mean_latency_ms=mean([float(result.latency_ms) for result in completed]),
        per_verdict={
            verdict: _verdict_metrics(results, verdict, EvidenceTarget.ORACLE)
            for verdict in EvidenceVerdict
        },
        end_to_end_per_verdict={
            verdict: _verdict_metrics(results, verdict, EvidenceTarget.ORACLE)
            for verdict in EvidenceVerdict
        },
        matcher_only_per_verdict={
            verdict: _verdict_metrics(
                results, verdict, EvidenceTarget.CANDIDATE_CONDITIONED
            )
            for verdict in EvidenceVerdict
        },
        end_to_end_experience_id_accuracy=_component_accuracy(
            oracle_positive_expected,
            lambda result: result.end_to_end_experience_id_correct,
        ),
        matcher_only_experience_id_accuracy=_component_accuracy(
            candidate_positive_expected,
            lambda result: result.matcher_only_experience_id_correct,
        ),
        end_to_end_source_accuracy=_component_accuracy(
            oracle_positive_expected,
            lambda result: result.end_to_end_source_correct,
        ),
        matcher_only_source_accuracy=_component_accuracy(
            candidate_positive_expected,
            lambda result: result.matcher_only_source_correct,
        ),
        end_to_end_acceptable_evidence_accuracy=_component_accuracy(
            oracle_positive_expected,
            lambda result: result.end_to_end_acceptable_evidence_correct,
        ),
        matcher_only_acceptable_evidence_accuracy=_component_accuracy(
            candidate_positive_expected,
            lambda result: result.matcher_only_acceptable_evidence_correct,
        ),
        end_to_end_canonical_quote_exact_agreement=_component_accuracy(
            oracle_positive_expected,
            lambda result: result.end_to_end_canonical_quote_exact,
        ),
        matcher_only_canonical_quote_exact_agreement=_component_accuracy(
            candidate_positive_expected,
            lambda result: result.matcher_only_canonical_quote_exact,
        ),
        end_to_end_atomic_verdict_accuracy=_shape_accuracy(
            results, CaseShape.ATOMIC, EvidenceTarget.ORACLE
        ),
        matcher_only_atomic_verdict_accuracy=_shape_accuracy(
            results, CaseShape.ATOMIC, EvidenceTarget.CANDIDATE_CONDITIONED
        ),
        end_to_end_composite_verdict_accuracy=_shape_accuracy(
            results, CaseShape.COMPOSITE, EvidenceTarget.ORACLE
        ),
        matcher_only_composite_verdict_accuracy=_shape_accuracy(
            results, CaseShape.COMPOSITE, EvidenceTarget.CANDIDATE_CONDITIONED
        ),
        verdict_error_attribution={
            "model_error": sum(
                result.error_type is None
                and not result.matcher_only_verdict_correct
                for result in results
            ),
            "retrieval_miss": sum(
                result.error_type is None
                and MatcherEvalTag.RETRIEVAL_MISS in result.tags
                and not result.end_to_end_verdict_correct
                and result.matcher_only_verdict_correct
                for result in results
            ),
            "canonical_quote_over_strict": sum(
                result.matcher_only_acceptable_evidence_correct is True
                and result.matcher_only_canonical_quote_exact is False
                for result in results
            ),
        },
    )


def _target_is_positive(case: MatcherEvalCase, target: EvidenceTarget) -> bool:
    verdict = (
        oracle_verdict(case)
        if target is EvidenceTarget.ORACLE
        else candidate_conditioned_verdict(case)
    )
    return verdict in {EvidenceVerdict.MATCHED, EvidenceVerdict.PARTIAL}


def _target_evidence(
    case: MatcherEvalCase,
    target: EvidenceTarget,
    *,
    canonical: bool = False,
) -> list[AcceptableEvidence]:
    evidence_items = case.canonical_evidence if canonical else case.acceptable_evidence
    if evidence_items:
        return [item for item in evidence_items if target in item.valid_for]
    if not isinstance(case.expected, ExpectedPositiveMatch):
        return []
    if target is EvidenceTarget.CANDIDATE_CONDITIONED and (
        case.expected.experience_id not in case.candidate_experience_ids
    ):
        return []
    return [
        AcceptableEvidence(
            experience_id=case.expected.experience_id,
            experience_version=case.expected.experience_version,
            source_ref=case.expected.source_ref,
            quote=case.expected.quote,
            valid_for=[target],
        )
    ]


def _experience_id_correct(
    case: MatcherEvalCase,
    proposal: ProposedEvidenceMatch,
    target: EvidenceTarget,
) -> bool | None:
    if not _target_is_positive(case, target):
        return None
    return any(
        proposal.experience_id == evidence.experience_id
        and proposal.experience_version == evidence.experience_version
        for evidence in _target_evidence(case, target)
    )


def _source_correct(
    case: MatcherEvalCase,
    proposal: ProposedEvidenceMatch,
    target: EvidenceTarget,
) -> bool | None:
    if not _target_is_positive(case, target):
        return None
    return any(
        proposal.experience_id == evidence.experience_id
        and proposal.experience_version == evidence.experience_version
        and proposal.source_ref == evidence.source_ref
        for evidence in _target_evidence(case, target)
    )


def _acceptable_evidence_correct(
    case: MatcherEvalCase,
    proposal: ProposedEvidenceMatch,
    target: EvidenceTarget,
) -> bool | None:
    if not _target_is_positive(case, target):
        return None
    return any(
        proposal.experience_id == evidence.experience_id
        and proposal.experience_version == evidence.experience_version
        and proposal.source_ref == evidence.source_ref
        and proposal.quote is not None
        and evidence.quote in proposal.quote
        for evidence in _target_evidence(case, target)
    )


def _canonical_quote_exact(
    case: MatcherEvalCase,
    proposal: ProposedEvidenceMatch,
    target: EvidenceTarget,
) -> bool | None:
    if not _target_is_positive(case, target):
        return None
    return any(
        proposal.experience_id == evidence.experience_id
        and proposal.experience_version == evidence.experience_version
        and proposal.source_ref == evidence.source_ref
        and proposal.quote == evidence.quote
        for evidence in _target_evidence(case, target, canonical=True)
    )


def _result_expected_verdict(
    result: MatcherCaseResult,
    target: EvidenceTarget,
) -> EvidenceVerdict:
    if target is EvidenceTarget.ORACLE:
        return result.oracle_expected_verdict or result.expected_verdict
    return result.candidate_conditioned_expected_verdict or result.expected_verdict


def _verdict_accuracy(
    results: list[MatcherCaseResult],
    target: EvidenceTarget,
) -> float:
    return _ratio(
        sum(
            result.raw_verdict is _result_expected_verdict(result, target)
            for result in results
        ),
        len(results),
    )


def _exact_match_rate(results: list[MatcherCaseResult]) -> float:
    return _ratio(sum(result.exact_match for result in results), len(results))


def _macro_f1(results: list[MatcherCaseResult], target: EvidenceTarget) -> float:
    return mean(
        [_verdict_metrics(results, verdict, target).f1 for verdict in EvidenceVerdict]
    )


def _verdict_metrics(
    results: list[MatcherCaseResult],
    verdict: EvidenceVerdict,
    target: EvidenceTarget,
) -> VerdictMetrics:
    true_positive = sum(
        _result_expected_verdict(result, target) is verdict and result.raw_verdict is verdict
        for result in results
    )
    predicted = sum(result.raw_verdict is verdict for result in results)
    support = sum(_result_expected_verdict(result, target) is verdict for result in results)
    precision = _ratio(true_positive, predicted)
    recall = _ratio(true_positive, support)
    return VerdictMetrics(
        support=support,
        precision=precision,
        recall=recall,
        f1=_ratio(2 * precision * recall, precision + recall),
    )


def _component_accuracy(
    results: list[MatcherCaseResult],
    selector: Callable[[MatcherCaseResult], bool | None],
) -> float:
    return _ratio(sum(selector(result) is True for result in results), len(results))


def _shape_accuracy(
    results: list[MatcherCaseResult],
    shape: CaseShape,
    target: EvidenceTarget,
) -> float:
    selected = [result for result in results if result.case_shape is shape]
    return _verdict_accuracy(selected, target)


def _ratio(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def elapsed_milliseconds(started: float) -> int:
    return int((perf_counter() - started) * 1_000)
