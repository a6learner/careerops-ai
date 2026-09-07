from uuid import UUID

import dramatiq

from careerops.adapters.fake_requirement_parser import FakeRequirementParser
from careerops.core.config import get_settings
from careerops.db.session import create_session_factory
from careerops.repositories.parse_runs import ParseRunRepository
from careerops.services.parse_run_execution import ParseRunExecutionService
from careerops.workers.broker import redis_broker

worker_session_factory = create_session_factory(get_settings().database_url)


@dramatiq.actor(
    actor_name="execute_parse_run",
    broker=redis_broker,
    queue_name="parse-runs",
    max_retries=0,
)
async def execute_parse_run(parse_run_id: str) -> None:
    await execute_parse_run_async(UUID(parse_run_id))


async def execute_parse_run_async(parse_run_id: UUID) -> bool:
    async with worker_session_factory() as session:
        service = ParseRunExecutionService(
            store=ParseRunRepository(session),
            parser=FakeRequirementParser(),
        )
        return await service.execute(parse_run_id)
