from http import HTTPStatus
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, File, Header, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from careerops.api.dependencies import get_current_user, get_dashboard_cache
from careerops.api.experiences import to_response as experience_response
from careerops.api.jobs import to_response as job_response
from careerops.api.preconditions import (
    MAX_IDEMPOTENCY_KEY_LENGTH,
    parse_idempotency_key,
    parse_if_match,
)
from careerops.core.config import get_settings
from careerops.db.session import get_session
from careerops.domain.assisted_imports import (
    CvImportRecord,
    ExperienceDraftRecord,
    JobDiscoveryResultRecord,
    JobDiscoveryRunRecord,
    JobDraftRecord,
    JobDraftUpdate,
    JobSearchQuery,
)
from careerops.domain.embeddings import embedding_space_for_provider
from careerops.domain.errors import InvalidDocumentError
from careerops.domain.users import UserAccount
from careerops.repositories.assisted_imports import AssistedImportRepository
from careerops.schemas.assisted_imports import (
    CvImportResponse,
    ExperienceDraftResponse,
    ExperienceDraftUpdateRequest,
    JobDiscoveryRequest,
    JobDiscoveryResultResponse,
    JobDiscoveryRunResponse,
    JobDraftResponse,
    JobDraftUpdateRequest,
    SourceReferenceResponse,
)
from careerops.schemas.experiences import ExperienceResponse
from careerops.schemas.jobs import JobResponse
from careerops.services.assisted_imports import AssistedImportService, RunDispatcher
from careerops.services.dashboard import DashboardCache
from careerops.services.embedding_recovery import EmbeddingRunDispatcher

router = APIRouter(tags=["assisted-imports"])


def get_cv_dispatcher(request: Request) -> RunDispatcher:
    return cast(RunDispatcher, request.app.state.cv_import_dispatcher)


def get_discovery_dispatcher(request: Request) -> RunDispatcher:
    return cast(RunDispatcher, request.app.state.job_discovery_dispatcher)


def get_embedding_dispatcher(request: Request) -> EmbeddingRunDispatcher:
    return cast(EmbeddingRunDispatcher, request.app.state.embedding_run_dispatcher)


@router.post(
    "/api/v1/cv-imports", response_model=CvImportResponse, status_code=HTTPStatus.ACCEPTED
)
async def submit_cv_import(
    current_user: Annotated[UserAccount, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    cv_dispatcher: Annotated[RunDispatcher, Depends(get_cv_dispatcher)],
    discovery_dispatcher: Annotated[RunDispatcher, Depends(get_discovery_dispatcher)],
    embedding_dispatcher: Annotated[EmbeddingRunDispatcher, Depends(get_embedding_dispatcher)],
    cache: Annotated[DashboardCache, Depends(get_dashboard_cache)],
    file: Annotated[UploadFile, File()],
    idempotency_key: Annotated[
        str | None,
        Header(alias="Idempotency-Key", max_length=MAX_IDEMPOTENCY_KEY_LENGTH),
    ] = None,
) -> CvImportResponse:
    content = await file.read(5 * 1024 * 1024 + 1)
    if file.filename is None:
        raise InvalidDocumentError("CV filename is required.")
    service = build_service(
        session, cv_dispatcher, discovery_dispatcher, embedding_dispatcher, cache
    )
    record = await service.submit_cv_import(
        user_id=current_user.id,
        idempotency_key=parse_idempotency_key(idempotency_key),
        filename=file.filename,
        media_type=file.content_type or "application/octet-stream",
        content=content,
    )
    return to_cv_response(record)


@router.get("/api/v1/cv-imports/{import_id}", response_model=CvImportResponse)
async def get_cv_import(
    import_id: UUID,
    current_user: Annotated[UserAccount, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    cv_dispatcher: Annotated[RunDispatcher, Depends(get_cv_dispatcher)],
    discovery_dispatcher: Annotated[RunDispatcher, Depends(get_discovery_dispatcher)],
    embedding_dispatcher: Annotated[EmbeddingRunDispatcher, Depends(get_embedding_dispatcher)],
    cache: Annotated[DashboardCache, Depends(get_dashboard_cache)],
) -> CvImportResponse:
    service = build_service(
        session, cv_dispatcher, discovery_dispatcher, embedding_dispatcher, cache
    )
    return to_cv_response(await service.get_cv_import(current_user.id, import_id))


@router.patch(
    "/api/v1/experience-drafts/{draft_id}", response_model=ExperienceDraftResponse
)
async def update_experience_draft(
    draft_id: UUID,
    payload: ExperienceDraftUpdateRequest,
    current_user: Annotated[UserAccount, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    cv_dispatcher: Annotated[RunDispatcher, Depends(get_cv_dispatcher)],
    discovery_dispatcher: Annotated[RunDispatcher, Depends(get_discovery_dispatcher)],
    embedding_dispatcher: Annotated[EmbeddingRunDispatcher, Depends(get_embedding_dispatcher)],
    cache: Annotated[DashboardCache, Depends(get_dashboard_cache)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> ExperienceDraftResponse:
    service = build_service(
        session, cv_dispatcher, discovery_dispatcher, embedding_dispatcher, cache
    )
    draft = await service.update_experience_draft(
        user_id=current_user.id,
        draft_id=draft_id,
        expected_version=parse_if_match(if_match),
        title=payload.title,
        kind=payload.kind,
        description=payload.description,
        skills=tuple(payload.skills),
        outcome=payload.outcome,
    )
    return to_experience_draft_response(draft)


@router.post(
    "/api/v1/experience-drafts/{draft_id}/confirm",
    response_model=ExperienceResponse,
    status_code=HTTPStatus.CREATED,
)
async def confirm_experience_draft(
    draft_id: UUID,
    current_user: Annotated[UserAccount, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    cv_dispatcher: Annotated[RunDispatcher, Depends(get_cv_dispatcher)],
    discovery_dispatcher: Annotated[RunDispatcher, Depends(get_discovery_dispatcher)],
    embedding_dispatcher: Annotated[EmbeddingRunDispatcher, Depends(get_embedding_dispatcher)],
    cache: Annotated[DashboardCache, Depends(get_dashboard_cache)],
) -> ExperienceResponse:
    service = build_service(
        session, cv_dispatcher, discovery_dispatcher, embedding_dispatcher, cache
    )
    return experience_response(await service.confirm_experience_draft(current_user.id, draft_id))


@router.post(
    "/api/v1/experience-drafts/{draft_id}/reject", status_code=HTTPStatus.NO_CONTENT
)
async def reject_experience_draft(
    draft_id: UUID,
    current_user: Annotated[UserAccount, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    cv_dispatcher: Annotated[RunDispatcher, Depends(get_cv_dispatcher)],
    discovery_dispatcher: Annotated[RunDispatcher, Depends(get_discovery_dispatcher)],
    embedding_dispatcher: Annotated[EmbeddingRunDispatcher, Depends(get_embedding_dispatcher)],
    cache: Annotated[DashboardCache, Depends(get_dashboard_cache)],
) -> None:
    service = build_service(
        session, cv_dispatcher, discovery_dispatcher, embedding_dispatcher, cache
    )
    await service.reject_experience_draft(current_user.id, draft_id)


@router.post(
    "/api/v1/job-discovery-runs",
    response_model=JobDiscoveryRunResponse,
    status_code=HTTPStatus.ACCEPTED,
)
async def submit_job_discovery(
    payload: JobDiscoveryRequest,
    current_user: Annotated[UserAccount, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    cv_dispatcher: Annotated[RunDispatcher, Depends(get_cv_dispatcher)],
    discovery_dispatcher: Annotated[RunDispatcher, Depends(get_discovery_dispatcher)],
    embedding_dispatcher: Annotated[EmbeddingRunDispatcher, Depends(get_embedding_dispatcher)],
    cache: Annotated[DashboardCache, Depends(get_dashboard_cache)],
    idempotency_key: Annotated[
        str | None,
        Header(alias="Idempotency-Key", max_length=MAX_IDEMPOTENCY_KEY_LENGTH),
    ] = None,
) -> JobDiscoveryRunResponse:
    service = build_service(
        session, cv_dispatcher, discovery_dispatcher, embedding_dispatcher, cache
    )
    record = await service.submit_discovery_run(
        current_user.id,
        parse_idempotency_key(idempotency_key),
        JobSearchQuery(
            query=payload.query,
            location=payload.location,
            remote=payload.remote,
            published_within_days=payload.published_within_days,
        ),
    )
    return to_discovery_response(record)


@router.get(
    "/api/v1/job-discovery-runs/{run_id}", response_model=JobDiscoveryRunResponse
)
async def get_job_discovery(
    run_id: UUID,
    current_user: Annotated[UserAccount, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    cv_dispatcher: Annotated[RunDispatcher, Depends(get_cv_dispatcher)],
    discovery_dispatcher: Annotated[RunDispatcher, Depends(get_discovery_dispatcher)],
    embedding_dispatcher: Annotated[EmbeddingRunDispatcher, Depends(get_embedding_dispatcher)],
    cache: Annotated[DashboardCache, Depends(get_dashboard_cache)],
) -> JobDiscoveryRunResponse:
    service = build_service(
        session, cv_dispatcher, discovery_dispatcher, embedding_dispatcher, cache
    )
    return to_discovery_response(await service.get_discovery_run(current_user.id, run_id))


@router.post(
    "/api/v1/job-discovery-results/{result_id}/draft",
    response_model=JobDraftResponse,
    status_code=HTTPStatus.CREATED,
)
async def create_job_draft(
    result_id: UUID,
    current_user: Annotated[UserAccount, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    cv_dispatcher: Annotated[RunDispatcher, Depends(get_cv_dispatcher)],
    discovery_dispatcher: Annotated[RunDispatcher, Depends(get_discovery_dispatcher)],
    embedding_dispatcher: Annotated[EmbeddingRunDispatcher, Depends(get_embedding_dispatcher)],
    cache: Annotated[DashboardCache, Depends(get_dashboard_cache)],
) -> JobDraftResponse:
    service = build_service(
        session, cv_dispatcher, discovery_dispatcher, embedding_dispatcher, cache
    )
    return to_job_draft_response(await service.create_job_draft(current_user.id, result_id))


@router.get("/api/v1/job-drafts/{draft_id}", response_model=JobDraftResponse)
async def get_job_draft(
    draft_id: UUID,
    current_user: Annotated[UserAccount, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    cv_dispatcher: Annotated[RunDispatcher, Depends(get_cv_dispatcher)],
    discovery_dispatcher: Annotated[RunDispatcher, Depends(get_discovery_dispatcher)],
    embedding_dispatcher: Annotated[EmbeddingRunDispatcher, Depends(get_embedding_dispatcher)],
    cache: Annotated[DashboardCache, Depends(get_dashboard_cache)],
) -> JobDraftResponse:
    service = build_service(
        session, cv_dispatcher, discovery_dispatcher, embedding_dispatcher, cache
    )
    return to_job_draft_response(await service.get_job_draft(current_user.id, draft_id))


@router.patch("/api/v1/job-drafts/{draft_id}", response_model=JobDraftResponse)
async def update_job_draft(
    draft_id: UUID,
    payload: JobDraftUpdateRequest,
    current_user: Annotated[UserAccount, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    cv_dispatcher: Annotated[RunDispatcher, Depends(get_cv_dispatcher)],
    discovery_dispatcher: Annotated[RunDispatcher, Depends(get_discovery_dispatcher)],
    embedding_dispatcher: Annotated[EmbeddingRunDispatcher, Depends(get_embedding_dispatcher)],
    cache: Annotated[DashboardCache, Depends(get_dashboard_cache)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> JobDraftResponse:
    service = build_service(
        session, cv_dispatcher, discovery_dispatcher, embedding_dispatcher, cache
    )
    draft = await service.update_job_draft(
        current_user.id,
        draft_id,
        parse_if_match(if_match),
        JobDraftUpdate(
            company=payload.company,
            title=payload.title,
            raw_description=payload.raw_description,
            location=payload.location,
            clear_location=payload.location is None and "location" in payload.model_fields_set,
        ),
    )
    return to_job_draft_response(draft)


@router.post(
    "/api/v1/job-drafts/{draft_id}/confirm",
    response_model=JobResponse,
    status_code=HTTPStatus.CREATED,
)
async def confirm_job_draft(
    draft_id: UUID,
    current_user: Annotated[UserAccount, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    cv_dispatcher: Annotated[RunDispatcher, Depends(get_cv_dispatcher)],
    discovery_dispatcher: Annotated[RunDispatcher, Depends(get_discovery_dispatcher)],
    embedding_dispatcher: Annotated[EmbeddingRunDispatcher, Depends(get_embedding_dispatcher)],
    cache: Annotated[DashboardCache, Depends(get_dashboard_cache)],
) -> JobResponse:
    service = build_service(
        session, cv_dispatcher, discovery_dispatcher, embedding_dispatcher, cache
    )
    return job_response(await service.confirm_job_draft(current_user.id, draft_id))


def build_service(
    session: AsyncSession,
    cv_dispatcher: RunDispatcher,
    discovery_dispatcher: RunDispatcher,
    embedding_dispatcher: EmbeddingRunDispatcher,
    cache: DashboardCache,
) -> AssistedImportService:
    return AssistedImportService(
        store=AssistedImportRepository(session),
        cv_dispatcher=cv_dispatcher,
        discovery_dispatcher=discovery_dispatcher,
        embedding_dispatcher=embedding_dispatcher,
        embedding_space=embedding_space_for_provider(get_settings().embedding_provider),
        dashboard_cache=cache,
    )


def to_cv_response(record: CvImportRecord) -> CvImportResponse:
    return CvImportResponse(
        id=record.id,
        status=record.status,
        filename=record.filename,
        document_type=record.document_type,
        media_type=record.media_type,
        size_bytes=record.size_bytes,
        content_sha256=record.content_sha256,
        extractor_name=record.extractor_name,
        attempt=record.attempt,
        error_code=record.error_code,
        started_at=record.started_at,
        finished_at=record.finished_at,
        created_at=record.created_at,
        drafts=[to_experience_draft_response(draft) for draft in record.drafts],
    )


def to_experience_draft_response(record: ExperienceDraftRecord) -> ExperienceDraftResponse:
    return ExperienceDraftResponse(
        id=record.id,
        cv_import_id=record.cv_import_id,
        status=record.status,
        title=record.title,
        kind=record.kind,
        description=record.description,
        skills=list(record.skills),
        outcome=record.outcome,
        source_refs=[
            SourceReferenceResponse(
                field=ref.field, start=ref.start, end=ref.end, quote=ref.quote
            )
            for ref in record.source_refs
        ],
        version=record.version,
        confirmed_experience_id=record.confirmed_experience_id,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def to_discovery_response(record: JobDiscoveryRunRecord) -> JobDiscoveryRunResponse:
    return JobDiscoveryRunResponse(
        id=record.id,
        status=record.status,
        query=record.query.query,
        location=record.query.location,
        remote=record.query.remote,
        published_within_days=record.query.published_within_days,
        query_fingerprint=record.query_fingerprint,
        provider_name=record.provider_name,
        attempt=record.attempt,
        error_code=record.error_code,
        started_at=record.started_at,
        finished_at=record.finished_at,
        created_at=record.created_at,
        results=[to_discovery_result_response(result) for result in record.results],
    )


def to_discovery_result_response(
    record: JobDiscoveryResultRecord,
) -> JobDiscoveryResultResponse:
    return JobDiscoveryResultResponse(
        id=record.id,
        provider_result_id=record.provider_result_id,
        company=record.company,
        title=record.title,
        source_url=record.source_url,
        summary=record.summary,
        raw_description=record.raw_description,
        location=record.location,
        published_at=record.published_at,
        observed_at=record.observed_at,
    )


def to_job_draft_response(record: JobDraftRecord) -> JobDraftResponse:
    return JobDraftResponse(
        id=record.id,
        result_id=record.result_id,
        status=record.status,
        company=record.company,
        title=record.title,
        raw_description=record.raw_description,
        source_url=record.source_url,
        location=record.location,
        version=record.version,
        confirmed_job_id=record.confirmed_job_id,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )
