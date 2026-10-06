import os
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel

from careerops.domain.analysis_runs import EvidenceMatcherOutput
from careerops.domain.evidence_matching import (
    MATCHER_PROMPT_VERSION_V1,
    EvidenceMatcherInput,
    EvidenceVerdict,
    ProposedEvidenceMatch,
)
from careerops.evaluation.evidence_matcher import (
    GapReasonCode,
    MatcherCaseResult,
    MatcherEvalSummary,
    evaluate_matcher_dataset,
    load_matcher_dataset,
    summarize_matcher_results,
)
from careerops.evaluation.evidence_retrieval_v2 import RetrievalSplit, load_corpus
from careerops.evaluation.run_evidence_matcher import MatcherEvalReport

MATCHER_EVALUATION_RUBRIC_VERSION = "evidence-matcher-evaluation-rubric-v2"


class MatcherOfflineRescoreReport(BaseModel):
    created_at: datetime
    git_revision: str
    rubric_version: str
    rescored_from_sha256: str
    source_provider: str
    source_model_name: str
    corpus_sha256: str
    development_cases_sha256: str
    provider_request_attempt_count: int
    summary: MatcherEvalSummary
    legacy_error_attribution: dict[str, int]
    cases: list[MatcherCaseResult]
    limitations: list[str]


class RecordedEvidenceMatcher:
    def __init__(
        self,
        *,
        source_report: MatcherEvalReport,
        requirement_case_ids: dict[UUID, str],
    ) -> None:
        self._model_name = source_report.model_name
        source_cases = {case.case_id: case for case in source_report.cases}
        self._results = {
            requirement_id: source_cases[case_id]
            for requirement_id, case_id in requirement_case_ids.items()
        }

    @property
    def model_name(self) -> str:
        return self._model_name

    async def match(self, matcher_input: EvidenceMatcherInput) -> EvidenceMatcherOutput:
        if len(matcher_input.requirements) != 1:
            raise ValueError("Offline matcher rescoring requires one requirement per case.")
        result = self._results[matcher_input.requirements[0].requirement_id]
        if result.error_type is not None or result.raw_verdict is None:
            raise ValueError("Offline matcher rescoring requires completed raw case output.")
        return EvidenceMatcherOutput(
            model_name=result.model_name or self._model_name,
            matches=(
                ProposedEvidenceMatch(
                    requirement_id=matcher_input.requirements[0].requirement_id,
                    verdict=result.raw_verdict,
                    experience_id=result.raw_experience_id,
                    experience_version=result.raw_experience_version,
                    source_ref=result.raw_source_ref,
                    quote=result.raw_quote,
                    confidence=result.confidence,
                ),
            ),
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
        )


async def run_offline_rescore(
    *,
    experiences_path: Path,
    development_cases_path: Path,
    source_report_path: Path,
    output_path: Path,
    git_revision: str,
) -> MatcherOfflineRescoreReport:
    if output_path.exists():
        raise FileExistsError(f"Refusing to overwrite evaluation evidence: {output_path}")

    corpus, corpus_hash = load_corpus(experiences_path)
    dataset, dataset_hash = load_matcher_dataset(development_cases_path, corpus)
    if dataset.split is not RetrievalSplit.DEVELOPMENT:
        raise RuntimeError("Offline matcher rescoring accepts development data only.")
    source_content = source_report_path.read_bytes()
    source_report = MatcherEvalReport.model_validate_json(source_content)
    if (
        source_report.split is not RetrievalSplit.DEVELOPMENT
        or source_report.corpus_sha256 != corpus_hash
        or source_report.summary.completed_case_count != len(dataset.cases)
        or [case.case_id for case in source_report.cases]
        != [case.case_id for case in dataset.cases]
    ):
        raise ValueError("Source matcher report does not match the development dataset.")

    matcher = RecordedEvidenceMatcher(
        source_report=source_report,
        requirement_case_ids={case.requirement.id: case.case_id for case in dataset.cases},
    )
    results = await evaluate_matcher_dataset(corpus, dataset, matcher)
    summary = summarize_matcher_results(results)
    legacy_ambiguity_case_ids = {
        case.case_id
        for case in dataset.cases
        if source_report.prompt_version == MATCHER_PROMPT_VERSION_V1
        and case.candidate_conditioned_verdict is EvidenceVerdict.MISSING
        and case.candidate_gap_reason_code
        is GapReasonCode.REQUIRED_TECHNOLOGY_ABSENT
    }
    legacy_ambiguity_count = sum(
        result.case_id in legacy_ambiguity_case_ids
        and result.raw_verdict is EvidenceVerdict.INSUFFICIENT_EVIDENCE
        for result in results
    )
    report = MatcherOfflineRescoreReport(
        created_at=datetime.now(UTC),
        git_revision=git_revision,
        rubric_version=MATCHER_EVALUATION_RUBRIC_VERSION,
        rescored_from_sha256=sha256(source_content).hexdigest(),
        source_provider=source_report.provider,
        source_model_name=source_report.model_name,
        corpus_sha256=corpus_hash,
        development_cases_sha256=dataset_hash,
        provider_request_attempt_count=0,
        summary=summary,
        legacy_error_attribution={
            "model_error": summary.verdict_error_attribution["model_error"]
            - legacy_ambiguity_count,
            "retrieval_miss": summary.verdict_error_attribution["retrieval_miss"],
            "verdict_label_ambiguity": legacy_ambiguity_count,
            "canonical_quote_over_strict": summary.verdict_error_attribution[
                "canonical_quote_over_strict"
            ],
        },
        cases=results,
        limitations=[
            "This report rescored saved raw development output and made zero provider calls.",
            "Matcher v2 labels remain pending project-author review.",
            "Canonical quote exact agreement is diagnostic, not an evidence-safety gate.",
            "The matcher holdout was not read, run, or used for tuning.",
            "Synthetic development results do not establish production accuracy.",
        ],
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_name(f".{output_path.name}.tmp")
    temporary.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    os.rename(temporary, output_path)
    return report
