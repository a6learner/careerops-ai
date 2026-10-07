import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from http import HTTPStatus
from typing import cast

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine

from careerops.adapters.redis_analysis_rate_limiter import RedisAnalysisRateLimiter
from careerops.api.action_items import router as action_items_router
from careerops.api.analysis_runs import router as analysis_runs_router
from careerops.api.auth import router as auth_router
from careerops.api.dashboard import router as dashboard_router
from careerops.api.experiences import router as experiences_router
from careerops.api.jobs import router as jobs_router
from careerops.api.parse_runs import router as parse_runs_router
from careerops.api.routes import router
from careerops.cache.dashboard import RedisDashboardCache
from careerops.cache.health import RedisReadinessChecker
from careerops.core.config import Settings, get_settings
from careerops.core.errors import ErrorCode, ErrorDetail, ErrorResponse
from careerops.core.logging import configure_logging
from careerops.core.request_id import RequestIdMiddleware
from careerops.db.health import DatabaseReadinessChecker
from careerops.db.session import create_session_factory
from careerops.domain.errors import (
    ActionItemNotFoundError,
    ActionItemSourceNotActionableError,
    ActionItemSourceNotFoundError,
    ActionItemVersionConflictError,
    AnalysisRateLimitExceededError,
    AnalysisRateLimitUnavailableError,
    AnalysisRunDispatchError,
    AnalysisRunNotFoundError,
    DuplicateEmailError,
    ExperienceNotFoundError,
    ExperienceVersionConflictError,
    ExpiredTokenError,
    IdempotencyKeyConflictError,
    InvalidCredentialsError,
    InvalidCursorError,
    InvalidTokenError,
    JobNotFoundError,
    JobVersionConflictError,
    MissingIdempotencyKeyError,
    MissingIfMatchHeaderError,
    MissingTokenError,
    NoActiveExperiencesError,
    ParseRunDispatchError,
    ParseRunNotFoundError,
    ParseRunNotReadyError,
)
from careerops.workers.dispatcher import (
    DramatiqAnalysisRunDispatcher,
    DramatiqEmbeddingRunDispatcher,
    DramatiqParseRunDispatcher,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = cast(Settings, app.state.settings)
    app.state.db_checker = DatabaseReadinessChecker(settings.database_url)
    session_factory = create_session_factory(settings.database_url)
    app.state.session_factory = session_factory
    yield
    await cast(Redis, app.state.redis_client).aclose()
    await cast(AsyncEngine, session_factory.kw["bind"]).dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(title="CareerOps AI", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    redis_client = Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=settings.redis_socket_timeout_seconds,
        socket_timeout=settings.redis_socket_timeout_seconds,
    )
    app.state.redis_client = redis_client
    app.state.redis_checker = RedisReadinessChecker(redis_client)
    app.state.dashboard_cache = RedisDashboardCache(
        redis_client,
        ttl_seconds=settings.dashboard_cache_ttl_seconds,
    )
    app.state.analysis_rate_limiter = RedisAnalysisRateLimiter(
        redis_client,
        limit=settings.analysis_rate_limit,
        window_seconds=settings.analysis_rate_limit_window_seconds,
    )
    app.state.parse_run_dispatcher = DramatiqParseRunDispatcher()
    app.state.analysis_run_dispatcher = DramatiqAnalysisRunDispatcher()
    app.state.embedding_run_dispatcher = DramatiqEmbeddingRunDispatcher()
    app.add_middleware(RequestIdMiddleware)
    app.include_router(router)
    app.include_router(auth_router)
    app.include_router(experiences_router)
    app.include_router(jobs_router)
    app.include_router(parse_runs_router)
    app.include_router(analysis_runs_router)
    app.include_router(action_items_router)
    app.include_router(dashboard_router)

    @app.exception_handler(ActionItemNotFoundError)
    async def action_item_not_found_handler(
        request: Request,
        exc: ActionItemNotFoundError,
    ) -> JSONResponse:
        return error_response(
            request=request,
            status_code=HTTPStatus.NOT_FOUND,
            code=ErrorCode.ACTION_ITEM_NOT_FOUND,
            message="Action item was not found.",
        )

    @app.exception_handler(ActionItemVersionConflictError)
    async def action_item_version_conflict_handler(
        request: Request,
        exc: ActionItemVersionConflictError,
    ) -> JSONResponse:
        return error_response(
            request=request,
            status_code=HTTPStatus.CONFLICT,
            code=ErrorCode.ACTION_ITEM_VERSION_CONFLICT,
            message="Action item version conflict.",
        )

    @app.exception_handler(ActionItemSourceNotFoundError)
    async def action_item_source_not_found_handler(
        request: Request,
        exc: ActionItemSourceNotFoundError,
    ) -> JSONResponse:
        return error_response(
            request=request,
            status_code=HTTPStatus.NOT_FOUND,
            code=ErrorCode.ACTION_ITEM_SOURCE_NOT_FOUND,
            message="Action item source was not found.",
        )

    @app.exception_handler(ActionItemSourceNotActionableError)
    async def action_item_source_not_actionable_handler(
        request: Request,
        exc: ActionItemSourceNotActionableError,
    ) -> JSONResponse:
        return error_response(
            request=request,
            status_code=HTTPStatus.CONFLICT,
            code=ErrorCode.ACTION_ITEM_SOURCE_NOT_ACTIONABLE,
            message="Only partial, missing, or insufficient-evidence results can become tasks.",
        )

    @app.exception_handler(DuplicateEmailError)
    async def duplicate_email_handler(request: Request, exc: DuplicateEmailError) -> JSONResponse:
        return error_response(
            request=request,
            status_code=HTTPStatus.CONFLICT,
            code=ErrorCode.EMAIL_ALREADY_REGISTERED,
            message="Email is already registered.",
        )

    @app.exception_handler(InvalidCredentialsError)
    async def invalid_credentials_handler(
        request: Request,
        exc: InvalidCredentialsError,
    ) -> JSONResponse:
        return error_response(
            request=request,
            status_code=HTTPStatus.UNAUTHORIZED,
            code=ErrorCode.INVALID_CREDENTIALS,
            message="Invalid email or password.",
        )

    @app.exception_handler(MissingTokenError)
    async def missing_token_handler(request: Request, exc: MissingTokenError) -> JSONResponse:
        return auth_error_response(
            request=request,
            code=ErrorCode.TOKEN_MISSING,
            message="Missing bearer token.",
        )

    @app.exception_handler(InvalidTokenError)
    async def invalid_token_handler(request: Request, exc: InvalidTokenError) -> JSONResponse:
        return auth_error_response(
            request=request,
            code=ErrorCode.TOKEN_INVALID,
            message="Invalid bearer token.",
        )

    @app.exception_handler(ExpiredTokenError)
    async def expired_token_handler(request: Request, exc: ExpiredTokenError) -> JSONResponse:
        return auth_error_response(
            request=request,
            code=ErrorCode.TOKEN_EXPIRED,
            message="Expired bearer token.",
        )

    @app.exception_handler(ExperienceNotFoundError)
    async def experience_not_found_handler(
        request: Request,
        exc: ExperienceNotFoundError,
    ) -> JSONResponse:
        return error_response(
            request=request,
            status_code=HTTPStatus.NOT_FOUND,
            code=ErrorCode.EXPERIENCE_NOT_FOUND,
            message="Experience was not found.",
        )

    @app.exception_handler(ExperienceVersionConflictError)
    async def experience_version_conflict_handler(
        request: Request,
        exc: ExperienceVersionConflictError,
    ) -> JSONResponse:
        return error_response(
            request=request,
            status_code=HTTPStatus.CONFLICT,
            code=ErrorCode.EXPERIENCE_VERSION_CONFLICT,
            message="Experience version conflict.",
        )

    @app.exception_handler(MissingIfMatchHeaderError)
    async def missing_if_match_handler(
        request: Request,
        exc: MissingIfMatchHeaderError,
    ) -> JSONResponse:
        return error_response(
            request=request,
            status_code=HTTPStatus.PRECONDITION_REQUIRED,
            code=ErrorCode.IF_MATCH_REQUIRED,
            message="If-Match header is required.",
        )

    @app.exception_handler(JobNotFoundError)
    async def job_not_found_handler(request: Request, exc: JobNotFoundError) -> JSONResponse:
        return error_response(
            request=request,
            status_code=HTTPStatus.NOT_FOUND,
            code=ErrorCode.JOB_NOT_FOUND,
            message="Job was not found.",
        )

    @app.exception_handler(JobVersionConflictError)
    async def job_version_conflict_handler(
        request: Request,
        exc: JobVersionConflictError,
    ) -> JSONResponse:
        return error_response(
            request=request,
            status_code=HTTPStatus.CONFLICT,
            code=ErrorCode.JOB_VERSION_CONFLICT,
            message="Job version conflict.",
        )

    @app.exception_handler(ParseRunNotFoundError)
    async def parse_run_not_found_handler(
        request: Request,
        exc: ParseRunNotFoundError,
    ) -> JSONResponse:
        return error_response(
            request=request,
            status_code=HTTPStatus.NOT_FOUND,
            code=ErrorCode.PARSE_RUN_NOT_FOUND,
            message="Parse run was not found.",
        )

    @app.exception_handler(AnalysisRunNotFoundError)
    async def analysis_run_not_found_handler(
        request: Request,
        exc: AnalysisRunNotFoundError,
    ) -> JSONResponse:
        return error_response(
            request=request,
            status_code=HTTPStatus.NOT_FOUND,
            code=ErrorCode.ANALYSIS_RUN_NOT_FOUND,
            message="Analysis run was not found.",
        )

    @app.exception_handler(AnalysisRateLimitExceededError)
    async def analysis_rate_limit_exceeded_handler(
        request: Request,
        exc: AnalysisRateLimitExceededError,
    ) -> JSONResponse:
        retry_after = str(exc.retry_after_seconds)
        return error_response(
            request=request,
            status_code=HTTPStatus.TOO_MANY_REQUESTS,
            code=ErrorCode.ANALYSIS_RATE_LIMITED,
            message="Analysis creation rate limit exceeded.",
            details={"retry_after_seconds": exc.retry_after_seconds},
            headers={"Retry-After": retry_after},
        )

    @app.exception_handler(AnalysisRateLimitUnavailableError)
    async def analysis_rate_limit_unavailable_handler(
        request: Request,
        exc: AnalysisRateLimitUnavailableError,
    ) -> JSONResponse:
        return error_response(
            request=request,
            status_code=HTTPStatus.SERVICE_UNAVAILABLE,
            code=ErrorCode.DEPENDENCY_UNAVAILABLE,
            message="Analysis admission control is unavailable; retry later.",
        )

    @app.exception_handler(ParseRunNotReadyError)
    async def parse_run_not_ready_handler(
        request: Request,
        exc: ParseRunNotReadyError,
    ) -> JSONResponse:
        return error_response(
            request=request,
            status_code=HTTPStatus.CONFLICT,
            code=ErrorCode.PARSE_RUN_NOT_READY,
            message="Parse run is not ready for analysis.",
        )

    @app.exception_handler(NoActiveExperiencesError)
    async def no_active_experiences_handler(
        request: Request,
        exc: NoActiveExperiencesError,
    ) -> JSONResponse:
        return error_response(
            request=request,
            status_code=HTTPStatus.CONFLICT,
            code=ErrorCode.NO_ACTIVE_EXPERIENCES,
            message="At least one active experience is required.",
        )

    @app.exception_handler(MissingIdempotencyKeyError)
    async def missing_idempotency_key_handler(
        request: Request,
        exc: MissingIdempotencyKeyError,
    ) -> JSONResponse:
        return error_response(
            request=request,
            status_code=HTTPStatus.PRECONDITION_REQUIRED,
            code=ErrorCode.IDEMPOTENCY_KEY_REQUIRED,
            message="Idempotency-Key header is required.",
        )

    @app.exception_handler(IdempotencyKeyConflictError)
    async def idempotency_key_conflict_handler(
        request: Request,
        exc: IdempotencyKeyConflictError,
    ) -> JSONResponse:
        return error_response(
            request=request,
            status_code=HTTPStatus.CONFLICT,
            code=ErrorCode.IDEMPOTENCY_KEY_CONFLICT,
            message="Idempotency key was already used with different input.",
        )

    @app.exception_handler(ParseRunDispatchError)
    async def parse_run_dispatch_error_handler(
        request: Request,
        exc: ParseRunDispatchError,
    ) -> JSONResponse:
        return error_response(
            request=request,
            status_code=HTTPStatus.SERVICE_UNAVAILABLE,
            code=ErrorCode.DEPENDENCY_UNAVAILABLE,
            message="Parse run queue is unavailable; retry with the same idempotency key.",
        )

    @app.exception_handler(AnalysisRunDispatchError)
    async def analysis_run_dispatch_error_handler(
        request: Request,
        exc: AnalysisRunDispatchError,
    ) -> JSONResponse:
        return error_response(
            request=request,
            status_code=HTTPStatus.SERVICE_UNAVAILABLE,
            code=ErrorCode.DEPENDENCY_UNAVAILABLE,
            message="Analysis run queue is unavailable; retry with the same idempotency key.",
        )

    @app.exception_handler(InvalidCursorError)
    async def invalid_cursor_handler(request: Request, exc: InvalidCursorError) -> JSONResponse:
        return error_response(
            request=request,
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            code=ErrorCode.INVALID_CURSOR,
            message="Invalid pagination cursor.",
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        return error_response(
            request=request,
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            code=ErrorCode.VALIDATION_ERROR,
            message="Request validation failed.",
            details={"errors": validation_error_details(exc)},
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            "Unhandled error request_id=%s path=%s exception_type=%s",
            getattr(request.state, "request_id", "unknown"),
            request.url.path,
            type(exc).__name__,
        )
        return error_response(
            request=request,
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            code=ErrorCode.INTERNAL_ERROR,
            message=HTTPStatus.INTERNAL_SERVER_ERROR.phrase,
        )

    return app


def auth_error_response(request: Request, code: ErrorCode, message: str) -> JSONResponse:
    return error_response(
        request=request,
        status_code=HTTPStatus.UNAUTHORIZED,
        code=code,
        message=message,
    )


def error_response(
    request: Request,
    status_code: int,
    code: ErrorCode,
    message: str,
    details: dict[str, object] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    request_id = cast(str, getattr(request.state, "request_id", "unknown"))
    payload = ErrorResponse(
        error=ErrorDetail(
            code=code,
            message=message,
            details=details or {},
            request_id=request_id,
        )
    )
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(mode="json"),
        headers=headers,
    )


def validation_error_details(exc: RequestValidationError) -> list[dict[str, str]]:
    details: list[dict[str, str]] = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error["loc"])
        details.append(
            {
                "location": location,
                "message": str(error["msg"]),
                "type": str(error["type"]),
            }
        )
    return details
