import asyncio
import logging
from typing import Protocol
from uuid import UUID

from dramatiq.errors import BrokerError
from redis.exceptions import RedisError

from careerops.domain.analysis_runs import AnalysisDispatchSource
from careerops.domain.errors import (
    AnalysisRunDispatchError,
    EmbeddingRunDispatchError,
    ParseRunDispatchError,
)
from careerops.workers.tasks import execute_analysis_run, execute_embedding_run, execute_parse_run

logger = logging.getLogger(__name__)


class ParseRunActor(Protocol):
    def send(self, parse_run_id: str) -> object: ...


class AnalysisRunActor(Protocol):
    def send(
        self,
        analysis_run_id: str,
        request_id: str,
        dispatch_source: str,
    ) -> object: ...


class EmbeddingRunActor(Protocol):
    def send(self, embedding_run_id: str) -> object: ...


class DramatiqParseRunDispatcher:
    def __init__(self, actor: ParseRunActor = execute_parse_run) -> None:
        self._actor = actor

    async def dispatch(self, parse_run_id: UUID) -> None:
        try:
            await asyncio.to_thread(self._actor.send, str(parse_run_id))
        except (BrokerError, RedisError) as exc:
            raise ParseRunDispatchError() from exc


class DramatiqAnalysisRunDispatcher:
    def __init__(self, actor: AnalysisRunActor = execute_analysis_run) -> None:
        self._actor = actor

    async def dispatch(
        self,
        analysis_run_id: UUID,
        request_id: str,
        dispatch_source: AnalysisDispatchSource,
    ) -> None:
        try:
            await asyncio.to_thread(
                self._actor.send,
                str(analysis_run_id),
                request_id,
                dispatch_source.value,
            )
        except (BrokerError, RedisError) as exc:
            logger.warning(
                "analysis_run_dispatch_failed",
                extra={
                    "request_id": request_id,
                    "run_type": "analysis",
                    "run_id": str(analysis_run_id),
                    "dispatch_source": dispatch_source.value,
                    "error_type": type(exc).__name__,
                },
            )
            raise AnalysisRunDispatchError() from exc
        logger.info(
            "analysis_run_dispatched",
            extra={
                "request_id": request_id,
                "run_type": "analysis",
                "run_id": str(analysis_run_id),
                "dispatch_source": dispatch_source.value,
            },
        )


class DramatiqEmbeddingRunDispatcher:
    def __init__(self, actor: EmbeddingRunActor = execute_embedding_run) -> None:
        self._actor = actor

    async def dispatch(self, embedding_run_id: UUID) -> None:
        try:
            await asyncio.to_thread(self._actor.send, str(embedding_run_id))
        except (BrokerError, RedisError) as exc:
            raise EmbeddingRunDispatchError() from exc
