import json
import logging
from uuid import UUID, uuid4

import httpx
import pytest
from tests.test_analysis_run_service import make_inputs

from careerops.adapters.evidence_matcher_factory import GROQ_EVIDENCE_MATCHER_MODEL
from careerops.adapters.fake_evidence_matcher import FakeEvidenceMatcher
from careerops.adapters.groq_evidence_matcher import GroqEvidenceMatcher
from careerops.domain.analysis_runs import (
    ANALYSIS_PROMPT_VERSION,
    FAKE_ANALYSIS_MODEL_NAME,
    AnalysisDispatchSource,
    AnalysisInput,
    AnalysisRunErrorCode,
    AnalysisRunWorkItem,
    EvidenceMatcherOutput,
    matcher_pipeline_version,
)
from careerops.domain.embeddings import FAKE_EMBEDDING_SPACE
from careerops.domain.errors import (
    EvidenceMatcherError,
    EvidenceMatcherFailureReason,
    MatcherOutputFailureReason,
    MatcherOutputValidationError,
)
from careerops.domain.evidence_matching import (
    MATCHER_PROMPT_VERSION,
    MATCHER_PROMPT_VERSION_V1,
    EvidenceMatcherInput,
    EvidenceVerdict,
    ProposedEvidenceMatch,
    ValidatedEvidenceMatch,
)
from careerops.services.analysis_results import AnalysisResultService
from careerops.services.analysis_run_execution import AnalysisRunExecutionService
from careerops.services.analysis_runs import compute_analysis_fingerprint


class ExecutionStore:
    def __init__(self, work_item: AnalysisRunWorkItem, analysis_input: AnalysisInput) -> None:
        self.work_item = work_item
        self.analysis_input = analysis_input
        self.claimed = False
        self.failed_with: AnalysisRunErrorCode | None = None
        self.failed_input_tokens: int | None = None
        self.failed_output_tokens: int | None = None
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
        attempt: int,
        model_name: str,
        error_code: AnalysisRunErrorCode,
        latency_ms: int,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
    ) -> bool:
        self.failed_with = error_code
        self.failed_input_tokens = input_tokens
        self.failed_output_tokens = output_tokens
        return True

    async def commit(self) -> None:
        self.commits += 1


class ResultStore:
    def __init__(self) -> None:
        self.matches: tuple[ValidatedEvidenceMatch, ...] = ()
        self.validation_failure_count: int | None = None
        self.model_name: str | None = None
        self.input_tokens: int | None = None
        self.output_tokens: int | None = None
        self.committed = False

    async def complete_analysis_run(
        self,
        analysis_run_id: UUID,
        attempt: int,
        matches: tuple[ValidatedEvidenceMatch, ...],
        validation_failure_count: int,
        model_name: str,
        latency_ms: int,
        input_tokens: int | None,
        output_tokens: int | None,
    ) -> bool:
        self.matches = matches
        self.validation_failure_count = validation_failure_count
        self.model_name = model_name
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        return True

    async def commit(self) -> None:
        self.committed = True


class InvalidMatcher:
    def __init__(self, mode: str) -> None:
        self._mode = mode

    @property
    def model_name(self) -> str:
        return FAKE_ANALYSIS_MODEL_NAME

    async def match(
        self,
        matcher_input: EvidenceMatcherInput,
    ) -> EvidenceMatcherOutput:
        requirement_id = matcher_input.requirements[0].requirement_id
        duplicate = ProposedEvidenceMatch(
            requirement_id=requirement_id,
            verdict=EvidenceVerdict.MISSING,
            experience_id=None,
            experience_version=None,
            quote=None,
            confidence=None,
        )
        if self._mode == "omitted":
            matches: tuple[ProposedEvidenceMatch, ...] = ()
        elif self._mode == "extra":
            matches = (
                duplicate,
                ProposedEvidenceMatch(
                    requirement_id=uuid4(),
                    verdict=EvidenceVerdict.MISSING,
                    experience_id=None,
                    experience_version=None,
                    quote=None,
                    confidence=None,
                ),
            )
        else:
            matches = (duplicate, duplicate)
        return EvidenceMatcherOutput(model_name=self.model_name, matches=matches)


class ProviderFailureMatcher:
    def __init__(self, reason: EvidenceMatcherFailureReason) -> None:
        self._reason = reason

    @property
    def model_name(self) -> str:
        return FAKE_ANALYSIS_MODEL_NAME

    async def match(self, matcher_input: EvidenceMatcherInput) -> EvidenceMatcherOutput:
        raise EvidenceMatcherError(self._reason)


class RecordingFakeMatcher(FakeEvidenceMatcher):
    def __init__(self) -> None:
        self.prompt_versions: list[str] = []

    async def match(self, matcher_input: EvidenceMatcherInput) -> EvidenceMatcherOutput:
        self.prompt_versions.append(matcher_input.prompt_version)
        return await super().match(matcher_input)


class OutputFailureMatcher:
    def __init__(self, reason: MatcherOutputFailureReason) -> None:
        self._reason = reason

    @property
    def model_name(self) -> str:
        return FAKE_ANALYSIS_MODEL_NAME

    async def match(self, matcher_input: EvidenceMatcherInput) -> EvidenceMatcherOutput:
        raise MatcherOutputValidationError(
            self._reason,
            diagnostic="loc=matches.0.evidence;type=missing",
            response_sha256="a" * 64,
            response_size_bytes=321,
            input_tokens=42,
            output_tokens=7,
        )


class UngroundedMatcher:
    @property
    def model_name(self) -> str:
        return FAKE_ANALYSIS_MODEL_NAME

    async def match(
        self,
        matcher_input: EvidenceMatcherInput,
    ) -> EvidenceMatcherOutput:
        return EvidenceMatcherOutput(
            model_name=self.model_name,
            matches=(
                ProposedEvidenceMatch(
                    requirement_id=matcher_input.requirements[0].requirement_id,
                    verdict=EvidenceVerdict.MATCHED,
                    experience_id=uuid4(),
                    experience_version=1,
                    source_ref="description",
                    quote="Invented production claim",
                    confidence=None,
                ),
            ),
        )


class WrongOutputModelMatcher(FakeEvidenceMatcher):
    async def match(self, matcher_input: EvidenceMatcherInput) -> EvidenceMatcherOutput:
        output = await super().match(matcher_input)
        return EvidenceMatcherOutput(
            model_name="unexpected-model",
            matches=output.matches,
        )


@pytest.mark.asyncio
async def test_execution_completes_all_requirements_once(
    caplog: pytest.LogCaptureFixture,
) -> None:
    store, results = make_execution_dependencies()
    service = AnalysisRunExecutionService(
        store,
        AnalysisResultService(results),
        FakeEvidenceMatcher(),
    )

    with caplog.at_level(logging.INFO):
        first = await service.execute(
            store.work_item.id,
            request_id="request-1",
            dispatch_source=AnalysisDispatchSource.SUBMISSION,
        )
        duplicate = await service.execute(
            store.work_item.id,
            request_id="request-2",
            dispatch_source=AnalysisDispatchSource.IDEMPOTENT_REPLAY,
        )

    assert first
    assert not duplicate
    assert len(results.matches) == 1
    assert results.matches[0].verdict is EvidenceVerdict.MATCHED
    assert results.committed
    assert store.commits == 1
    succeeded = next(
        record for record in caplog.records if record.getMessage() == "analysis_run_succeeded"
    )
    skipped = next(
        record for record in caplog.records if record.getMessage() == "analysis_run_claim_skipped"
    )
    assert succeeded.request_id == "request-1"
    assert succeeded.run_id == str(store.work_item.id)
    assert succeeded.attempt == 1
    assert skipped.request_id == "request-2"
    assert skipped.outcome == "not_queued"


@pytest.mark.asyncio
async def test_execution_uses_prompt_version_bound_to_durable_work_item() -> None:
    store, results = make_execution_dependencies()
    old_pipeline_version = store.work_item.prompt_version.replace(
        MATCHER_PROMPT_VERSION,
        MATCHER_PROMPT_VERSION_V1,
    )
    store.work_item = AnalysisRunWorkItem(
        id=store.work_item.id,
        attempt=store.work_item.attempt,
        user_id=store.work_item.user_id,
        job_id=store.work_item.job_id,
        parse_run_id=store.work_item.parse_run_id,
        input_fingerprint=compute_analysis_fingerprint(
            store.work_item.parse_run_id,
            store.analysis_input.parse_input_fingerprint,
            store.analysis_input.experiences,
            old_pipeline_version,
        ),
        model_name=store.work_item.model_name,
        prompt_version=old_pipeline_version,
        created_at=store.work_item.created_at,
    )
    matcher = RecordingFakeMatcher()

    executed = await AnalysisRunExecutionService(
        store,
        AnalysisResultService(results),
        matcher,
    ).execute(store.work_item.id)

    assert executed
    assert matcher.prompt_versions == [MATCHER_PROMPT_VERSION_V1]
    assert results.committed


@pytest.mark.asyncio
async def test_execution_resolves_matcher_from_durable_work_item() -> None:
    store, results = make_execution_dependencies()
    resolved: list[AnalysisRunWorkItem] = []

    def resolve(work_item: AnalysisRunWorkItem) -> FakeEvidenceMatcher:
        resolved.append(work_item)
        return FakeEvidenceMatcher()

    executed = await AnalysisRunExecutionService(
        store,
        AnalysisResultService(results),
        matcher_factory=resolve,
    ).execute(store.work_item.id)

    assert executed
    assert resolved == [store.work_item]
    assert results.committed


@pytest.mark.asyncio
async def test_execution_runs_mocked_groq_matcher_through_worker_boundary() -> None:
    store, results = make_execution_dependencies()
    pipeline_version = matcher_pipeline_version(
        FAKE_EMBEDDING_SPACE,
        GROQ_EVIDENCE_MATCHER_MODEL,
    )
    store.work_item = AnalysisRunWorkItem(
        id=store.work_item.id,
        attempt=store.work_item.attempt,
        user_id=store.work_item.user_id,
        job_id=store.work_item.job_id,
        parse_run_id=store.work_item.parse_run_id,
        input_fingerprint=compute_analysis_fingerprint(
            store.work_item.parse_run_id,
            store.analysis_input.parse_input_fingerprint,
            store.analysis_input.experiences,
            pipeline_version,
        ),
        model_name=GROQ_EVIDENCE_MATCHER_MODEL,
        prompt_version=pipeline_version,
        created_at=store.work_item.created_at,
    )

    def handle(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        supplied = json.loads(body["messages"][1]["content"])
        requirement_id = supplied["requirements"][0]["requirement_id"]
        experience_id = supplied["experiences"][0]["experience_id"]
        return httpx.Response(
            200,
            request=request,
            json={
                "model": GROQ_EVIDENCE_MATCHER_MODEL,
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "schema_version": "evidence-matcher-schema-v1",
                                    "matches": [
                                        {
                                            "requirement_id": requirement_id,
                                            "verdict": "matched",
                                            "evidence": {
                                                "experience_id": experience_id,
                                                "experience_version": 1,
                                                "source_ref": "skill:0",
                                                "quote": "Python",
                                            },
                                            "confidence": 0.9,
                                        }
                                    ],
                                }
                            )
                        }
                    }
                ],
                "usage": {"prompt_tokens": 120, "completion_tokens": 30},
            },
        )

    matcher = GroqEvidenceMatcher(
        api_key="test-key",
        model=GROQ_EVIDENCE_MATCHER_MODEL,
        base_url="https://api.groq.test/openai/v1",
        timeout_seconds=1.0,
        max_attempts=1,
        retry_base_delay_seconds=0.0,
        max_output_tokens=800,
        transport=httpx.MockTransport(handle),
    )

    executed = await AnalysisRunExecutionService(
        store,
        AnalysisResultService(results),
        matcher,
    ).execute(store.work_item.id)

    assert executed
    assert results.committed
    assert results.model_name == GROQ_EVIDENCE_MATCHER_MODEL
    assert results.input_tokens == 120
    assert results.output_tokens == 30
    assert results.matches[0].verdict is EvidenceVerdict.MATCHED
    assert results.matches[0].quote_valid


@pytest.mark.asyncio
async def test_execution_rejects_durable_model_pipeline_mismatch() -> None:
    store, results = make_execution_dependencies()
    store.work_item = AnalysisRunWorkItem(
        id=store.work_item.id,
        attempt=store.work_item.attempt,
        user_id=store.work_item.user_id,
        job_id=store.work_item.job_id,
        parse_run_id=store.work_item.parse_run_id,
        input_fingerprint=store.work_item.input_fingerprint,
        model_name="unexpected-model",
        prompt_version=store.work_item.prompt_version,
        created_at=store.work_item.created_at,
    )

    executed = await AnalysisRunExecutionService(
        store,
        AnalysisResultService(results),
        FakeEvidenceMatcher(),
    ).execute(store.work_item.id)

    assert executed
    assert store.failed_with is AnalysisRunErrorCode.MATCHER_OUTPUT_INVALID_CONTRACT
    assert not results.committed


@pytest.mark.asyncio
async def test_execution_rejects_provider_model_identity_mismatch() -> None:
    store, results = make_execution_dependencies()

    executed = await AnalysisRunExecutionService(
        store,
        AnalysisResultService(results),
        WrongOutputModelMatcher(),
    ).execute(store.work_item.id)

    assert executed
    assert store.failed_with is AnalysisRunErrorCode.MATCHER_OUTPUT_INVALID_CONTRACT
    assert not results.committed


@pytest.mark.asyncio
async def test_execution_fails_when_experience_library_changed() -> None:
    store, results = make_execution_dependencies()
    store.work_item = AnalysisRunWorkItem(
        id=store.work_item.id,
        attempt=store.work_item.attempt,
        user_id=store.work_item.user_id,
        job_id=store.work_item.job_id,
        parse_run_id=store.work_item.parse_run_id,
        input_fingerprint="f" * 64,
        model_name=store.work_item.model_name,
        prompt_version=store.work_item.prompt_version,
        created_at=store.work_item.created_at,
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


@pytest.mark.parametrize("mode", ["omitted", "duplicate", "extra"])
@pytest.mark.asyncio
async def test_execution_rejects_inexact_requirement_coverage(mode: str) -> None:
    store, results = make_execution_dependencies()

    executed = await AnalysisRunExecutionService(
        store,
        AnalysisResultService(results),
        InvalidMatcher(mode),
    ).execute(store.work_item.id)

    assert executed
    assert store.failed_with is AnalysisRunErrorCode.MATCHER_OUTPUT_INVALID_CONTRACT
    assert not results.committed


@pytest.mark.parametrize(
    ("reason", "expected"),
    [
        (
            EvidenceMatcherFailureReason.DISABLED,
            AnalysisRunErrorCode.MATCHER_PROVIDER_DISABLED,
        ),
        (
            EvidenceMatcherFailureReason.MISCONFIGURED,
            AnalysisRunErrorCode.MATCHER_PROVIDER_MISCONFIGURED,
        ),
        (
            EvidenceMatcherFailureReason.TIMEOUT,
            AnalysisRunErrorCode.MATCHER_PROVIDER_TIMEOUT,
        ),
        (
            EvidenceMatcherFailureReason.RATE_LIMITED,
            AnalysisRunErrorCode.MATCHER_PROVIDER_RATE_LIMITED,
        ),
        (
            EvidenceMatcherFailureReason.UNAVAILABLE,
            AnalysisRunErrorCode.MATCHER_PROVIDER_UNAVAILABLE,
        ),
        (
            EvidenceMatcherFailureReason.REQUEST_FAILED,
            AnalysisRunErrorCode.MATCHER_PROVIDER_FAILED,
        ),
    ],
)
@pytest.mark.asyncio
async def test_execution_persists_specific_provider_failure(
    reason: EvidenceMatcherFailureReason,
    expected: AnalysisRunErrorCode,
) -> None:
    store, results = make_execution_dependencies()

    executed = await AnalysisRunExecutionService(
        store,
        AnalysisResultService(results),
        ProviderFailureMatcher(reason),
    ).execute(store.work_item.id)

    assert executed
    assert store.failed_with is expected
    assert store.failed_input_tokens is None
    assert store.failed_output_tokens is None
    assert not results.committed


@pytest.mark.parametrize(
    ("reason", "expected"),
    [
        (
            MatcherOutputFailureReason.INVALID_JSON,
            AnalysisRunErrorCode.MATCHER_OUTPUT_INVALID_JSON,
        ),
        (
            MatcherOutputFailureReason.INVALID_SCHEMA,
            AnalysisRunErrorCode.MATCHER_OUTPUT_INVALID_SCHEMA,
        ),
        (
            MatcherOutputFailureReason.INVALID_CONTRACT,
            AnalysisRunErrorCode.MATCHER_OUTPUT_INVALID_CONTRACT,
        ),
    ],
)
@pytest.mark.asyncio
async def test_execution_persists_specific_output_failure(
    reason: MatcherOutputFailureReason,
    expected: AnalysisRunErrorCode,
    caplog: pytest.LogCaptureFixture,
) -> None:
    store, results = make_execution_dependencies()

    with caplog.at_level(logging.WARNING):
        executed = await AnalysisRunExecutionService(
            store,
            AnalysisResultService(results),
            OutputFailureMatcher(reason),
        ).execute(store.work_item.id)

    assert executed
    assert store.failed_with is expected
    assert store.failed_input_tokens == 42
    assert store.failed_output_tokens == 7
    assert not results.committed
    assert caplog.records[-2].getMessage() == "evidence_matcher_output_rejected"
    assert caplog.records[-2].failure_reason == reason.value
    assert caplog.records[-2].diagnostic == (
        "loc=matches.0.evidence;type=missing"
    )
    assert caplog.records[-2].response_sha256 == "a" * 64
    assert caplog.records[-2].response_size_bytes == 321
    assert caplog.records[-1].getMessage() == "analysis_run_failed"


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
        attempt=1,
        user_id=job.user_id,
        job_id=job.id,
        parse_run_id=parse_run.id,
        input_fingerprint=compute_analysis_fingerprint(
            parse_run.id,
            parse_run.input_fingerprint,
            (experience,),
        ),
        model_name=FAKE_ANALYSIS_MODEL_NAME,
        prompt_version=ANALYSIS_PROMPT_VERSION,
        created_at=experience.created_at,
    )
    return ExecutionStore(work_item, analysis_input), ResultStore()
