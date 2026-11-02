from dataclasses import replace
from uuid import UUID, uuid4

import pytest
from tests.test_analysis_run_execution import ExecutionStore, ResultStore
from tests.test_analysis_run_service import make_inputs

from careerops.adapters.fake_evidence_matcher import FakeEvidenceMatcher
from careerops.domain.analysis_runs import (
    ANALYSIS_PROMPT_VERSION,
    FAKE_ANALYSIS_MODEL_NAME,
    MATCHER_BATCH_SIZE,
    MATCHER_BATCHING_VERSION,
    AnalysisInput,
    AnalysisRunErrorCode,
    AnalysisRunWorkItem,
    EvidenceMatcherOutput,
    matcher_batch_size_from_pipeline,
)
from careerops.domain.errors import EvidenceMatcherError, EvidenceMatcherFailureReason
from careerops.domain.evidence_matching import EvidenceMatcherInput, EvidenceVerdict
from careerops.domain.evidence_retrieval import retrieve_evidence_candidates
from careerops.domain.experiences import ExperienceRecord
from careerops.domain.parse_runs import JobRequirementRecord
from careerops.services.analysis_results import AnalysisResultService
from careerops.services.analysis_run_execution import (
    AnalysisRunExecutionService,
    split_candidate_sets,
)
from careerops.services.analysis_runs import compute_analysis_fingerprint


class RecordingMatcher:
    def __init__(self, *, fail_on_call: int | None = None) -> None:
        self._fake = FakeEvidenceMatcher()
        self._fail_on_call = fail_on_call
        self.inputs: list[EvidenceMatcherInput] = []

    @property
    def model_name(self) -> str:
        return FAKE_ANALYSIS_MODEL_NAME

    async def match(self, matcher_input: EvidenceMatcherInput) -> EvidenceMatcherOutput:
        self.inputs.append(matcher_input)
        if len(self.inputs) == self._fail_on_call:
            raise EvidenceMatcherError(EvidenceMatcherFailureReason.RATE_LIMITED)
        output = await self._fake.match(matcher_input)
        return replace(output, input_tokens=100, output_tokens=40)


def make_batched_dependencies(
    *,
    python_requirements: int,
    go_requirements: int = 0,
    prompt_version: str = ANALYSIS_PROMPT_VERSION,
) -> tuple[ExecutionStore, ResultStore, ExperienceRecord, ExperienceRecord]:
    job, parse_run, python_experience = make_inputs()
    go_experience = replace(
        python_experience,
        id=uuid4(),
        title="Go service",
        description="Built Go services.",
        skills=("Go",),
        content_hash="d" * 64,
    )
    template = parse_run.requirements[0]
    requirements = tuple(
        make_requirement(template, "Python required.", "Python")
        for _ in range(python_requirements)
    ) + tuple(make_requirement(template, "Go required.", "Go") for _ in range(go_requirements))
    experiences = (python_experience, go_experience)
    work_item = AnalysisRunWorkItem(
        id=uuid4(),
        attempt=1,
        user_id=job.user_id,
        job_id=job.id,
        parse_run_id=parse_run.id,
        input_fingerprint=compute_analysis_fingerprint(
            parse_run.id,
            parse_run.input_fingerprint,
            experiences,
            prompt_version,
        ),
        model_name=FAKE_ANALYSIS_MODEL_NAME,
        prompt_version=prompt_version,
        created_at=python_experience.created_at,
    )
    analysis_input = AnalysisInput(
        parse_input_fingerprint=parse_run.input_fingerprint,
        requirements=requirements,
        experiences=experiences,
    )
    store = ExecutionStore(work_item, analysis_input)
    return store, ResultStore(), python_experience, go_experience


def make_requirement(
    template: JobRequirementRecord,
    text: str,
    skill: str,
) -> JobRequirementRecord:
    return replace(template, id=uuid4(), text=text, skill_normalized=skill)


async def execute(store: ExecutionStore, results: ResultStore, matcher: RecordingMatcher) -> bool:
    return await AnalysisRunExecutionService(
        store,
        AnalysisResultService(results),
        matcher,
    ).execute(store.work_item.id)


def test_new_pipelines_record_the_batch_size() -> None:
    assert MATCHER_BATCHING_VERSION in ANALYSIS_PROMPT_VERSION.split(":")
    assert matcher_batch_size_from_pipeline(ANALYSIS_PROMPT_VERSION) == MATCHER_BATCH_SIZE


def test_pipelines_created_before_batching_keep_single_call() -> None:
    legacy = ANALYSIS_PROMPT_VERSION.replace(f"{MATCHER_BATCHING_VERSION}:", "")

    assert matcher_batch_size_from_pipeline(legacy) is None


@pytest.mark.parametrize(
    "segment",
    ["matcher-batch-0", "matcher-batch-x", "matcher-batch-6:matcher-batch-6"],
)
def test_invalid_batch_segments_are_rejected(segment: str) -> None:
    with pytest.raises(ValueError):
        matcher_batch_size_from_pipeline(f"match-v2:{segment}:model")


@pytest.mark.parametrize(
    ("requirements", "sizes"),
    [(0, [0]), (1, [1]), (6, [6]), (7, [6, 1]), (26, [6, 6, 6, 6, 2])],
)
def test_split_candidate_sets_keeps_order_and_bounds(requirements: int, sizes: list[int]) -> None:
    store, _, python_experience, _ = make_batched_dependencies(python_requirements=requirements)
    candidate_sets = retrieve_evidence_candidates(
        store.analysis_input.requirements,
        (python_experience,),
    )

    batches = split_candidate_sets(candidate_sets, MATCHER_BATCH_SIZE)

    assert [len(batch) for batch in batches] == sizes
    assert tuple(item for batch in batches for item in batch) == candidate_sets
    assert split_candidate_sets(candidate_sets, None) == (candidate_sets,)


@pytest.mark.asyncio
async def test_batched_run_stores_every_requirement_once_with_summed_tokens() -> None:
    store, results, _, _ = make_batched_dependencies(python_requirements=13)
    matcher = RecordingMatcher()

    assert await execute(store, results, matcher)

    assert [len(item.requirements) for item in matcher.inputs] == [6, 6, 1]
    expected_ids = [requirement.id for requirement in store.analysis_input.requirements]
    assert [match.requirement_id for match in results.matches] == expected_ids
    assert results.committed
    assert results.input_tokens == 300
    assert results.output_tokens == 120
    assert all(match.verdict is EvidenceVerdict.MATCHED for match in results.matches)


@pytest.mark.asyncio
async def test_each_batch_carries_only_its_own_candidate_experiences() -> None:
    store, results, python_experience, go_experience = make_batched_dependencies(
        python_requirements=6,
        go_requirements=6,
    )
    matcher = RecordingMatcher()

    assert await execute(store, results, matcher)

    sent: list[set[UUID]] = [
        {experience.experience_id for experience in item.experiences} for item in matcher.inputs
    ]
    assert sent == [{python_experience.id}, {go_experience.id}]


@pytest.mark.asyncio
async def test_failed_middle_batch_fails_the_whole_run_and_stores_nothing() -> None:
    store, results, _, _ = make_batched_dependencies(python_requirements=18)
    matcher = RecordingMatcher(fail_on_call=2)

    assert await execute(store, results, matcher)

    assert len(matcher.inputs) == 2
    assert store.failed_with is AnalysisRunErrorCode.MATCHER_PROVIDER_RATE_LIMITED
    assert store.failed_input_tokens == 100
    assert store.failed_output_tokens == 40
    assert not results.committed
    assert results.matches == ()


@pytest.mark.asyncio
async def test_legacy_pipeline_run_still_uses_one_call() -> None:
    legacy = ANALYSIS_PROMPT_VERSION.replace(f"{MATCHER_BATCHING_VERSION}:", "")
    store, results, _, _ = make_batched_dependencies(python_requirements=13, prompt_version=legacy)
    matcher = RecordingMatcher()

    assert await execute(store, results, matcher)

    assert [len(item.requirements) for item in matcher.inputs] == [13]
    assert len(results.matches) == 13
