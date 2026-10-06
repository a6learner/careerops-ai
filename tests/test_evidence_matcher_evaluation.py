from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from uuid import UUID

import pytest

from careerops.domain.analysis_runs import EvidenceMatcherOutput
from careerops.domain.errors import (
    EvidenceMatcherError,
    EvidenceMatcherFailureReason,
    MatcherOutputFailureReason,
    MatcherOutputValidationError,
)
from careerops.domain.evidence_matching import (
    EvidenceMatcherInput,
    EvidenceVerdict,
    ProposedEvidenceMatch,
)
from careerops.evaluation.evidence_matcher import (
    EvidenceTarget,
    MatcherEvalDataset,
    candidate_conditioned_verdict,
    evaluate_matcher_dataset,
    load_matcher_dataset,
    load_matcher_review_manifest,
    summarize_matcher_results,
    validate_matcher_dataset,
    validate_matcher_review_manifest,
)
from careerops.evaluation.evidence_retrieval_v2 import (
    RetrievalSplit,
    RetrievalV2Corpus,
    ReviewStatus,
    load_corpus,
)
from careerops.evaluation.matcher_holdout import (
    MatcherHoldoutManifest,
    validate_holdout_manifest,
)
from careerops.evaluation.run_evidence_matcher import run

CORPUS_PATH = Path("evals/evidence_retrieval_v2/experiences.json")
DEVELOPMENT_PATH = Path("evals/evidence_matcher_v1/development_cases.json")
HOLDOUT_PATH = Path("evals/evidence_matcher_v1/holdout_cases.json")
MANIFEST_PATH = Path("evals/evidence_matcher_v1/review_manifest.json")
HOLDOUT_RUN_MANIFEST_PATH = Path(
    "evals/evidence_matcher_v1/holdout_v2_run_manifest.json"
)


class GoldMatcher:
    def __init__(self, dataset: MatcherEvalDataset) -> None:
        self._cases = {case.requirement.id: case for case in dataset.cases}

    @property
    def model_name(self) -> str:
        return "gold-test-matcher"

    async def match(self, matcher_input: EvidenceMatcherInput) -> EvidenceMatcherOutput:
        requirement_id = matcher_input.requirements[0].requirement_id
        case = self._cases[requirement_id]
        verdict = candidate_conditioned_verdict(case)
        acceptable = [
            item
            for item in case.acceptable_evidence
            if EvidenceTarget.CANDIDATE_CONDITIONED in item.valid_for
        ]
        evidence = acceptable[-1] if acceptable else None
        if verdict in {EvidenceVerdict.MATCHED, EvidenceVerdict.PARTIAL}:
            assert evidence is not None
            proposal = ProposedEvidenceMatch(
                requirement_id=requirement_id,
                verdict=verdict,
                experience_id=evidence.experience_id,
                experience_version=evidence.experience_version,
                source_ref=evidence.source_ref,
                quote=evidence.quote,
                confidence=0.9,
            )
        else:
            proposal = ProposedEvidenceMatch(
                requirement_id=requirement_id,
                verdict=verdict,
                experience_id=None,
                experience_version=None,
                quote=None,
                confidence=0.9,
            )
        return EvidenceMatcherOutput(model_name=self.model_name, matches=(proposal,))


class FailureMatcher:
    def __init__(self, error: Exception) -> None:
        self._error = error

    @property
    def model_name(self) -> str:
        return "failure-test-matcher"

    async def match(self, matcher_input: EvidenceMatcherInput) -> EvidenceMatcherOutput:
        raise self._error


def load_checked_data() -> tuple[RetrievalV2Corpus, MatcherEvalDataset]:
    corpus, _ = load_corpus(CORPUS_PATH)
    development, _ = load_matcher_dataset(DEVELOPMENT_PATH, corpus)
    return corpus, development


def test_checked_in_matcher_development_dataset_uses_v2_labels() -> None:
    _, development = load_checked_data()

    assert development.split is RetrievalSplit.DEVELOPMENT
    assert development.version == 2
    assert len(development.cases) == 12
    assert all(case.expected is None for case in development.cases)
    assert all(case.oracle_verdict is not None for case in development.cases)
    assert all(case.candidate_conditioned_verdict is not None for case in development.cases)
    dev_006 = next(case for case in development.cases if case.case_id == "matcher-dev-006")
    assert len(dev_006.acceptable_evidence) == 2
    assert len(dev_006.canonical_evidence) == 1
    dev_012 = next(case for case in development.cases if case.case_id == "matcher-dev-012")
    assert dev_012.candidate_conditioned_verdict is EvidenceVerdict.INSUFFICIENT_EVIDENCE
    assert dev_012.candidate_gap_reason_code is not None
    assert dev_012.candidate_gap_reason_code.value == "metric_not_proven"


def test_legacy_manifest_preserves_pre_migration_holdout_hash() -> None:
    corpus, corpus_hash = load_corpus(CORPUS_PATH)
    development, development_hash = load_matcher_dataset(DEVELOPMENT_PATH, corpus)
    current_holdout_hash = sha256(HOLDOUT_PATH.read_bytes()).hexdigest()
    manifest = load_matcher_review_manifest(MANIFEST_PATH)

    assert manifest.version == 2
    assert manifest.status is ReviewStatus.APPROVED_FROZEN
    assert manifest.reviewer == "project author"
    assert manifest.reviewed_at == datetime(2026, 10, 5, 3, 4, 46, tzinfo=UTC)
    assert manifest.corpus_sha256 == corpus_hash
    assert manifest.development_cases_sha256 == development_hash
    assert manifest.holdout_cases_sha256 == (
        "ef179ec0ce80de83806381c834cf73d7f5ab8c4135f3a15305f845e559a9dfdd"
    )
    assert manifest.holdout_cases_sha256 != current_holdout_hash


def test_checked_in_holdout_uses_rubric_v2_labels() -> None:
    corpus, _ = load_corpus(CORPUS_PATH)
    holdout, _ = load_matcher_dataset(HOLDOUT_PATH, corpus)

    assert holdout.version == 2
    assert len(holdout.cases) == 8
    assert all(case.expected is None for case in holdout.cases)
    assert all(case.oracle_verdict is not None for case in holdout.cases)
    assert all(case.candidate_conditioned_verdict is not None for case in holdout.cases)
    retrieval_miss = next(
        case for case in holdout.cases if case.case_id == "matcher-holdout-002"
    )
    assert retrieval_miss.oracle_verdict is EvidenceVerdict.MATCHED
    assert retrieval_miss.candidate_conditioned_verdict is EvidenceVerdict.MISSING


def test_migrated_holdout_run_manifest_is_approved_and_hash_bound() -> None:
    manifest = MatcherHoldoutManifest.model_validate_json(
        HOLDOUT_RUN_MANIFEST_PATH.read_bytes()
    )

    assert manifest.status is ReviewStatus.APPROVED_FROZEN
    assert manifest.reviewer == "project author"
    assert manifest.reviewed_at == datetime.fromisoformat(
        "2026-10-05T17:29:53.1449873-07:00"
    )
    assert manifest.holdout_cases_sha256 == sha256(HOLDOUT_PATH.read_bytes()).hexdigest()


def test_approved_holdout_manifest_content_validates() -> None:
    validated, _ = validate_holdout_manifest(
        HOLDOUT_RUN_MANIFEST_PATH,
        experiences_path=CORPUS_PATH,
        development_cases_path=DEVELOPMENT_PATH,
        holdout_cases_path=HOLDOUT_PATH,
        selected_development_manifest_path=Path(
            "evals/evidence_matcher_v1/prompt_v4_selected_development_manifest.json"
        ),
        development_report_path=Path(
            "docs/metrics/2026-10-05-groq-evidence-matcher-development-prompt-v4.json"
        ),
        development_coverage_report_path=Path(
            "docs/metrics/"
            "2026-10-05-groq-evidence-matcher-development-prompt-v4-coverage-v2-gates-v4.json"
        ),
        checkpoint_path=Path(
            "docs/metrics/2026-10-05-groq-evidence-matcher-holdout-checkpoint.json"
        ),
        output_path=Path(
            "docs/metrics/2026-10-05-groq-evidence-matcher-holdout.json"
        ),
    )

    assert validated.status is ReviewStatus.APPROVED_FROZEN


def test_dataset_rejects_cross_profile_candidate() -> None:
    corpus, development = load_checked_data()
    case = development.cases[0].model_copy(
        update={
            "candidate_experience_ids": [
                UUID("22222222-2222-4222-8222-000000000001")
            ]
        }
    )
    changed = development.model_copy(update={"cases": [case, *development.cases[1:]]})

    with pytest.raises(ValueError, match="cross-profile candidate"):
        validate_matcher_dataset(changed, corpus)


def test_dataset_rejects_ungrounded_acceptable_quote() -> None:
    corpus, development = load_checked_data()
    evidence = development.cases[0].acceptable_evidence[0]
    case = development.cases[0].model_copy(
        update={
            "acceptable_evidence": [
                evidence.model_copy(update={"quote": "invented quote"})
            ]
        }
    )
    changed = development.model_copy(update={"cases": [case, *development.cases[1:]]})

    with pytest.raises(ValueError, match="ungrounded evidence quote"):
        validate_matcher_dataset(changed, corpus)


def test_pending_manifest_cannot_authorize_a_run() -> None:
    corpus, corpus_hash = load_corpus(CORPUS_PATH)
    development, development_hash = load_matcher_dataset(DEVELOPMENT_PATH, corpus)
    manifest = load_matcher_review_manifest(MANIFEST_PATH).model_copy(
        update={
            "status": ReviewStatus.PENDING_AUTHOR_REVIEW,
            "reviewer": None,
            "reviewed_at": None,
        }
    )

    with pytest.raises(ValueError, match="approved and frozen"):
        validate_matcher_review_manifest(
            manifest,
            corpus_sha256=corpus_hash,
            dataset_sha256=development_hash,
            split=development.split,
        )


@pytest.mark.asyncio
async def test_metrics_separate_oracle_from_candidate_conditioned_verdict() -> None:
    corpus, development = load_checked_data()

    results = await evaluate_matcher_dataset(corpus, development, GoldMatcher(development))
    summary = summarize_matcher_results(results)

    assert summary.case_count == 12
    assert summary.matcher_eligible_count == 12
    assert summary.retrieval_miss_count == 1
    assert summary.schema_pass_rate == 1.0
    assert summary.matcher_only_verdict_accuracy == 1.0
    assert summary.matcher_only_exact_match_rate == 1.0
    assert summary.end_to_end_verdict_accuracy < 1.0
    assert summary.matcher_only_acceptable_evidence_accuracy == 1.0
    assert summary.end_to_end_acceptable_evidence_accuracy < 1.0
    assert summary.citation_validity_rate == 1.0
    assert summary.unsupported_positive_claim_rate == 0.0
    assert summary.confidence_case_count == 12
    assert summary.end_to_end_per_verdict == summary.per_verdict
    assert summary.matcher_only_per_verdict[EvidenceVerdict.MATCHED].support == 2
    assert summary.matcher_only_per_verdict[EvidenceVerdict.PARTIAL].support == 4


@pytest.mark.parametrize(
    ("error", "provider_failures", "output_failures"),
    [
        (
            EvidenceMatcherError(EvidenceMatcherFailureReason.TIMEOUT),
            1,
            0,
        ),
        (
            MatcherOutputValidationError(MatcherOutputFailureReason.INVALID_SCHEMA),
            0,
            1,
        ),
    ],
)
@pytest.mark.asyncio
async def test_summary_keeps_provider_and_output_failures_separate(
    error: Exception,
    provider_failures: int,
    output_failures: int,
) -> None:
    corpus, development = load_checked_data()
    one_case = development.model_copy(update={"cases": development.cases[:1]})

    results = await evaluate_matcher_dataset(corpus, one_case, FailureMatcher(error))
    summary = summarize_matcher_results(results)

    assert summary.schema_pass_rate == 0.0
    assert summary.provider_failure_count == provider_failures
    assert summary.output_failure_count == output_failures


@pytest.mark.asyncio
async def test_output_failure_preserves_safe_diagnostics_without_a_verdict() -> None:
    corpus, development = load_checked_data()
    one_case = development.model_copy(update={"cases": development.cases[:1]})
    error = MatcherOutputValidationError(
        MatcherOutputFailureReason.INVALID_SCHEMA,
        diagnostic="loc=matches.0.evidence;type=missing",
        response_sha256="a" * 64,
        response_size_bytes=321,
        input_tokens=100,
        output_tokens=20,
    )

    results = await evaluate_matcher_dataset(corpus, one_case, FailureMatcher(error))

    assert results[0].raw_verdict is None
    assert results[0].error_diagnostic == "loc=matches.0.evidence;type=missing"
    assert results[0].response_sha256 == "a" * 64
    assert results[0].response_size_bytes == 321
    assert results[0].input_tokens == 100
    assert results[0].output_tokens == 20


@pytest.mark.asyncio
async def test_runner_refuses_holdout_before_reading_approval(tmp_path: Path) -> None:
    output_path = tmp_path / "holdout-report.json"
    corpus, development = load_checked_data()
    toy_holdout = development.model_copy(update={"split": RetrievalSplit.HOLDOUT})
    toy_holdout_path = tmp_path / "toy-holdout.json"
    toy_holdout_path.write_text(toy_holdout.model_dump_json(indent=2), encoding="utf-8")

    with pytest.raises(RuntimeError, match="holdout is sealed"):
        await run(
            CORPUS_PATH,
            toy_holdout_path,
            MANIFEST_PATH,
            output_path,
            "test-revision",
        )

    assert not output_path.exists()


@pytest.mark.asyncio
async def test_approved_temp_manifest_allows_immutable_fake_report(tmp_path: Path) -> None:
    corpus, corpus_hash = load_corpus(CORPUS_PATH)
    development, development_hash = load_matcher_dataset(DEVELOPMENT_PATH, corpus)
    manifest = load_matcher_review_manifest(MANIFEST_PATH).model_copy(
        update={
            "status": ReviewStatus.APPROVED_FROZEN,
            "reviewer": "unit test",
            "reviewed_at": datetime(2026, 10, 4, tzinfo=UTC),
        }
    )
    validate_matcher_review_manifest(
        manifest,
        corpus_sha256=corpus_hash,
        dataset_sha256=development_hash,
        split=development.split,
    )
    manifest_path = tmp_path / "approved-manifest.json"
    manifest_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    output_path = tmp_path / "fake-report.json"

    report = await run(
        CORPUS_PATH,
        DEVELOPMENT_PATH,
        manifest_path,
        output_path,
        "test-revision",
    )

    assert report.provider == "fake"
    assert report.provider_request_attempt_count == 0
    assert report.provider_request_budget == 0
    assert report.summary.case_count == 12
    assert output_path.exists()
    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        await run(
            CORPUS_PATH,
            DEVELOPMENT_PATH,
            manifest_path,
            output_path,
            "test-revision",
        )
