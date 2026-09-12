import asyncio
from typing import Protocol
from uuid import UUID

from dramatiq.errors import BrokerError
from redis.exceptions import RedisError

from careerops.domain.errors import AnalysisRunDispatchError, ParseRunDispatchError
from careerops.workers.tasks import execute_analysis_run, execute_parse_run


class ParseRunActor(Protocol):
    def send(self, parse_run_id: str) -> object: ...


class AnalysisRunActor(Protocol):
    def send(self, analysis_run_id: str) -> object: ...


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

    async def dispatch(self, analysis_run_id: UUID) -> None:
        try:
            await asyncio.to_thread(self._actor.send, str(analysis_run_id))
        except (BrokerError, RedisError) as exc:
            raise AnalysisRunDispatchError() from exc
