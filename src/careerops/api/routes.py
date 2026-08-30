from typing import cast

from fastapi import APIRouter, Request, status

from careerops.core.config import Settings
from careerops.db.health import DatabaseReadinessChecker
from careerops.schemas.health import HealthCheck, ReadinessCheck

router = APIRouter()


@router.get("/healthz", response_model=HealthCheck)
async def healthz(request: Request) -> HealthCheck:
    settings = cast(Settings, request.app.state.settings)
    return HealthCheck(status="ok", service=settings.service_name)


@router.get(
    "/readyz",
    response_model=ReadinessCheck,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ReadinessCheck}},
)
async def readyz(request: Request) -> ReadinessCheck:
    checker = cast(DatabaseReadinessChecker, request.app.state.db_checker)
    database_ready = await checker.is_ready()
    if database_ready:
        return ReadinessCheck(status="ready", database=True)
    return ReadinessCheck(status="not_ready", database=False)
