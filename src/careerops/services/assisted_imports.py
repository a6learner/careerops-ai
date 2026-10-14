import hashlib
import json
from pathlib import Path
from typing import Protocol
from urllib.parse import urlparse
from uuid import UUID

from careerops.adapters.document_text_extractor import (
    DocumentExtractionError,
    extract_document_text,
)
from careerops.domain.assisted_imports import (
    CV_EXTRACTOR_NAME,
    FAKE_JOB_SEARCH_PROVIDER,
    MAX_CV_BYTES,
    AssistedRunStatus,
    CvImportErrorCode,
    CvImportRecord,
    CvImportWorkItem,
    DocumentType,
    ExperienceDraftRecord,
    ExtractedExperienceDraft,
    JobDiscoveryErrorCode,
    JobDiscoveryRunRecord,
    JobDiscoveryWorkItem,
    JobDraftRecord,
    JobDraftUpdate,
    JobSearchQuery,
    JobSearchResult,
    SourceReference,
)
from careerops.domain.embeddings import EmbeddingSpace
from careerops.domain.errors import (
    AssistedResourceConflictError,
    AssistedResourceNotFoundError,
    IdempotencyKeyConflictError,
    InvalidDocumentError,
)
from careerops.domain.experiences import ExperienceCreate, ExperienceKind, ExperienceRecord
from careerops.domain.jobs import JobRecord
from careerops.services.dashboard import DashboardCacheInvalidator
from careerops.services.embedding_recovery import EmbeddingRunDispatcher
from careerops.services.experiences import compute_experience_content_hash
from careerops.services.jobs import compute_description_hash


class AssistedImportStore(Protocol):
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
    ) -> tuple[CvImportRecord, bool]: ...
    async def get_cv_import(self, user_id: UUID, import_id: UUID) -> CvImportRecord | None: ...
    async def claim_cv_import(self, import_id: UUID) -> CvImportWorkItem | None: ...
    async def complete_cv_import(
        self,
        import_id: UUID,
        normalized_text: str,
        drafts: tuple[ExtractedExperienceDraft, ...],
    ) -> bool: ...
    async def fail_cv_import(self, import_id: UUID, error_code: str) -> bool: ...
    async def get_experience_draft(
        self, user_id: UUID, draft_id: UUID
    ) -> ExperienceDraftRecord | None: ...
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
    ) -> ExperienceDraftRecord | None: ...
    async def reject_experience_draft(self, user_id: UUID, draft_id: UUID) -> bool: ...
    async def confirm_experience_draft(
        self,
        user_id: UUID,
        draft_id: UUID,
        content_hash: str,
        embedding_space: EmbeddingSpace,
    ) -> tuple[ExperienceRecord, UUID] | None: ...
    async def create_or_get_discovery_run(
        self,
        *,
        user_id: UUID,
        idempotency_key: str,
        query: JobSearchQuery,
        query_fingerprint: str,
        provider_name: str,
    ) -> tuple[JobDiscoveryRunRecord, bool]: ...
    async def get_discovery_run(
        self, user_id: UUID, run_id: UUID
    ) -> JobDiscoveryRunRecord | None: ...
    async def claim_discovery_run(self, run_id: UUID) -> JobDiscoveryWorkItem | None: ...
    async def complete_discovery_run(
        self, run_id: UUID, results: tuple[JobSearchResult, ...]
    ) -> bool: ...
    async def fail_discovery_run(self, run_id: UUID, error_code: str) -> bool: ...
    async def create_or_get_job_draft(
        self, user_id: UUID, result_id: UUID
    ) -> JobDraftRecord | None: ...
    async def get_job_draft(self, user_id: UUID, draft_id: UUID) -> JobDraftRecord | None: ...
    async def update_job_draft(
        self, user_id: UUID, draft_id: UUID, expected_version: int, payload: JobDraftUpdate
    ) -> JobDraftRecord | None: ...
    async def confirm_job_draft(
        self, user_id: UUID, draft_id: UUID, description_hash: str
    ) -> JobRecord | None: ...
    async def commit(self) -> None: ...


class RunDispatcher(Protocol):
    async def dispatch(self, run_id: UUID) -> None: ...


class JobSearchProvider(Protocol):
    @property
    def provider_name(self) -> str: ...

    async def search(self, query: JobSearchQuery) -> tuple[JobSearchResult, ...]: ...


class AssistedImportService:
    def __init__(
        self,
        store: AssistedImportStore,
        cv_dispatcher: RunDispatcher,
        discovery_dispatcher: RunDispatcher,
        embedding_dispatcher: EmbeddingRunDispatcher,
        embedding_space: EmbeddingSpace,
        dashboard_cache: DashboardCacheInvalidator,
    ) -> None:
        self._store = store
        self._cv_dispatcher = cv_dispatcher
        self._discovery_dispatcher = discovery_dispatcher
        self._embedding_dispatcher = embedding_dispatcher
        self._embedding_space = embedding_space
        self._dashboard_cache = dashboard_cache

    async def submit_cv_import(
        self,
        *,
        user_id: UUID,
        idempotency_key: str,
        filename: str,
        media_type: str,
        content: bytes,
    ) -> CvImportRecord:
        document_type = detect_document_type(filename, content)
        content_sha256 = hashlib.sha256(content).hexdigest()
        record, created = await self._store.create_or_get_cv_import(
            user_id=user_id,
            idempotency_key=idempotency_key,
            filename=Path(filename).name,
            document_type=document_type,
            media_type=media_type,
            content=content,
            content_sha256=content_sha256,
            extractor_name=CV_EXTRACTOR_NAME,
        )
        if record.content_sha256 != content_sha256 or record.document_type != document_type:
            raise IdempotencyKeyConflictError()
        if created:
            await self._store.commit()
        if record.status == AssistedRunStatus.QUEUED:
            await self._cv_dispatcher.dispatch(record.id)
        return record

    async def get_cv_import(self, user_id: UUID, import_id: UUID) -> CvImportRecord:
        record = await self._store.get_cv_import(user_id, import_id)
        if record is None:
            raise AssistedResourceNotFoundError()
        return record

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
    ) -> ExperienceDraftRecord:
        current = await self._store.get_experience_draft(user_id, draft_id)
        if current is None:
            raise AssistedResourceNotFoundError()
        draft = await self._store.update_experience_draft(
            user_id=user_id,
            draft_id=draft_id,
            expected_version=expected_version,
            title=title,
            kind=kind,
            description=description,
            skills=skills,
            outcome=outcome,
        )
        if draft is None:
            raise AssistedResourceConflictError()
        await self._store.commit()
        return draft

    async def reject_experience_draft(self, user_id: UUID, draft_id: UUID) -> None:
        current = await self._store.get_experience_draft(user_id, draft_id)
        if current is None:
            raise AssistedResourceNotFoundError()
        if not await self._store.reject_experience_draft(user_id, draft_id):
            raise AssistedResourceConflictError()
        await self._store.commit()

    async def confirm_experience_draft(
        self, user_id: UUID, draft_id: UUID
    ) -> ExperienceRecord:
        current = await self._store.get_experience_draft(user_id, draft_id)
        if current is None:
            raise AssistedResourceNotFoundError()
        content_hash = compute_experience_content_hash(
            ExperienceCreate(
                user_id=user_id,
                title=current.title,
                kind=current.kind,
                description=current.description,
                skills=current.skills,
                outcome=current.outcome,
            )
        )
        confirmed = await self._store.confirm_experience_draft(
            user_id, draft_id, content_hash, self._embedding_space
        )
        if confirmed is None:
            raise AssistedResourceConflictError()
        experience, embedding_run_id = confirmed
        await self._store.commit()
        await self._embedding_dispatcher.dispatch(embedding_run_id)
        return experience

    async def submit_discovery_run(
        self, user_id: UUID, idempotency_key: str, query: JobSearchQuery
    ) -> JobDiscoveryRunRecord:
        fingerprint = compute_search_fingerprint(query)
        record, created = await self._store.create_or_get_discovery_run(
            user_id=user_id,
            idempotency_key=idempotency_key,
            query=query,
            query_fingerprint=fingerprint,
            provider_name=FAKE_JOB_SEARCH_PROVIDER,
        )
        if record.query_fingerprint != fingerprint:
            raise IdempotencyKeyConflictError()
        if created:
            await self._store.commit()
        if record.status == AssistedRunStatus.QUEUED:
            await self._discovery_dispatcher.dispatch(record.id)
        return record

    async def get_discovery_run(
        self, user_id: UUID, run_id: UUID
    ) -> JobDiscoveryRunRecord:
        record = await self._store.get_discovery_run(user_id, run_id)
        if record is None:
            raise AssistedResourceNotFoundError()
        return record

    async def create_job_draft(self, user_id: UUID, result_id: UUID) -> JobDraftRecord:
        draft = await self._store.create_or_get_job_draft(user_id, result_id)
        if draft is None:
            raise AssistedResourceNotFoundError()
        await self._store.commit()
        return draft

    async def get_job_draft(self, user_id: UUID, draft_id: UUID) -> JobDraftRecord:
        draft = await self._store.get_job_draft(user_id, draft_id)
        if draft is None:
            raise AssistedResourceNotFoundError()
        return draft

    async def update_job_draft(
        self,
        user_id: UUID,
        draft_id: UUID,
        expected_version: int,
        payload: JobDraftUpdate,
    ) -> JobDraftRecord:
        current = await self._store.get_job_draft(user_id, draft_id)
        if current is None:
            raise AssistedResourceNotFoundError()
        draft = await self._store.update_job_draft(user_id, draft_id, expected_version, payload)
        if draft is None:
            raise AssistedResourceConflictError()
        await self._store.commit()
        return draft

    async def confirm_job_draft(self, user_id: UUID, draft_id: UUID) -> JobRecord:
        current = await self._store.get_job_draft(user_id, draft_id)
        if current is None:
            raise AssistedResourceNotFoundError()
        if current.raw_description is None:
            raise AssistedResourceConflictError()
        job = await self._store.confirm_job_draft(
            user_id, draft_id, compute_description_hash(current.raw_description)
        )
        if job is None:
            raise AssistedResourceConflictError()
        await self._store.commit()
        await self._dashboard_cache.invalidate(user_id)
        return job


class CvImportExecutionService:
    def __init__(self, store: AssistedImportStore) -> None:
        self._store = store

    async def execute(self, import_id: UUID) -> bool:
        work = await self._store.claim_cv_import(import_id)
        if work is None:
            return False
        await self._store.commit()
        try:
            text = extract_document_text(work.document_type, work.filename, work.source_bytes)
            drafts = extract_experience_drafts(text)
            validate_extracted_drafts(text, drafts)
        except DocumentExtractionError as exc:
            await self._store.fail_cv_import(import_id, exc.code.value)
            await self._store.commit()
            return True
        except ValueError:
            await self._store.fail_cv_import(
                import_id, CvImportErrorCode.EXTRACTOR_FAILED.value
            )
            await self._store.commit()
            return True
        completed = await self._store.complete_cv_import(import_id, text, drafts)
        if completed:
            await self._store.commit()
        return completed


class JobDiscoveryExecutionService:
    def __init__(self, store: AssistedImportStore, provider: JobSearchProvider) -> None:
        self._store = store
        self._provider = provider

    async def execute(self, run_id: UUID) -> bool:
        work = await self._store.claim_discovery_run(run_id)
        if work is None:
            return False
        await self._store.commit()
        try:
            results = await self._provider.search(work.query)
            validate_search_results(results)
        except ValueError:
            await self._store.fail_discovery_run(
                run_id, JobDiscoveryErrorCode.SEARCH_OUTPUT_INVALID.value
            )
            await self._store.commit()
            return True
        except Exception:
            await self._store.fail_discovery_run(
                run_id, JobDiscoveryErrorCode.SEARCH_FAILED.value
            )
            await self._store.commit()
            return True
        completed = await self._store.complete_discovery_run(run_id, results)
        if completed:
            await self._store.commit()
        return completed


def detect_document_type(filename: str, content: bytes) -> DocumentType:
    if not content or len(content) > MAX_CV_BYTES:
        raise InvalidDocumentError("CV file must be between 1 byte and 5 MiB.")
    suffix = Path(filename).suffix.casefold()
    if content.startswith(b"%PDF-"):
        return DocumentType.PDF
    if content.startswith(bytes.fromhex("D0CF11E0A1B11AE1")) and suffix == ".doc":
        return DocumentType.DOC
    if content.lstrip().startswith(b"{\\rtf") and suffix == ".rtf":
        return DocumentType.RTF
    if content.startswith(b"PK\x03\x04"):
        if suffix == ".docx":
            return DocumentType.DOCX
        if suffix == ".odt":
            return DocumentType.ODT
    if suffix in {".txt", ".md", ".markdown"} and b"\x00" not in content:
        try:
            content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise InvalidDocumentError("Text CV files must use UTF-8 encoding.") from exc
        return DocumentType.MARKDOWN if suffix in {".md", ".markdown"} else DocumentType.TEXT
    raise InvalidDocumentError("Unsupported or mismatched CV file type.")


def extract_experience_drafts(text: str) -> tuple[ExtractedExperienceDraft, ...]:
    blocks = [block.strip() for block in text.split("\n\n") if block.strip()]
    if not blocks:
        raise ValueError("No extractable CV blocks.")
    drafts: list[ExtractedExperienceDraft] = []
    search_start = 0
    for block in blocks[:20]:
        start = text.find(block, search_start)
        end = start + len(block)
        search_start = end
        lines = [line.strip(" \t-•") for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        title = lines[0][:200]
        description = "\n".join(lines[1:]) or title
        drafts.append(
            ExtractedExperienceDraft(
                title=title,
                kind=ExperienceKind.OTHER,
                description=description[:10_000],
                skills=(),
                outcome=None,
                source_refs=(
                    SourceReference(field="source_block", start=start, end=end, quote=block),
                ),
            )
        )
    if not drafts:
        raise ValueError("No extractable CV blocks.")
    return tuple(drafts)


def validate_extracted_drafts(
    source_text: str, drafts: tuple[ExtractedExperienceDraft, ...]
) -> None:
    for draft in drafts:
        if not draft.source_refs:
            raise ValueError("Draft has no source reference.")
        for ref in draft.source_refs:
            if (
                ref.start < 0
                or ref.end <= ref.start
                or ref.end > len(source_text)
                or source_text[ref.start : ref.end] != ref.quote
            ):
                raise ValueError("Draft source reference is not grounded.")
        source = "\n".join(ref.quote for ref in draft.source_refs).casefold()
        if draft.title.casefold() not in source:
            raise ValueError("Draft title is not grounded.")
        for skill in draft.skills:
            if skill.casefold() not in source:
                raise ValueError("Draft skill is not grounded.")
        if draft.outcome is not None and draft.outcome.casefold() not in source:
            raise ValueError("Draft outcome is not grounded.")


def compute_search_fingerprint(query: JobSearchQuery) -> str:
    encoded = json.dumps(
        {
            "query": query.query,
            "location": query.location,
            "remote": query.remote,
            "published_within_days": query.published_within_days,
            "provider": FAKE_JOB_SEARCH_PROVIDER,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def validate_search_results(results: tuple[JobSearchResult, ...]) -> None:
    seen: set[str] = set()
    for result in results:
        parsed = urlparse(result.source_url)
        if (
            not result.provider_result_id
            or result.provider_result_id in seen
            or not result.company.strip()
            or not result.title.strip()
            or parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or not result.summary.strip()
        ):
            raise ValueError("Search provider returned invalid output.")
        seen.add(result.provider_result_id)
