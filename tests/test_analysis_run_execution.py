from uuid import UUID, uuid4

import pytest
from tests.test_analysis_run_service import make_inputs

from careerops.adapters.fake_evidence_matcher import FakeEvidenceMatcher
from careerops.domain.analysis_runs import (
    AnalysisInput,
    AnalysisRunErrorCode,
    AnalysisRunWorkItem,
    EvidenceMatcherOutput,
)
from careerops.domain.evidence_matching import (
    EvidenceVerdict,
    ProposedEvidenceMatch,
    ValidatedEvidenceMatch,
)
from careerops.domain.evidence_retrieval import RequirementCandidateSet
from careerops.services.analysis_results import AnalysisResultService
from careerops.services.analysis_run_execution import AnalysisRunExecutionService
from careerops.services.analysis_runs import compute_analysis_fingerprint


class ExecutionStore:
    def __init__(self, work_item: AnalysisRunWorkItem, analysis_input: AnalysisInput) -> None:
        self.work_item = work_item
        self.analysis_input = analysis_input
        self.claimed = False
        self.failed_with: AnalysisRunErrorCode | None = None
        self.commits = 0

    async def claim_analysis_run(self, analysis_run_id: UUID) -> AnalysisRunWorkItem | None:
        if self.claimed or analysis_run_id != self.work_item.id:
            return None
        self.claimed = True
        return self.work_item

    async def load_analysis_input(self, work_item: AnalysisRunWorkItem) -> AnalysisInput:
        return self.analysis_input

    async def fail_analysis_run(
        self,
        analysis_run_id: UUID,
        model_name: str,
        error_code: AnalysisRunErrorCode,
        latency_ms: int,
    ) -> bool:
        self.failed_with = error_code
        return True

    async def commit(self) -> None:
        self.commits += 1


class ResultStore:
    def __init__(self) -> None:
        self.matches: tuple[ValidatedEvidenceMatch, ...] = ()
        self.validation_failure_count: int | None = None
        self.committed = False

    async def complete_analysis_run(
        self,
        analysis_run_id: UUID,
        matches: tuple[ValidatedEvidenceMatch, ...],
        validation_failure_count: int,
        model_name: str,
        latency_ms: int,
        input_tokens: int | None,
        output_tokens: int | None,
    ) -> bool:
        self.matches = matches
        self.validation_failure_count = validation_failure_count
        return True

    async def commit(self) -> None:
        self.committed = True


class InvalidMatcher:
    @property
    def model_name(self) -> str:
        return "invalid-matcher"

    async def match(
        self,
        candidate_sets: tuple[RequirementCandidateSet, ...],
    ) -> EvidenceMatcherOutput:
        requirement_id = candidate_sets[0].requirement.id
        duplicate = ProposedEvidenceMatch(
            requirement_id=requirement_id,
            verdict=EvidenceVerdict.MISSING,
            experience_id=None,
            experience_version=None,
            quote=None,
            confidence=None,
        )
        return EvidenceMatcherOutput(model_name=self.model_name, matches=(duplicate, duplicate))


class UngroundedMatcher:
    @property
    def model_name(self) -> str:
        return "ungrounded-matcher"

    async def match(
        self,
        candidate_sets: tuple[RequirementCandidateSet, ...],
    ) -> EvidenceMatcherOutput:
        return EvidenceMatcherOutput(
            model_name=self.model_name,
            matches=(
                ProposedEvidenceMatch(
                    requirement_id=candidate_sets[0].requirement.id,
                    verdict=EvidenceVerdict.MATCHED,
                    experience_id=uuid4(),
                    experience_version=1,
                    quote="Invented production claim",
                    confidence=None,
                ),
            ),
        )


@pytest.mark.asyncio
async def test_execution_completes_all_requirements_once() -> None:
    store, results = make_execution_dependencies()
    service = AnalysisRunExecutionService(
        store,
        AnalysisResultService(results),
        FakeEvidenceMatcher(),
    )

    first = await service.execute(store.work_item.id)
    duplicate = await service.execute(store.work_item.id)

    assert first
    assert not duplicate
    assert len(results.matches) == 1
    assert results.matches[0].verdict is EvidenceVerdict.MATCHED
    assert results.committed
    assert store.commits == 1


@pytest.mark.asyncio
async def test_execution_fails_when_experience_library_changed() -> None:
    store, results = make_execution_dependencies()
    store.work_item = AnalysisRunWorkItem(
        id=store.work_item.id,
        user_id=store.work_item.user_id,
        job_id=store.work_item.job_id,
        parse_run_id=store.work_item.parse_run_id,
        input_fingerprint="f" * 64,
    )

    executed = await AnalysisRunExecutionService(
        store,
        AnalysisResultService(results),
        FakeEvidenceMatcher(),
    ).execute(store.work_item.id)

    assert executed
    assert store.failed_with is AnalysisRunErrorCode.ANALYSIS_INPUT_CHANGED
    assert not results.committed
    assert store.commits == 2


@pytest.mark.asyncio
async def test_execution_rejects_duplicate_requirement_output() -> None:
    store, results = make_execution_dependencies()

    executed = await AnalysisRunExecutionService(
        store,
        AnalysisResultService(results),
        InvalidMatcher(),
    ).execute(store.work_item.id)

    assert executed
    assert store.failed_with is AnalysisRunErrorCode.MATCHER_OUTPUT_INVALID
    assert not results.committed


@pytest.mark.asyncio
async def test_execution_downgrades_ungrounded_positive_claim() -> None:
    store, results = make_execution_dependencies()

    executed = await AnalysisRunExecutionService(
        store,
        AnalysisResultService(results),
        UngroundedMatcher(),
    ).execute(store.work_item.id)

    assert executed
    assert results.matches[0].verdict is EvidenceVerdict.INSUFFICIENT_EVIDENCE
    assert results.matches[0].experience_id is None
    assert results.validation_failure_count == 1


def make_execution_dependencies() -> tuple[ExecutionStore, ResultStore]:
    job, parse_run, experience = make_inputs()
    analysis_input = AnalysisInput(
        parse_input_fingerprint=parse_run.input_fingerprint,
        requirements=parse_run.requirements,
        experiences=(experience,),
    )
    work_item = AnalysisRunWorkItem(
        id=uuid4(),
        user_id=job.user_id,
        job_id=job.id,
        parse_run_id=parse_run.id,
        input_fingerprint=compute_analysis_fingerprint(
            parse_run.id,
            parse_run.input_fingerprint,
            (experience,),
        ),
    )
    return ExecutionStore(work_item, analysis_input), ResultStore()
