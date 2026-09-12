from uuid import UUID

import dramatiq

from careerops.adapters.factory import create_requirement_parser
from careerops.adapters.fake_evidence_matcher import FakeEvidenceMatcher
from careerops.core.config import get_settings
from careerops.db.session import create_session_factory
from careerops.repositories.analysis_results import AnalysisResultRepository
from careerops.repositories.analysis_runs import AnalysisRunRepository
from careerops.repositories.parse_runs import ParseRunRepository
from careerops.services.analysis_results import AnalysisResultService
from careerops.services.analysis_run_execution import AnalysisRunExecutionService, EvidenceMatcher
from careerops.services.parse_run_execution import ParseRunExecutionService, RequirementParser
from careerops.workers.broker import redis_broker

worker_session_factory = create_session_factory(get_settings().database_url)


@dramatiq.actor(
    actor_name="execute_parse_run",
    broker=redis_broker,
    queue_name="parse-runs",
    max_retries=0,
)
async def execute_parse_run(parse_run_id: str) -> None:
    settings = get_settings()
    await execute_parse_run_async(
        UUID(parse_run_id),
        create_requirement_parser(settings),
    )


async def execute_parse_run_async(
    parse_run_id: UUID,
    parser: RequirementParser,
) -> bool:
    async with worker_session_factory() as session:
        service = ParseRunExecutionService(
            store=ParseRunRepository(session),
            parser=parser,
        )
        return await service.execute(parse_run_id)


@dramatiq.actor(
    actor_name="execute_analysis_run",
    broker=redis_broker,
    queue_name="analysis-runs",
    max_retries=0,
)
async def execute_analysis_run(analysis_run_id: str) -> None:
    await execute_analysis_run_async(UUID(analysis_run_id), FakeEvidenceMatcher())


async def execute_analysis_run_async(
    analysis_run_id: UUID,
    matcher: EvidenceMatcher,
) -> bool:
    async with worker_session_factory() as session:
        service = AnalysisRunExecutionService(
            store=AnalysisRunRepository(session),
            results=AnalysisResultService(AnalysisResultRepository(session)),
            matcher=matcher,
        )
        return await service.execute(analysis_run_id)
