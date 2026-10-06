from pathlib import Path

import pytest

from careerops.domain.evidence_matching import MATCHER_PROMPT_VERSION
from careerops.evaluation.evidence_matcher import load_matcher_dataset
from careerops.evaluation.evidence_retrieval_v2 import RetrievalSplit, load_corpus
from careerops.evaluation.rescore_evidence_matcher import run_offline_rescore
from careerops.evaluation.run_evidence_matcher import MatcherEvalReport

CORPUS_PATH = Path("evals/evidence_retrieval_v2/experiences.json")
DEVELOPMENT_PATH = Path("evals/evidence_matcher_v1/development_cases.json")
RECOVERY_REPORT_PATH = Path(
    "docs/metrics/2026-10-04-groq-evidence-matcher-development-recovery.json"
)


@pytest.mark.asyncio
async def test_offline_rescore_replays_raw_output_without_provider_requests(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "offline-rescore.json"

    report = await run_offline_rescore(
        experiences_path=CORPUS_PATH,
        development_cases_path=DEVELOPMENT_PATH,
        source_report_path=RECOVERY_REPORT_PATH,
        output_path=output_path,
        git_revision="test-revision",
    )

    assert report.provider_request_attempt_count == 0
    assert report.summary.case_count == 12
    assert report.summary.completed_case_count == 12
    assert report.summary.end_to_end_verdict_accuracy == 0.5
    assert report.summary.matcher_only_verdict_accuracy == pytest.approx(7 / 12)
    assert report.summary.matcher_only_experience_id_accuracy == 1.0
    assert report.summary.matcher_only_source_accuracy == 1.0
    assert report.summary.matcher_only_acceptable_evidence_accuracy == 1.0
    assert report.summary.matcher_only_canonical_quote_exact_agreement == 0.0
    assert report.summary.citation_validity_rate == 1.0
    assert report.summary.unsupported_positive_claim_rate == 0.0
    assert report.summary.verdict_error_attribution == {
        "model_error": 5,
        "retrieval_miss": 1,
        "canonical_quote_over_strict": 6,
    }
    assert report.legacy_error_attribution == {
        "model_error": 2,
        "retrieval_miss": 1,
        "verdict_label_ambiguity": 3,
        "canonical_quote_over_strict": 6,
    }
    assert report.summary.matcher_only_per_verdict["missing"].recall == 0.0
    assert report.summary.matcher_only_per_verdict["partial"].support == 4
    retrieval_miss = next(
        case for case in report.cases if case.case_id == "matcher-dev-009"
    )
    assert retrieval_miss.end_to_end_verdict_correct is False
    assert retrieval_miss.matcher_only_verdict_correct is True
    assert retrieval_miss.matcher_only_acceptable_evidence_correct is True
    assert output_path.exists()

    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        await run_offline_rescore(
            experiences_path=CORPUS_PATH,
            development_cases_path=DEVELOPMENT_PATH,
            source_report_path=RECOVERY_REPORT_PATH,
            output_path=output_path,
            git_revision="test-revision",
        )


@pytest.mark.asyncio
async def test_offline_rescore_refuses_holdout_before_source_report_read(
    tmp_path: Path,
) -> None:
    corpus, _ = load_corpus(CORPUS_PATH)
    development, _ = load_matcher_dataset(DEVELOPMENT_PATH, corpus)
    toy_holdout = development.model_copy(update={"split": RetrievalSplit.HOLDOUT})
    toy_holdout_path = tmp_path / "toy-holdout.json"
    toy_holdout_path.write_text(toy_holdout.model_dump_json(indent=2), encoding="utf-8")
    missing_source = tmp_path / "missing-source.json"

    with pytest.raises(RuntimeError, match="development data only"):
        await run_offline_rescore(
            experiences_path=CORPUS_PATH,
            development_cases_path=toy_holdout_path,
            source_report_path=missing_source,
            output_path=tmp_path / "report.json",
            git_revision="test-revision",
        )


@pytest.mark.asyncio
async def test_legacy_ambiguity_attribution_is_disabled_for_prompt_v2(
    tmp_path: Path,
) -> None:
    source = MatcherEvalReport.model_validate_json(RECOVERY_REPORT_PATH.read_bytes())
    v2_source_path = tmp_path / "v2-source.json"
    v2_source_path.write_text(
        source.model_copy(update={"prompt_version": MATCHER_PROMPT_VERSION}).model_dump_json(
            indent=2
        ),
        encoding="utf-8",
    )

    report = await run_offline_rescore(
        experiences_path=CORPUS_PATH,
        development_cases_path=DEVELOPMENT_PATH,
        source_report_path=v2_source_path,
        output_path=tmp_path / "v2-rescore.json",
        git_revision="test-revision",
    )

    assert report.legacy_error_attribution["verdict_label_ambiguity"] == 0
    assert report.legacy_error_attribution["model_error"] == 5
