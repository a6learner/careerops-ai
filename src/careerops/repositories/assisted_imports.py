from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from careerops.db.models import (
    CvImport,
    Experience,
    ExperienceDraft,
    ExperienceEmbeddingRun,
    Job,
    JobDiscoveryResult,
    JobDiscoveryRun,
    JobDraft,
)
from careerops.domain.assisted_imports import (
    AssistedRunStatus,
    CvImportRecord,
    CvImportWorkItem,
    DocumentType,
    DraftStatus,
    ExperienceDraftRecord,
    ExtractedExperienceDraft,
    JobDiscoveryResultRecord,
    JobDiscoveryRunRecord,
    JobDiscoveryWorkItem,
    JobDraftRecord,
    JobDraftUpdate,
    JobSearchQuery,
    JobSearchResult,
    SourceReference,
)
from careerops.domain.embeddings import EmbeddingSpace
from careerops.domain.experiences import ExperienceKind, ExperienceRecord
from careerops.domain.jobs import JobRecord, JobStatus


class AssistedImportRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_or_get_cv_import(
        self,
        *,
        user_id: UUID,
        idempotency_key: str,
        filename: str,
        document_type: DocumentType,
        media_type: str,
        content: bytes,
        content_sha256: str,
        extractor_name: str,
    ) -> tuple[CvImportRecord, bool]:
        import_id = uuid4()
        result = await self._session.execute(
            insert(CvImport)
            .values(
                id=import_id,
                user_id=user_id,
                status=AssistedRunStatus.QUEUED.value,
                idempotency_key=idempotency_key,
                filename=filename,
                document_type=document_type.value,
                media_type=media_type,
                size_bytes=len(content),
                content_sha256=content_sha256,
                source_bytes=content,
                extractor_name=extractor_name,
                attempt=1,
            )
            .on_conflict_do_nothing(
                index_elements=[CvImport.user_id, CvImport.idempotency_key]
            )
            .returning(CvImport.id)
        )
        created = result.scalar_one_or_none() is not None
        if created:
            record = await self.get_cv_import(user_id, import_id)
        else:
            record = await self.get_cv_import_by_key(user_id, idempotency_key)
        if record is None:
            raise RuntimeError("CV import idempotency conflict did not resolve.")
        return record, created

    async def get_cv_import_by_key(
        self, user_id: UUID, idempotency_key: str
    ) -> CvImportRecord | None:
        result = await self._session.execute(
            select(CvImport).where(
                CvImport.user_id == user_id, CvImport.idempotency_key == idempotency_key
            )
        )
        row = result.scalar_one_or_none()
        return None if row is None else await self._cv_record(row)

    async def get_cv_import(self, user_id: UUID, import_id: UUID) -> CvImportRecord | None:
        result = await self._session.execute(
            select(CvImport).where(CvImport.id == import_id, CvImport.user_id == user_id)
        )
        row = result.scalar_one_or_none()
        return None if row is None else await self._cv_record(row)

    async def claim_cv_import(self, import_id: UUID) -> CvImportWorkItem | None:
        result = await self._session.execute(
            update(CvImport)
            .where(CvImport.id == import_id, CvImport.status == AssistedRunStatus.QUEUED.value)
            .values(status=AssistedRunStatus.RUNNING.value, started_at=datetime.now(UTC))
            .returning(
                CvImport.id, CvImport.document_type, CvImport.filename, CvImport.source_bytes
            )
        )
        row = result.one_or_none()
        if row is None:
            return None
        return CvImportWorkItem(
            id=row.id,
            document_type=DocumentType(row.document_type),
            filename=row.filename,
            source_bytes=row.source_bytes,
        )

    async def complete_cv_import(
        self,
        import_id: UUID,
        normalized_text: str,
        drafts: tuple[ExtractedExperienceDraft, ...],
    ) -> bool:
        result = await self._session.execute(
            update(CvImport)
            .where(CvImport.id == import_id, CvImport.status == AssistedRunStatus.RUNNING.value)
            .values(
                status=AssistedRunStatus.SUCCEEDED.value,
                normalized_text=normalized_text,
                error_code=None,
                finished_at=datetime.now(UTC),
            )
            .returning(CvImport.user_id)
        )
        user_id = result.scalar_one_or_none()
        if user_id is None:
            return False
        for draft in drafts:
            self._session.add(
                ExperienceDraft(
                    user_id=user_id,
                    cv_import_id=import_id,
                    status=DraftStatus.PENDING.value,
                    title=draft.title,
                    kind=draft.kind.value,
                    description=draft.description,
                    skills=list(draft.skills),
                    outcome=draft.outcome,
                    source_refs=[
                        {
                            "field": ref.field,
                            "start": ref.start,
                            "end": ref.end,
                            "quote": ref.quote,
                        }
                        for ref in draft.source_refs
                    ],
                )
            )
        await self._session.flush()
        return True

    async def fail_cv_import(self, import_id: UUID, error_code: str) -> bool:
        result = await self._session.execute(
            update(CvImport)
            .where(CvImport.id == import_id, CvImport.status == AssistedRunStatus.RUNNING.value)
            .values(
                status=AssistedRunStatus.FAILED.value,
                error_code=error_code,
                finished_at=datetime.now(UTC),
            )
            .returning(CvImport.id)
        )
        return result.scalar_one_or_none() is not None

    async def update_experience_draft(
        self,
        *,
        user_id: UUID,
        draft_id: UUID,
        expected_version: int,
        title: str,
        kind: ExperienceKind,
        description: str,
        skills: tuple[str, ...],
        outcome: str | None,
    ) -> ExperienceDraftRecord | None:
        result = await self._session.execute(
            update(ExperienceDraft)
            .where(
                ExperienceDraft.id == draft_id,
                ExperienceDraft.user_id == user_id,
                ExperienceDraft.status == DraftStatus.PENDING.value,
                ExperienceDraft.version == expected_version,
            )
            .values(
                title=title,
                kind=kind.value,
                description=description,
                skills=list(skills),
                outcome=outcome,
                version=expected_version + 1,
                updated_at=datetime.now(UTC),
            )
            .returning(ExperienceDraft)
        )
        row = result.scalar_one_or_none()
        return None if row is None else _experience_draft_record(row)

    async def get_experience_draft(
        self, user_id: UUID, draft_id: UUID
    ) -> ExperienceDraftRecord | None:
        result = await self._session.execute(
            select(ExperienceDraft).where(
                ExperienceDraft.id == draft_id,
                ExperienceDraft.user_id == user_id,
            )
        )
        row = result.scalar_one_or_none()
        return None if row is None else _experience_draft_record(row)

    async def reject_experience_draft(self, user_id: UUID, draft_id: UUID) -> bool:
        result = await self._session.execute(
            update(ExperienceDraft)
            .where(
                ExperienceDraft.id == draft_id,
                ExperienceDraft.user_id == user_id,
                ExperienceDraft.status == DraftStatus.PENDING.value,
            )
            .values(status=DraftStatus.REJECTED.value, updated_at=datetime.now(UTC))
            .returning(ExperienceDraft.id)
        )
        return result.scalar_one_or_none() is not None

    async def confirm_experience_draft(
        self,
        user_id: UUID,
        draft_id: UUID,
        content_hash: str,
        embedding_space: EmbeddingSpace,
    ) -> tuple[ExperienceRecord, UUID] | None:
        result = await self._session.execute(
            select(ExperienceDraft)
            .where(ExperienceDraft.id == draft_id, ExperienceDraft.user_id == user_id)
            .with_for_update()
        )
        draft = result.scalar_one_or_none()
        if draft is None:
            return None
        if draft.status == DraftStatus.CONFIRMED.value and draft.confirmed_experience_id:
            experience = await self._session.get(Experience, draft.confirmed_experience_id)
            if experience is None:
                raise RuntimeError("Confirmed Experience is missing.")
            run_result = await self._session.execute(
                select(ExperienceEmbeddingRun.id).where(
                    ExperienceEmbeddingRun.experience_id == experience.id
                )
            )
            run_id = run_result.scalar_one()
            return _experience_record(experience), run_id
        if draft.status != DraftStatus.PENDING.value:
            return None

        experience = Experience(
            user_id=user_id,
            title=draft.title,
            kind=draft.kind,
            description=draft.description,
            skills=list(draft.skills),
            outcome=draft.outcome,
            content_hash=content_hash,
        )
        self._session.add(experience)
        await self._session.flush()
        run = ExperienceEmbeddingRun(
            user_id=user_id,
            experience_id=experience.id,
            experience_version=1,
            content_hash=experience.content_hash,
            status=AssistedRunStatus.QUEUED.value,
            model_name=embedding_space.model_name,
            input_version=embedding_space.document_input_version,
            attempt=1,
        )
        self._session.add(run)
        draft.status = DraftStatus.CONFIRMED.value
        draft.confirmed_experience_id = experience.id
        draft.updated_at = datetime.now(UTC)
        await self._session.flush()
        await self._session.refresh(experience)
        return _experience_record(experience), run.id

    async def create_or_get_discovery_run(
        self,
        *,
        user_id: UUID,
        idempotency_key: str,
        query: JobSearchQuery,
        query_fingerprint: str,
        provider_name: str,
    ) -> tuple[JobDiscoveryRunRecord, bool]:
        run_id = uuid4()
        result = await self._session.execute(
            insert(JobDiscoveryRun)
            .values(
                id=run_id,
                user_id=user_id,
                status=AssistedRunStatus.QUEUED.value,
                idempotency_key=idempotency_key,
                query=query.query,
                location=query.location,
                remote=query.remote,
                published_within_days=query.published_within_days,
                query_fingerprint=query_fingerprint,
                provider_name=provider_name,
                attempt=1,
            )
            .on_conflict_do_nothing(
                index_elements=[JobDiscoveryRun.user_id, JobDiscoveryRun.idempotency_key]
            )
            .returning(JobDiscoveryRun.id)
        )
        created = result.scalar_one_or_none() is not None
        if created:
            record = await self.get_discovery_run(user_id, run_id)
        else:
            record = await self.get_discovery_run_by_key(user_id, idempotency_key)
        if record is None:
            raise RuntimeError("Discovery idempotency conflict did not resolve.")
        return record, created

    async def get_discovery_run_by_key(
        self, user_id: UUID, idempotency_key: str
    ) -> JobDiscoveryRunRecord | None:
        result = await self._session.execute(
            select(JobDiscoveryRun).where(
                JobDiscoveryRun.user_id == user_id,
                JobDiscoveryRun.idempotency_key == idempotency_key,
            )
        )
        row = result.scalar_one_or_none()
        return None if row is None else await self._discovery_record(row)

    async def get_discovery_run(
        self, user_id: UUID, run_id: UUID
    ) -> JobDiscoveryRunRecord | None:
        result = await self._session.execute(
            select(JobDiscoveryRun).where(
                JobDiscoveryRun.id == run_id, JobDiscoveryRun.user_id == user_id
            )
        )
        row = result.scalar_one_or_none()
        return None if row is None else await self._discovery_record(row)

    async def claim_discovery_run(self, run_id: UUID) -> JobDiscoveryWorkItem | None:
        result = await self._session.execute(
            update(JobDiscoveryRun)
            .where(
                JobDiscoveryRun.id == run_id,
                JobDiscoveryRun.status == AssistedRunStatus.QUEUED.value,
            )
            .values(status=AssistedRunStatus.RUNNING.value, started_at=datetime.now(UTC))
            .returning(
                JobDiscoveryRun.id,
                JobDiscoveryRun.query,
                JobDiscoveryRun.location,
                JobDiscoveryRun.remote,
                JobDiscoveryRun.published_within_days,
            )
        )
        row = result.one_or_none()
        if row is None:
            return None
        return JobDiscoveryWorkItem(
            id=row.id,
            query=JobSearchQuery(
                query=row.query,
                location=row.location,
                remote=row.remote,
                published_within_days=row.published_within_days,
            ),
        )

    async def complete_discovery_run(
        self, run_id: UUID, results: tuple[JobSearchResult, ...]
    ) -> bool:
        changed = await self._session.execute(
            update(JobDiscoveryRun)
            .where(
                JobDiscoveryRun.id == run_id,
                JobDiscoveryRun.status == AssistedRunStatus.RUNNING.value,
            )
            .values(
                status=AssistedRunStatus.SUCCEEDED.value,
                finished_at=datetime.now(UTC),
                error_code=None,
            )
            .returning(JobDiscoveryRun.user_id)
        )
        user_id = changed.scalar_one_or_none()
        if user_id is None:
            return False
        observed_at = datetime.now(UTC)
        for item in results:
            self._session.add(
                JobDiscoveryResult(
                    user_id=user_id,
                    run_id=run_id,
                    provider_result_id=item.provider_result_id,
                    company=item.company,
                    title=item.title,
                    source_url=item.source_url,
                    summary=item.summary,
                    raw_description=item.raw_description,
                    location=item.location,
                    published_at=item.published_at,
                    observed_at=observed_at,
                )
            )
        await self._session.flush()
        return True

    async def fail_discovery_run(self, run_id: UUID, error_code: str) -> bool:
        result = await self._session.execute(
            update(JobDiscoveryRun)
            .where(
                JobDiscoveryRun.id == run_id,
                JobDiscoveryRun.status == AssistedRunStatus.RUNNING.value,
            )
            .values(
                status=AssistedRunStatus.FAILED.value,
                error_code=error_code,
                finished_at=datetime.now(UTC),
            )
            .returning(JobDiscoveryRun.id)
        )
        return result.scalar_one_or_none() is not None

    async def create_or_get_job_draft(
        self, user_id: UUID, result_id: UUID
    ) -> JobDraftRecord | None:
        source_result = await self._session.execute(
            select(JobDiscoveryResult).where(
                JobDiscoveryResult.id == result_id, JobDiscoveryResult.user_id == user_id
            )
        )
        source = source_result.scalar_one_or_none()
        if source is None:
            return None
        draft_id = uuid4()
        await self._session.execute(
            insert(JobDraft)
            .values(
                id=draft_id,
                user_id=user_id,
                result_id=result_id,
                status=DraftStatus.PENDING.value,
                company=source.company,
                title=source.title,
                raw_description=source.raw_description,
                source_url=source.source_url,
                location=source.location,
                version=1,
            )
            .on_conflict_do_nothing(index_elements=[JobDraft.result_id])
        )
        result = await self._session.execute(
            select(JobDraft).where(JobDraft.result_id == result_id, JobDraft.user_id == user_id)
        )
        row = result.scalar_one_or_none()
        return None if row is None else _job_draft_record(row)

    async def get_job_draft(self, user_id: UUID, draft_id: UUID) -> JobDraftRecord | None:
        result = await self._session.execute(
            select(JobDraft).where(JobDraft.id == draft_id, JobDraft.user_id == user_id)
        )
        row = result.scalar_one_or_none()
        return None if row is None else _job_draft_record(row)

    async def update_job_draft(
        self,
        user_id: UUID,
        draft_id: UUID,
        expected_version: int,
        payload: JobDraftUpdate,
    ) -> JobDraftRecord | None:
        values: dict[str, object] = {
            "version": expected_version + 1,
            "updated_at": datetime.now(UTC),
        }
        if payload.company is not None:
            values["company"] = payload.company
        if payload.title is not None:
            values["title"] = payload.title
        if payload.raw_description is not None:
            values["raw_description"] = payload.raw_description
        if payload.clear_location:
            values["location"] = None
        elif payload.location is not None:
            values["location"] = payload.location
        result = await self._session.execute(
            update(JobDraft)
            .where(
                JobDraft.id == draft_id,
                JobDraft.user_id == user_id,
                JobDraft.status == DraftStatus.PENDING.value,
                JobDraft.version == expected_version,
            )
            .values(**values)
            .returning(JobDraft)
        )
        row = result.scalar_one_or_none()
        return None if row is None else _job_draft_record(row)

    async def confirm_job_draft(
        self, user_id: UUID, draft_id: UUID, description_hash: str
    ) -> JobRecord | None:
        result = await self._session.execute(
            select(JobDraft)
            .where(JobDraft.id == draft_id, JobDraft.user_id == user_id)
            .with_for_update()
        )
        draft = result.scalar_one_or_none()
        if draft is None:
            return None
        if draft.status == DraftStatus.CONFIRMED.value and draft.confirmed_job_id:
            job = await self._session.get(Job, draft.confirmed_job_id)
            return None if job is None else _job_record(job)
        if draft.status != DraftStatus.PENDING.value or not draft.raw_description:
            return None
        job = Job(
            user_id=user_id,
            company=draft.company,
            title=draft.title,
            raw_description=draft.raw_description,
            description_hash=description_hash,
            source_url=draft.source_url,
            location=draft.location,
            deadline=None,
            status=JobStatus.SAVED.value,
        )
        self._session.add(job)
        await self._session.flush()
        draft.status = DraftStatus.CONFIRMED.value
        draft.confirmed_job_id = job.id
        draft.updated_at = datetime.now(UTC)
        await self._session.flush()
        await self._session.refresh(job)
        return _job_record(job)

    async def commit(self) -> None:
        await self._session.commit()

    async def _cv_record(self, row: CvImport) -> CvImportRecord:
        result = await self._session.execute(
            select(ExperienceDraft)
            .where(ExperienceDraft.cv_import_id == row.id)
            .order_by(ExperienceDraft.created_at.asc(), ExperienceDraft.id.asc())
        )
        return CvImportRecord(
            id=row.id,
            user_id=row.user_id,
            status=AssistedRunStatus(row.status),
            filename=row.filename,
            document_type=DocumentType(row.document_type),
            media_type=row.media_type,
            size_bytes=row.size_bytes,
            content_sha256=row.content_sha256,
            extractor_name=row.extractor_name,
            attempt=row.attempt,
            error_code=row.error_code,
            started_at=row.started_at,
            finished_at=row.finished_at,
            created_at=row.created_at,
            drafts=tuple(_experience_draft_record(item) for item in result.scalars().all()),
        )

    async def _discovery_record(self, row: JobDiscoveryRun) -> JobDiscoveryRunRecord:
        result = await self._session.execute(
            select(JobDiscoveryResult)
            .where(JobDiscoveryResult.run_id == row.id)
            .order_by(JobDiscoveryResult.observed_at.asc(), JobDiscoveryResult.id.asc())
        )
        return JobDiscoveryRunRecord(
            id=row.id,
            user_id=row.user_id,
            status=AssistedRunStatus(row.status),
            query=JobSearchQuery(
                query=row.query,
                location=row.location,
                remote=row.remote,
                published_within_days=row.published_within_days,
            ),
            query_fingerprint=row.query_fingerprint,
            provider_name=row.provider_name,
            attempt=row.attempt,
            error_code=row.error_code,
            started_at=row.started_at,
            finished_at=row.finished_at,
            created_at=row.created_at,
            results=tuple(_discovery_result_record(item) for item in result.scalars().all()),
        )


def _source_reference(value: object) -> SourceReference:
    if not isinstance(value, dict):
        raise RuntimeError("Invalid stored source reference.")
    field = value.get("field")
    start = value.get("start")
    end = value.get("end")
    quote = value.get("quote")
    if not (
        isinstance(field, str)
        and isinstance(start, int)
        and isinstance(end, int)
        and isinstance(quote, str)
    ):
        raise RuntimeError("Invalid stored source reference.")
    return SourceReference(field=field, start=start, end=end, quote=quote)


def _experience_draft_record(row: ExperienceDraft) -> ExperienceDraftRecord:
    return ExperienceDraftRecord(
        id=row.id,
        cv_import_id=row.cv_import_id,
        status=DraftStatus(row.status),
        title=row.title,
        kind=ExperienceKind(row.kind),
        description=row.description,
        skills=tuple(row.skills),
        outcome=row.outcome,
        source_refs=tuple(_source_reference(ref) for ref in row.source_refs),
        version=row.version,
        confirmed_experience_id=row.confirmed_experience_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _discovery_result_record(row: JobDiscoveryResult) -> JobDiscoveryResultRecord:
    return JobDiscoveryResultRecord(
        id=row.id,
        provider_result_id=row.provider_result_id,
        company=row.company,
        title=row.title,
        source_url=row.source_url,
        summary=row.summary,
        raw_description=row.raw_description,
        location=row.location,
        published_at=row.published_at,
        observed_at=row.observed_at,
    )


def _job_draft_record(row: JobDraft) -> JobDraftRecord:
    return JobDraftRecord(
        id=row.id,
        result_id=row.result_id,
        status=DraftStatus(row.status),
        company=row.company,
        title=row.title,
        raw_description=row.raw_description,
        source_url=row.source_url,
        location=row.location,
        version=row.version,
        confirmed_job_id=row.confirmed_job_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _experience_record(row: Experience) -> ExperienceRecord:
    return ExperienceRecord(
        id=row.id,
        user_id=row.user_id,
        title=row.title,
        kind=ExperienceKind(row.kind),
        description=row.description,
        skills=tuple(row.skills),
        outcome=row.outcome,
        version=row.version,
        content_hash=row.content_hash,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _job_record(row: Job) -> JobRecord:
    return JobRecord(
        id=row.id,
        user_id=row.user_id,
        company=row.company,
        title=row.title,
        raw_description=row.raw_description,
        description_hash=row.description_hash,
        source_url=row.source_url,
        location=row.location,
        deadline=row.deadline,
        status=JobStatus(row.status),
        version=row.version,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
