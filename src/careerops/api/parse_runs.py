from http import HTTPStatus
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from careerops.api.dependencies import get_current_user
from careerops.api.preconditions import MAX_IDEMPOTENCY_KEY_LENGTH, parse_idempotency_key
from careerops.db.session import get_session
from careerops.domain.parse_runs import JobRequirementRecord, ParseRunRecord
from careerops.domain.users import UserAccount
from careerops.repositories.jobs import JobRepository
from careerops.repositories.parse_runs import ParseRunRepository
from careerops.schemas.parse_runs import JobRequirementResponse, ParseRunResponse
from careerops.services.parse_runs import ParseRunDispatcher, ParseRunService

router = APIRouter(prefix="/api/v1/jobs/{job_id}/parse-runs", tags=["parse-runs"])


def get_parse_run_dispatcher(request: Request) -> ParseRunDispatcher:
    return cast(ParseRunDispatcher, request.app.state.parse_run_dispatcher)


@router.post("", response_model=ParseRunResponse, status_code=HTTPStatus.ACCEPTED)
async def submit_parse_run(
    job_id: UUID,
    current_user: Annotated[UserAccount, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    dispatcher: Annotated[ParseRunDispatcher, Depends(get_parse_run_dispatcher)],
    idempotency_key: Annotated[
        str | None,
        Header(alias="Idempotency-Key", max_length=MAX_IDEMPOTENCY_KEY_LENGTH),
    ] = None,
) -> ParseRunResponse:
    service = build_parse_run_service(session, dispatcher)
    run = await service.submit_parse_run(
        user_id=current_user.id,
        job_id=job_id,
        idempotency_key=parse_idempotency_key(idempotency_key),
    )
    return to_response(run)


@router.get("/{parse_run_id}", response_model=ParseRunResponse)
async def get_parse_run(
    job_id: UUID,
    parse_run_id: UUID,
    current_user: Annotated[UserAccount, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    dispatcher: Annotated[ParseRunDispatcher, Depends(get_parse_run_dispatcher)],
) -> ParseRunResponse:
    service = build_parse_run_service(session, dispatcher)
    run = await service.get_parse_run(
        user_id=current_user.id,
        job_id=job_id,
        parse_run_id=parse_run_id,
    )
    return to_response(run)


def build_parse_run_service(
    session: AsyncSession,
    dispatcher: ParseRunDispatcher,
) -> ParseRunService:
    return ParseRunService(
        jobs=JobRepository(session),
        parse_runs=ParseRunRepository(session),
        dispatcher=dispatcher,
    )


def to_response(run: ParseRunRecord) -> ParseRunResponse:
    return ParseRunResponse(
        id=run.id,
        job_id=run.job_id,
        status=run.status,
        idempotency_key=run.idempotency_key,
        input_fingerprint=run.input_fingerprint,
        model_name=run.model_name,
        prompt_version=run.prompt_version,
        attempt=run.attempt,
        error_code=run.error_code,
        latency_ms=run.latency_ms,
        input_tokens=run.input_tokens,
        output_tokens=run.output_tokens,
        started_at=run.started_at,
        finished_at=run.finished_at,
        created_at=run.created_at,
        requirements=[to_requirement_response(requirement) for requirement in run.requirements],
    )


def to_requirement_response(requirement: JobRequirementRecord) -> JobRequirementResponse:
    return JobRequirementResponse(
        id=requirement.id,
        category=requirement.category,
        text=requirement.text,
        skill_normalized=requirement.skill_normalized,
        source_span_start=requirement.source_span_start,
        source_span_end=requirement.source_span_end,
    )
