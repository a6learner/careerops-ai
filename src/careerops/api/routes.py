import asyncio
import logging
from typing import cast

from fastapi import APIRouter, Request, Response, status

from careerops.cache.health import RedisReadinessChecker
from careerops.core.config import Settings
from careerops.core.request_id import request_id_from_request
from careerops.db.health import DatabaseReadinessChecker
from careerops.schemas.health import HealthCheck, ReadinessCheck

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/healthz", response_model=HealthCheck)
async def healthz(request: Request) -> HealthCheck:
    settings = cast(Settings, request.app.state.settings)
    return HealthCheck(status="ok", service=settings.service_name)


@router.get(
    "/readyz",
    response_model=ReadinessCheck,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ReadinessCheck}},
)
async def readyz(request: Request, response: Response) -> ReadinessCheck:
    database_checker = cast(DatabaseReadinessChecker, request.app.state.db_checker)
    redis_checker = cast(RedisReadinessChecker, request.app.state.redis_checker)
    database_ready, redis_ready = await asyncio.gather(
        database_checker.is_ready(),
        redis_checker.is_ready(),
    )
    if database_ready and redis_ready:
        return ReadinessCheck(status="ready", database=True, redis=True)

    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    logger.warning(
        "readiness_check_failed",
        extra={
            "request_id": request_id_from_request(request),
            "database_ready": database_ready,
            "redis_ready": redis_ready,
        },
    )
    return ReadinessCheck(
        status="not_ready",
        database=database_ready,
        redis=redis_ready,
    )
