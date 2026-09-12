import asyncio
from datetime import UTC, datetime, timedelta
from typing import cast

from sqlalchemy.ext.asyncio import AsyncEngine

from careerops.core.config import get_settings
from careerops.db.session import create_session_factory
from careerops.repositories.analysis_runs import AnalysisRunRepository
from careerops.services.analysis_run_recovery import (
    AnalysisRunRecoveryResult,
    AnalysisRunRecoveryService,
)
from careerops.workers.dispatcher import DramatiqAnalysisRunDispatcher


async def recover_analysis_runs() -> AnalysisRunRecoveryResult:
    settings = get_settings()
    session_factory = create_session_factory(settings.database_url)
    try:
        async with session_factory() as session:
            service = AnalysisRunRecoveryService(
                store=AnalysisRunRepository(session),
                dispatcher=DramatiqAnalysisRunDispatcher(),
            )
            stale_before = datetime.now(UTC) - timedelta(
                seconds=settings.analysis_run_stale_after_seconds
            )
            return await service.recover(
                stale_before,
                settings.analysis_run_recovery_batch_size,
            )
    finally:
        engine = cast(AsyncEngine, session_factory.kw["bind"])
        await engine.dispose()


def main() -> None:
    result = asyncio.run(recover_analysis_runs())
    print(
        f"requeued={result.requeued} dispatched={result.dispatched} "
        f"dispatch_failed={result.dispatch_failed}"
    )
    if result.dispatch_failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
