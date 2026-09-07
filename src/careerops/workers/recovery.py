import asyncio
from datetime import UTC, datetime, timedelta
from typing import cast

from sqlalchemy.ext.asyncio import AsyncEngine

from careerops.core.config import get_settings
from careerops.db.session import create_session_factory
from careerops.repositories.parse_runs import ParseRunRepository
from careerops.services.parse_run_recovery import ParseRunRecoveryResult, ParseRunRecoveryService
from careerops.workers.dispatcher import DramatiqParseRunDispatcher


async def recover_parse_runs() -> ParseRunRecoveryResult:
    settings = get_settings()
    session_factory = create_session_factory(settings.database_url)
    try:
        async with session_factory() as session:
            service = ParseRunRecoveryService(
                store=ParseRunRepository(session),
                dispatcher=DramatiqParseRunDispatcher(),
            )
            stale_before = datetime.now(UTC) - timedelta(
                seconds=settings.parse_run_stale_after_seconds
            )
            return await service.recover(stale_before, settings.parse_run_recovery_batch_size)
    finally:
        engine = cast(AsyncEngine, session_factory.kw["bind"])
        await engine.dispose()


def main() -> None:
    result = asyncio.run(recover_parse_runs())
    print(
        f"requeued={result.requeued} dispatched={result.dispatched} "
        f"dispatch_failed={result.dispatch_failed}"
    )
    if result.dispatch_failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
