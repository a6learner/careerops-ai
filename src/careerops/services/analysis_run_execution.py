import logging
from collections.abc import Callable
from dataclasses import dataclass
from math import isfinite
from time import perf_counter
from typing import Protocol
from uuid import UUID

from careerops.domain.analysis_runs import (
    AnalysisDispatchSource,
    AnalysisInput,
    AnalysisRunErrorCode,
    AnalysisRunWorkItem,
    EvidenceMatcherOutput,
    matcher_batch_size_from_pipeline,
    matcher_model_name_from_pipeline,
    matcher_prompt_version_from_pipeline,
)
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
    ValidatedEvidenceMatch,
    validate_evidence_match,
)
from careerops.domain.evidence_retrieval import RequirementCandidateSet
from careerops.services.analysis_results import AnalysisResultService
from careerops.services.analysis_runs import compute_analysis_fingerprint
from careerops.services.evidence_matcher_contract import build_evidence_matcher_input
from careerops.services.hybrid_retrieval import EvidenceRetriever, LexicalEvidenceRetriever

logger = logging.getLogger(__name__)


class EvidenceMatcher(Protocol):
    @property
    def model_name(self) -> str: ...

    async def match(
        self,
        matcher_input: EvidenceMatcherInput,
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
        input_tokens: int | None = None,
        output_tokens: int | None = None,
    ) -> bool: ...

    async def commit(self) -> None: ...


class AnalysisRunExecutionService:
    def __init__(
        self,
        store: AnalysisRunExecutionStore,
        results: AnalysisResultService,
        matcher: EvidenceMatcher | None = None,
        retriever: EvidenceRetriever | None = None,
        retriever_factory: Callable[[AnalysisRunWorkItem], EvidenceRetriever] | None = None,
        matcher_factory: Callable[[AnalysisRunWorkItem], EvidenceMatcher] | None = None,
    ) -> None:
        self._store = store
        self._results = results
        if (matcher is None) == (matcher_factory is None):
            raise ValueError("Provide exactly one matcher or matcher_factory.")
        self._matcher_factory = matcher_factory or _fixed_matcher_factory(matcher)
        fixed_retriever = retriever or LexicalEvidenceRetriever()
        self._retriever_factory = retriever_factory or (lambda work_item: fixed_retriever)

    async def execute(
        self,
        analysis_run_id: UUID,
        *,
        request_id: str = "unknown",
        dispatch_source: AnalysisDispatchSource = AnalysisDispatchSource.LEGACY,
    ) -> bool:
        work_item = await self._store.claim_analysis_run(analysis_run_id)
        if work_item is None:
            logger.info(
                "analysis_run_claim_skipped",
                extra={
                    "request_id": request_id,
                    "run_type": "analysis",
                    "run_id": str(analysis_run_id),
                    "dispatch_source": dispatch_source.value,
                    "outcome": "not_queued",
                },
            )
            return False
        await self._store.commit()
        logger.info(
            "analysis_run_claimed",
            extra=analysis_run_log_fields(work_item, request_id, dispatch_source),
        )

        started = perf_counter()
        matcher = self._matcher_factory(work_item)
        try:
            pipeline_matcher_model = matcher_model_name_from_pipeline(
                work_item.prompt_version
            )
        except ValueError:
            pipeline_matcher_model = ""
        if (
            pipeline_matcher_model != work_item.model_name
            or matcher.model_name != work_item.model_name
        ):
            await self._fail(
                analysis_run_id,
                work_item.attempt,
                work_item.model_name,
                AnalysisRunErrorCode.MATCHER_OUTPUT_INVALID_CONTRACT,
                elapsed_milliseconds(started),
                request_id=request_id,
                dispatch_source=dispatch_source,
            )
            return True
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
                matcher.model_name,
                AnalysisRunErrorCode.ANALYSIS_INPUT_CHANGED,
                elapsed_milliseconds(started),
                request_id=request_id,
                dispatch_source=dispatch_source,
            )
            return True

        candidate_sets = await self._retriever_factory(work_item).retrieve(
            user_id=work_item.user_id,
            requirements=analysis_input.requirements,
            experiences=analysis_input.experiences,
            available_before=work_item.created_at,
        )
        try:
            matcher_prompt_version = matcher_prompt_version_from_pipeline(
                work_item.prompt_version
            )
            batch_size = matcher_batch_size_from_pipeline(work_item.prompt_version)
        except ValueError:
            await self._fail(
                analysis_run_id,
                work_item.attempt,
                matcher.model_name,
                AnalysisRunErrorCode.MATCHER_OUTPUT_INVALID_CONTRACT,
                elapsed_milliseconds(started),
                request_id=request_id,
                dispatch_source=dispatch_source,
            )
            return True
        try:
            matched = await match_in_batches(
                matcher,
                candidate_sets,
                batch_size=batch_size,
                prompt_version=matcher_prompt_version,
                expected_model_name=work_item.model_name,
                user_id=work_item.user_id,
                analysis_input=analysis_input,
            )
        except MatcherBatchFailure as failure:
            await self._fail_batch(
                analysis_run_id,
                work_item,
                matcher.model_name,
                failure,
                elapsed_milliseconds(started),
                request_id=request_id,
                dispatch_source=dispatch_source,
            )
            return True
        latency_ms = elapsed_milliseconds(started)
        completed = await self._results.complete(
            analysis_run_id,
            work_item.attempt,
            matched.matches,
            model_name=matched.model_name,
            latency_ms=latency_ms,
            input_tokens=matched.input_tokens,
            output_tokens=matched.output_tokens,
        )
        logger.log(
            logging.INFO if completed else logging.WARNING,
            "analysis_run_succeeded" if completed else "analysis_run_persistence_fenced",
            extra={
                **analysis_run_log_fields(work_item, request_id, dispatch_source),
                "outcome": "succeeded" if completed else "stale_attempt",
                "latency_ms": latency_ms,
                "input_tokens": matched.input_tokens,
                "output_tokens": matched.output_tokens,
                "batch_count": matched.batch_count,
            },
        )
        return completed

    async def _fail_batch(
        self,
        analysis_run_id: UUID,
        work_item: AnalysisRunWorkItem,
        model_name: str,
        failure: "MatcherBatchFailure",
        latency_ms: int,
        *,
        request_id: str,
        dispatch_source: AnalysisDispatchSource,
    ) -> bool:
        cause = failure.cause
        if isinstance(cause, EvidenceMatcherError):
            error_code = provider_error_code(cause.reason)
        else:
            error_code = output_error_code(cause.reason)
            logger.warning(
                "evidence_matcher_output_rejected",
                extra={
                    **analysis_run_log_fields(work_item, request_id, dispatch_source),
                    "failure_reason": cause.reason.value,
                    "diagnostic": cause.diagnostic,
                    "response_sha256": cause.response_sha256,
                    "response_size_bytes": cause.response_size_bytes,
                    "batch_index": failure.batch_index,
                    "batch_count": failure.batch_count,
                },
            )
        return await self._fail(
            analysis_run_id,
            work_item.attempt,
            model_name,
            error_code,
            latency_ms,
            request_id=request_id,
            dispatch_source=dispatch_source,
            input_tokens=failure.input_tokens,
            output_tokens=failure.output_tokens,
        )

    async def _fail(
        self,
        analysis_run_id: UUID,
        attempt: int,
        model_name: str,
        error_code: AnalysisRunErrorCode,
        latency_ms: int,
        *,
        request_id: str,
        dispatch_source: AnalysisDispatchSource,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
    ) -> bool:
        failed = await self._store.fail_analysis_run(
            analysis_run_id,
            attempt,
            model_name,
            error_code,
            latency_ms,
            input_tokens,
            output_tokens,
        )
        if failed:
            await self._store.commit()
        logger.log(
            logging.WARNING,
            "analysis_run_failed" if failed else "analysis_run_persistence_fenced",
            extra={
                "request_id": request_id,
                "run_type": "analysis",
                "run_id": str(analysis_run_id),
                "attempt": attempt,
                "dispatch_source": dispatch_source.value,
                "model_name": model_name,
                "outcome": "failed" if failed else "stale_attempt",
                "error_code": error_code.value,
                "latency_ms": latency_ms,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            },
        )
        return failed


def analysis_run_log_fields(
    work_item: AnalysisRunWorkItem,
    request_id: str,
    dispatch_source: AnalysisDispatchSource,
) -> dict[str, object]:
    return {
        "request_id": request_id,
        "user_id": str(work_item.user_id),
        "run_type": "analysis",
        "run_id": str(work_item.id),
        "attempt": work_item.attempt,
        "dispatch_source": dispatch_source.value,
        "pipeline_version": work_item.prompt_version,
        "model_name": work_item.model_name,
    }


def _fixed_matcher_factory(
    matcher: EvidenceMatcher | None,
) -> Callable[[AnalysisRunWorkItem], EvidenceMatcher]:
    if matcher is None:
        raise ValueError("A fixed matcher is required.")
    return lambda work_item: matcher


@dataclass(frozen=True)
class MatchedBatches:
    matches: tuple[ValidatedEvidenceMatch, ...]
    model_name: str
    input_tokens: int | None
    output_tokens: int | None
    batch_count: int


class MatcherBatchFailure(Exception):
    def __init__(
        self,
        cause: EvidenceMatcherError | MatcherOutputValidationError,
        *,
        batch_index: int,
        batch_count: int,
        input_tokens: int | None,
        output_tokens: int | None,
    ) -> None:
        super().__init__("Evidence matcher batch failed.")
        self.cause = cause
        self.batch_index = batch_index
        self.batch_count = batch_count
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


def split_candidate_sets(
    candidate_sets: tuple[RequirementCandidateSet, ...],
    batch_size: int | None,
) -> tuple[tuple[RequirementCandidateSet, ...], ...]:
    if batch_size is None or len(candidate_sets) <= batch_size:
        return (candidate_sets,)
    return tuple(
        candidate_sets[start : start + batch_size]
        for start in range(0, len(candidate_sets), batch_size)
    )


async def match_in_batches(
    matcher: EvidenceMatcher,
    candidate_sets: tuple[RequirementCandidateSet, ...],
    *,
    batch_size: int | None,
    prompt_version: str,
    expected_model_name: str,
    user_id: UUID,
    analysis_input: AnalysisInput,
) -> MatchedBatches:
    batches = split_candidate_sets(candidate_sets, batch_size)
    matches: list[ValidatedEvidenceMatch] = []
    input_tokens: list[int | None] = []
    output_tokens: list[int | None] = []
    for batch_index, batch in enumerate(batches):
        try:
            output = await matcher.match(
                build_evidence_matcher_input(batch, prompt_version=prompt_version)
            )
            input_tokens.append(output.input_tokens)
            output_tokens.append(output.output_tokens)
            if output.model_name != expected_model_name:
                raise MatcherOutputValidationError(MatcherOutputFailureReason.INVALID_CONTRACT)
            matches.extend(validate_matcher_output(output, batch, user_id, analysis_input))
        except (EvidenceMatcherError, MatcherOutputValidationError) as exc:
            if isinstance(exc, MatcherOutputValidationError) and len(input_tokens) == batch_index:
                input_tokens.append(exc.input_tokens)
                output_tokens.append(exc.output_tokens)
            raise MatcherBatchFailure(
                exc,
                batch_index=batch_index,
                batch_count=len(batches),
                input_tokens=sum_known_tokens(input_tokens),
                output_tokens=sum_known_tokens(output_tokens),
            ) from exc
    return MatchedBatches(
        matches=tuple(matches),
        model_name=expected_model_name,
        input_tokens=sum_known_tokens(input_tokens),
        output_tokens=sum_known_tokens(output_tokens),
        batch_count=len(batches),
    )


def sum_known_tokens(values: list[int | None]) -> int | None:
    known = [value for value in values if value is not None]
    return sum(known) if known else None


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
            match.confidence is not None
            and (not isfinite(match.confidence) or not 0 <= match.confidence <= 1)
            for match in output.matches
        )
        or any(not _proposal_shape_is_valid(match) for match in output.matches)
    ):
        raise MatcherOutputValidationError(
            MatcherOutputFailureReason.INVALID_CONTRACT,
            diagnostic=contract_diagnostic(expected_ids, proposed_ids, output),
            input_tokens=output.input_tokens,
            output_tokens=output.output_tokens,
        )

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


def contract_diagnostic(
    expected_ids: tuple[UUID, ...],
    proposed_ids: tuple[UUID, ...],
    output: EvidenceMatcherOutput,
) -> str:
    expected = set(expected_ids)
    proposed = set(proposed_ids)
    invalid_shapes = sum(not _proposal_shape_is_valid(match) for match in output.matches)
    return (
        f"expected={len(expected_ids)};returned={len(proposed_ids)};"
        f"missing={len(expected - proposed)};unknown={len(proposed - expected)};"
        f"duplicates={len(proposed_ids) - len(proposed)};invalid_shape={invalid_shapes}"
    )


def _proposal_shape_is_valid(proposal: ProposedEvidenceMatch) -> bool:
    evidence_values = (
        proposal.experience_id,
        proposal.experience_version,
        proposal.source_ref,
        proposal.quote,
    )
    if proposal.verdict in {EvidenceVerdict.MATCHED, EvidenceVerdict.PARTIAL}:
        return (
            all(value is not None for value in evidence_values)
            and proposal.experience_version is not None
            and proposal.experience_version >= 1
            and proposal.source_ref is not None
            and proposal.source_ref.strip() != ""
            and proposal.quote is not None
            and proposal.quote.strip() != ""
        )
    return all(value is None for value in evidence_values)


def provider_error_code(reason: EvidenceMatcherFailureReason) -> AnalysisRunErrorCode:
    return {
        EvidenceMatcherFailureReason.REQUEST_FAILED: AnalysisRunErrorCode.MATCHER_PROVIDER_FAILED,
        EvidenceMatcherFailureReason.DISABLED: AnalysisRunErrorCode.MATCHER_PROVIDER_DISABLED,
        EvidenceMatcherFailureReason.MISCONFIGURED: (
            AnalysisRunErrorCode.MATCHER_PROVIDER_MISCONFIGURED
        ),
        EvidenceMatcherFailureReason.TIMEOUT: AnalysisRunErrorCode.MATCHER_PROVIDER_TIMEOUT,
        EvidenceMatcherFailureReason.RATE_LIMITED: (
            AnalysisRunErrorCode.MATCHER_PROVIDER_RATE_LIMITED
        ),
        EvidenceMatcherFailureReason.UNAVAILABLE: (
            AnalysisRunErrorCode.MATCHER_PROVIDER_UNAVAILABLE
        ),
    }[reason]


def output_error_code(reason: MatcherOutputFailureReason) -> AnalysisRunErrorCode:
    return {
        MatcherOutputFailureReason.INVALID_JSON: (
            AnalysisRunErrorCode.MATCHER_OUTPUT_INVALID_JSON
        ),
        MatcherOutputFailureReason.INVALID_SCHEMA: (
            AnalysisRunErrorCode.MATCHER_OUTPUT_INVALID_SCHEMA
        ),
        MatcherOutputFailureReason.INVALID_CONTRACT: (
            AnalysisRunErrorCode.MATCHER_OUTPUT_INVALID_CONTRACT
        ),
    }[reason]


def elapsed_milliseconds(started: float) -> int:
    return int((perf_counter() - started) * 1000)
