from typing import Protocol
from uuid import UUID

from careerops.domain.evidence_matching import ValidatedEvidenceMatch


class AnalysisResultStore(Protocol):
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
    ) -> bool: ...

    async def commit(self) -> None: ...


class AnalysisResultService:
    def __init__(self, results: AnalysisResultStore) -> None:
        self._results = results

    async def complete(
        self,
        analysis_run_id: UUID,
        attempt: int,
        matches: tuple[ValidatedEvidenceMatch, ...],
        model_name: str,
        latency_ms: int,
        input_tokens: int | None,
        output_tokens: int | None,
    ) -> bool:
        completed = await self._results.complete_analysis_run(
            analysis_run_id=analysis_run_id,
            attempt=attempt,
            matches=matches,
            validation_failure_count=sum(match.validation_failed for match in matches),
            model_name=model_name,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        if not completed:
            return False
        await self._results.commit()
        return True
