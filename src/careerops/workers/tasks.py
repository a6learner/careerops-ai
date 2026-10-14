import logging
from uuid import UUID

import dramatiq

from careerops.adapters.embedding_factory import ConfiguredEmbeddingProviderResolver
from careerops.adapters.evidence_matcher_factory import ConfiguredEvidenceMatcherResolver
from careerops.adapters.factory import create_requirement_parser
from careerops.adapters.fake_job_search import FakeJobSearchProvider
from careerops.core.config import get_settings
from careerops.core.logging import configure_logging
from careerops.core.request_id import normalize_request_id
from careerops.db.session import create_session_factory
from careerops.domain.analysis_runs import AnalysisDispatchSource, AnalysisRunWorkItem
from careerops.domain.embeddings import embedding_space_for_analysis_pipeline
from careerops.repositories.analysis_results import AnalysisResultRepository
from careerops.repositories.analysis_runs import AnalysisRunRepository
from careerops.repositories.assisted_imports import AssistedImportRepository
from careerops.repositories.embedding_runs import EmbeddingRunRepository
from careerops.repositories.evidence_retrieval import EvidenceVectorRepository
from careerops.repositories.parse_runs import ParseRunRepository
from careerops.services.analysis_results import AnalysisResultService
from careerops.services.analysis_run_execution import AnalysisRunExecutionService, EvidenceMatcher
from careerops.services.assisted_imports import (
    CvImportExecutionService,
    JobDiscoveryExecutionService,
)
from careerops.services.embedding_execution import EmbeddingExecutionService
from careerops.services.hybrid_retrieval import HybridEvidenceRetriever
from careerops.services.parse_run_execution import ParseRunExecutionService, RequirementParser
from careerops.workers.broker import redis_broker

worker_session_factory = create_session_factory(get_settings().database_url)
logger = logging.getLogger(__name__)


def build_hybrid_retriever(
    work_item: AnalysisRunWorkItem,
    vectors: EvidenceVectorRepository,
    resolver: ConfiguredEmbeddingProviderResolver,
) -> HybridEvidenceRetriever:
    space = embedding_space_for_analysis_pipeline(work_item.prompt_version)
    return HybridEvidenceRetriever(
        vectors=vectors,
        provider=resolver.resolve(space.model_name, space.document_input_version),
        space=space,
    )


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
async def execute_analysis_run(
    analysis_run_id: str,
    request_id: str | None = None,
    dispatch_source: str = AnalysisDispatchSource.LEGACY.value,
) -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    safe_request_id = normalize_request_id(request_id)
    source = parse_analysis_dispatch_source(dispatch_source)
    logger.info(
        "analysis_worker_delivery_received",
        extra={
            "request_id": safe_request_id,
            "run_type": "analysis",
            "run_id": analysis_run_id,
            "dispatch_source": source.value,
        },
    )
    await execute_analysis_run_async(
        UUID(analysis_run_id),
        request_id=safe_request_id,
        dispatch_source=source,
    )


async def execute_analysis_run_async(
    analysis_run_id: UUID,
    matcher: EvidenceMatcher | None = None,
    *,
    request_id: str | None = None,
    dispatch_source: AnalysisDispatchSource = AnalysisDispatchSource.LEGACY,
) -> bool:
    safe_request_id = normalize_request_id(request_id)
    async with worker_session_factory() as session:
        settings = get_settings()
        resolver = ConfiguredEmbeddingProviderResolver(settings)
        matcher_resolver = ConfiguredEvidenceMatcherResolver(settings)
        vectors = EvidenceVectorRepository(session)
        service = AnalysisRunExecutionService(
            store=AnalysisRunRepository(session),
            results=AnalysisResultService(AnalysisResultRepository(session)),
            matcher=matcher,
            matcher_factory=(
                None
                if matcher is not None
                else lambda work_item: matcher_resolver.resolve_pipeline(
                    work_item.model_name,
                    work_item.prompt_version,
                )
            ),
            retriever_factory=lambda work_item: build_hybrid_retriever(
                work_item,
                vectors,
                resolver,
            ),
        )
        return await service.execute(
            analysis_run_id,
            request_id=safe_request_id,
            dispatch_source=dispatch_source,
        )


def parse_analysis_dispatch_source(value: str) -> AnalysisDispatchSource:
    try:
        return AnalysisDispatchSource(value)
    except ValueError:
        return AnalysisDispatchSource.LEGACY


@dramatiq.actor(
    actor_name="execute_embedding_run",
    broker=redis_broker,
    queue_name="embedding-runs",
    max_retries=0,
)
async def execute_embedding_run(embedding_run_id: str) -> None:
    await execute_embedding_run_async(UUID(embedding_run_id))


async def execute_embedding_run_async(
    embedding_run_id: UUID,
) -> bool:
    async with worker_session_factory() as session:
        service = EmbeddingExecutionService(
            store=EmbeddingRunRepository(session),
            providers=ConfiguredEmbeddingProviderResolver(get_settings()),
        )
        return await service.execute(embedding_run_id)


@dramatiq.actor(
    actor_name="execute_cv_import",
    broker=redis_broker,
    queue_name="cv-imports",
    max_retries=0,
)
async def execute_cv_import(cv_import_id: str) -> None:
    async with worker_session_factory() as session:
        service = CvImportExecutionService(AssistedImportRepository(session))
        await service.execute(UUID(cv_import_id))


@dramatiq.actor(
    actor_name="execute_job_discovery",
    broker=redis_broker,
    queue_name="job-discovery",
    max_retries=0,
)
async def execute_job_discovery(run_id: str) -> None:
    async with worker_session_factory() as session:
        service = JobDiscoveryExecutionService(
            AssistedImportRepository(session), FakeJobSearchProvider()
        )
        await service.execute(UUID(run_id))
