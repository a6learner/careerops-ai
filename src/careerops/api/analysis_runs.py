from http import HTTPStatus
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from careerops.api.dependencies import get_current_user
from careerops.api.preconditions import MAX_IDEMPOTENCY_KEY_LENGTH, parse_idempotency_key
from careerops.core.config import get_settings
from careerops.db.session import get_session
from careerops.domain.analysis_runs import AnalysisRunRecord, EvidenceMatchRecord
from careerops.domain.embeddings import embedding_space_for_provider
from careerops.domain.users import UserAccount
from careerops.repositories.analysis_runs import AnalysisRunRepository
from careerops.repositories.experiences import ExperienceRepository
from careerops.repositories.jobs import JobRepository
from careerops.repositories.parse_runs import ParseRunRepository
from careerops.schemas.analysis_runs import (
    AnalysisRunResponse,
    AnalysisRunSubmitRequest,
    EvidenceMatchResponse,
)
from careerops.services.analysis_runs import AnalysisRunDispatcher, AnalysisRunService

router = APIRouter(prefix="/api/v1/jobs/{job_id}/analysis-runs", tags=["analysis-runs"])


def get_analysis_run_dispatcher(request: Request) -> AnalysisRunDispatcher:
    return cast(AnalysisRunDispatcher, request.app.state.analysis_run_dispatcher)


@router.post("", response_model=AnalysisRunResponse, status_code=HTTPStatus.ACCEPTED)
async def submit_analysis_run(
    job_id: UUID,
    payload: AnalysisRunSubmitRequest,
    current_user: Annotated[UserAccount, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    dispatcher: Annotated[AnalysisRunDispatcher, Depends(get_analysis_run_dispatcher)],
    idempotency_key: Annotated[
        str | None,
        Header(alias="Idempotency-Key", max_length=MAX_IDEMPOTENCY_KEY_LENGTH),
    ] = None,
) -> AnalysisRunResponse:
    run = await build_analysis_run_service(session, dispatcher).submit_analysis_run(
        user_id=current_user.id,
        job_id=job_id,
        parse_run_id=payload.parse_run_id,
        idempotency_key=parse_idempotency_key(idempotency_key),
    )
    return to_response(run)


@router.get("/{analysis_run_id}", response_model=AnalysisRunResponse)
async def get_analysis_run(
    job_id: UUID,
    analysis_run_id: UUID,
    current_user: Annotated[UserAccount, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    dispatcher: Annotated[AnalysisRunDispatcher, Depends(get_analysis_run_dispatcher)],
) -> AnalysisRunResponse:
    run = await build_analysis_run_service(session, dispatcher).get_analysis_run(
        current_user.id,
        job_id,
        analysis_run_id,
    )
    return to_response(run)


def build_analysis_run_service(
    session: AsyncSession,
    dispatcher: AnalysisRunDispatcher,
) -> AnalysisRunService:
    return AnalysisRunService(
        jobs=JobRepository(session),
        parse_runs=ParseRunRepository(session),
        experiences=ExperienceRepository(session),
        analysis_runs=AnalysisRunRepository(session),
        dispatcher=dispatcher,
        retrieval_space=embedding_space_for_provider(get_settings().embedding_provider),
    )


def to_response(run: AnalysisRunRecord) -> AnalysisRunResponse:
    return AnalysisRunResponse(
        id=run.id,
        job_id=run.job_id,
        parse_run_id=run.parse_run_id,
        status=run.status,
        idempotency_key=run.idempotency_key,
        input_fingerprint=run.input_fingerprint,
        model_name=run.model_name,
        prompt_version=run.prompt_version,
        attempt=run.attempt,
        validation_failure_count=run.validation_failure_count,
        error_code=run.error_code,
        latency_ms=run.latency_ms,
        input_tokens=run.input_tokens,
        output_tokens=run.output_tokens,
        started_at=run.started_at,
        finished_at=run.finished_at,
        created_at=run.created_at,
        matches=[to_match_response(match) for match in run.matches],
    )


def to_match_response(match: EvidenceMatchRecord) -> EvidenceMatchResponse:
    return EvidenceMatchResponse(
        id=match.id,
        requirement_id=match.requirement_id,
        experience_id=match.experience_id,
        experience_version=match.experience_version,
        verdict=match.verdict,
        quote=match.quote,
        quote_valid=match.quote_valid,
        confidence=match.confidence,
    )
