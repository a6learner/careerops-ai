import asyncio
from datetime import UTC, datetime, timedelta
from typing import cast

from sqlalchemy.ext.asyncio import AsyncEngine

from careerops.core.config import get_settings
from careerops.db.session import create_session_factory
from careerops.domain.embeddings import EMBEDDING_INPUT_VERSION, FAKE_EMBEDDING_MODEL_NAME
from careerops.repositories.embedding_runs import EmbeddingRunRepository
from careerops.services.embedding_recovery import (
    EmbeddingRecoveryResult,
    EmbeddingRecoveryService,
)
from careerops.workers.dispatcher import DramatiqEmbeddingRunDispatcher


async def recover_embedding_runs() -> EmbeddingRecoveryResult:
    settings = get_settings()
    session_factory = create_session_factory(settings.database_url)
    try:
        async with session_factory() as session:
            service = EmbeddingRecoveryService(
                store=EmbeddingRunRepository(session),
                dispatcher=DramatiqEmbeddingRunDispatcher(),
                model_name=FAKE_EMBEDDING_MODEL_NAME,
                input_version=EMBEDDING_INPUT_VERSION,
            )
            stale_before = datetime.now(UTC) - timedelta(
                seconds=settings.embedding_run_stale_after_seconds
            )
            return await service.recover(
                stale_before,
                settings.embedding_run_recovery_batch_size,
            )
    finally:
        engine = cast(AsyncEngine, session_factory.kw["bind"])
        await engine.dispose()


def main() -> None:
    result = asyncio.run(recover_embedding_runs())
    print(
        f"reconciled={result.reconciled} requeued={result.requeued} "
        f"dispatched={result.dispatched} dispatch_failed={result.dispatch_failed}"
    )
    if result.dispatch_failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
