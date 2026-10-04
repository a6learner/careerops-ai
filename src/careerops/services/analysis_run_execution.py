from collections.abc import Callable
from time import perf_counter
from typing import Protocol
from uuid import UUID

from careerops.domain.analysis_runs import (
    AnalysisInput,
    AnalysisRunErrorCode,
    AnalysisRunWorkItem,
    EvidenceMatcherOutput,
)
from careerops.domain.errors import EvidenceMatcherError, MatcherOutputValidationError
from careerops.domain.evidence_matching import ValidatedEvidenceMatch, validate_evidence_match
from careerops.domain.evidence_retrieval import RequirementCandidateSet
from careerops.services.analysis_results import AnalysisResultService
from careerops.services.analysis_runs import compute_analysis_fingerprint
from careerops.services.hybrid_retrieval import EvidenceRetriever, LexicalEvidenceRetriever


class EvidenceMatcher(Protocol):
    @property
    def model_name(self) -> str: ...

    async def match(
        self,
        candidate_sets: tuple[RequirementCandidateSet, ...],
    ) -> EvidenceMatcherOutput: ...


class AnalysisRunExecutionStore(Protocol):
    async def claim_analysis_run(self, analysis_run_id: UUID) -> AnalysisRunWorkItem | None: ...

    async def load_analysis_input(self, work_item: AnalysisRunWorkItem) -> AnalysisInput: ...

    async def fail_analysis_run(
        self,
        analysis_run_id: UUID,
        attempt: int,
        model_name: str,
        error_code: AnalysisRunErrorCode,
        latency_ms: int,
    ) -> bool: ...

    async def commit(self) -> None: ...


class AnalysisRunExecutionService:
    def __init__(
        self,
        store: AnalysisRunExecutionStore,
        results: AnalysisResultService,
        matcher: EvidenceMatcher,
        retriever: EvidenceRetriever | None = None,
        retriever_factory: Callable[[AnalysisRunWorkItem], EvidenceRetriever] | None = None,
    ) -> None:
        self._store = store
        self._results = results
        self._matcher = matcher
        fixed_retriever = retriever or LexicalEvidenceRetriever()
        self._retriever_factory = retriever_factory or (lambda work_item: fixed_retriever)

    async def execute(self, analysis_run_id: UUID) -> bool:
        work_item = await self._store.claim_analysis_run(analysis_run_id)
        if work_item is None:
            return False
        await self._store.commit()

        started = perf_counter()
        analysis_input = await self._store.load_analysis_input(work_item)
        current_fingerprint = compute_analysis_fingerprint(
            work_item.parse_run_id,
            analysis_input.parse_input_fingerprint,
            analysis_input.experiences,
            work_item.prompt_version,
        )
        if current_fingerprint != work_item.input_fingerprint:
            await self._fail(
                analysis_run_id,
                work_item.attempt,
                AnalysisRunErrorCode.ANALYSIS_INPUT_CHANGED,
                elapsed_milliseconds(started),
            )
            return True

        candidate_sets = await self._retriever_factory(work_item).retrieve(
            user_id=work_item.user_id,
            requirements=analysis_input.requirements,
            experiences=analysis_input.experiences,
            available_before=work_item.created_at,
        )
        try:
            output = await self._matcher.match(candidate_sets)
            validated_matches = validate_matcher_output(
                output,
                candidate_sets,
                work_item.user_id,
                analysis_input,
            )
        except EvidenceMatcherError:
            await self._fail(
                analysis_run_id,
                work_item.attempt,
                AnalysisRunErrorCode.MATCHER_FAILED,
                elapsed_milliseconds(started),
            )
            return True
        except MatcherOutputValidationError:
            await self._fail(
                analysis_run_id,
                work_item.attempt,
                AnalysisRunErrorCode.MATCHER_OUTPUT_INVALID,
                elapsed_milliseconds(started),
            )
            return True

        return await self._results.complete(
            analysis_run_id,
            work_item.attempt,
            validated_matches,
            model_name=output.model_name,
            latency_ms=elapsed_milliseconds(started),
            input_tokens=output.input_tokens,
            output_tokens=output.output_tokens,
        )

    async def _fail(
        self,
        analysis_run_id: UUID,
        attempt: int,
        error_code: AnalysisRunErrorCode,
        latency_ms: int,
    ) -> None:
        failed = await self._store.fail_analysis_run(
            analysis_run_id,
            attempt,
            self._matcher.model_name,
            error_code,
            latency_ms,
        )
        if failed:
            await self._store.commit()


def validate_matcher_output(
    output: EvidenceMatcherOutput,
    candidate_sets: tuple[RequirementCandidateSet, ...],
    user_id: UUID,
    analysis_input: AnalysisInput,
) -> tuple[ValidatedEvidenceMatch, ...]:
    expected_ids = tuple(candidate_set.requirement.id for candidate_set in candidate_sets)
    proposed_ids = tuple(match.requirement_id for match in output.matches)
    if (
        output.model_name.strip() == ""
        or len(proposed_ids) != len(expected_ids)
        or len(set(proposed_ids)) != len(proposed_ids)
        or set(proposed_ids) != set(expected_ids)
        or any(
            match.confidence is not None and not 0 <= match.confidence <= 1
            for match in output.matches
        )
    ):
        raise MatcherOutputValidationError()

    proposals = {match.requirement_id: match for match in output.matches}
    experiences = {experience.id: experience for experience in analysis_input.experiences}
    return tuple(
        validate_evidence_match(
            proposals[candidate_set.requirement.id],
            user_id=user_id,
            experiences=experiences,
            candidate_experience_ids={
                candidate.experience.id for candidate in candidate_set.candidates
            },
        )
        for candidate_set in candidate_sets
    )


def elapsed_milliseconds(started: float) -> int:
    return int((perf_counter() - started) * 1000)
