from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from http import HTTPStatus
from typing import cast

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncEngine

from careerops.api.auth import router as auth_router
from careerops.api.routes import router
from careerops.core.config import Settings, get_settings
from careerops.core.errors import ErrorCode, ErrorDetail, ErrorResponse
from careerops.core.logging import configure_logging
from careerops.core.request_id import RequestIdMiddleware
from careerops.db.health import DatabaseReadinessChecker
from careerops.db.session import create_session_factory
from careerops.domain.errors import DuplicateEmailError


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = cast(Settings, app.state.settings)
    app.state.db_checker = DatabaseReadinessChecker(settings.database_url)
    session_factory = create_session_factory(settings.database_url)
    app.state.session_factory = session_factory
    yield
    await cast(AsyncEngine, session_factory.kw["bind"]).dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(title="CareerOps AI", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.add_middleware(RequestIdMiddleware)
    app.include_router(router)
    app.include_router(auth_router)

    @app.exception_handler(DuplicateEmailError)
    async def duplicate_email_handler(request: Request, exc: DuplicateEmailError) -> JSONResponse:
        request_id = cast(str, getattr(request.state, "request_id", "unknown"))
        payload = ErrorResponse(
            error=ErrorDetail(
                code=ErrorCode.EMAIL_ALREADY_REGISTERED,
                message="Email is already registered.",
                request_id=request_id,
            )
        )
        return JSONResponse(
            status_code=HTTPStatus.CONFLICT,
            content=payload.model_dump(mode="json"),
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = cast(str, getattr(request.state, "request_id", "unknown"))
        payload = ErrorResponse(
            error=ErrorDetail(
                code=ErrorCode.DEPENDENCY_UNAVAILABLE,
                message=HTTPStatus.INTERNAL_SERVER_ERROR.phrase,
                request_id=request_id,
            )
        )
        return JSONResponse(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            content=payload.model_dump(mode="json"),
        )

    return app
