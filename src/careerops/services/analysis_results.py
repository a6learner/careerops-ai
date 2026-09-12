from typing import Protocol
from uuid import UUID

from careerops.domain.evidence_matching import ValidatedEvidenceMatch


class AnalysisResultStore(Protocol):
    async def complete_analysis_run(
        self,
        analysis_run_id: UUID,
        matches: tuple[ValidatedEvidenceMatch, ...],
        validation_failure_count: int,
    ) -> bool: ...

    async def commit(self) -> None: ...


class AnalysisResultService:
    def __init__(self, results: AnalysisResultStore) -> None:
        self._results = results

    async def complete(
        self,
        analysis_run_id: UUID,
        matches: tuple[ValidatedEvidenceMatch, ...],
    ) -> bool:
        completed = await self._results.complete_analysis_run(
            analysis_run_id=analysis_run_id,
            matches=matches,
            validation_failure_count=sum(match.validation_failed for match in matches),
        )
        if not completed:
            return False
        await self._results.commit()
        return True
