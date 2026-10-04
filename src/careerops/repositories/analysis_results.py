from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from careerops.db.models import AnalysisRun, EvidenceMatch
from careerops.domain.evidence_matching import ValidatedEvidenceMatch


class AnalysisResultRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

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
        result = await self._session.execute(
            update(AnalysisRun)
            .where(
                AnalysisRun.id == analysis_run_id,
                AnalysisRun.status == "running",
                AnalysisRun.attempt == attempt,
            )
            .values(
                status="succeeded",
                validation_failure_count=validation_failure_count,
                model_name=model_name,
                error_code=None,
                latency_ms=latency_ms,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                finished_at=datetime.now(UTC),
            )
            .returning(AnalysisRun.id)
        )
        if result.scalar_one_or_none() is None:
            return False

        self._session.add_all(
            [
                EvidenceMatch(
                    analysis_run_id=analysis_run_id,
                    requirement_id=match.requirement_id,
                    experience_id=match.experience_id,
                    experience_version=match.experience_version,
                    verdict=match.verdict.value,
                    quote=match.quote,
                    quote_valid=match.quote_valid,
                    confidence=match.confidence,
                )
                for match in matches
            ]
        )
        await self._session.flush()
        return True

    async def commit(self) -> None:
        await self._session.commit()
