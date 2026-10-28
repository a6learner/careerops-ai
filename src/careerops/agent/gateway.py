from typing import Literal
from uuid import NAMESPACE_URL, UUID, uuid5

import httpx
from pydantic import BaseModel

from careerops.agent.client import ProjectAgentClient
from careerops.agent.contracts import (
    AgentConfig,
    AgentError,
    PendingCheckpoint,
    PendingPage,
    PendingSummary,
    RecordQuery,
    SubmissionResult,
)
from careerops.agent.storage import ProtectedStore
from careerops.domain.project_records import (
    CheckpointInput,
    CheckpointPage,
    CheckpointRecord,
    ProjectInput,
    ProjectPage,
    ProjectRecord,
)
from careerops.services.project_records import content_hash


class ProjectContext(BaseModel):
    project: ProjectRecord
    confirmed_records: CheckpointPage


class ProjectAgent:
    def __init__(
        self,
        config: AgentConfig,
        store: ProtectedStore,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.config = config
        self.store = store
        self._transport = transport

    def _client(self) -> ProjectAgentClient:
        # Reload after a terminal login; a long-running host must not cache an expired token.
        return ProjectAgentClient(self.config, self.store.credentials(), self._transport)

    async def list_projects(self, query: RecordQuery) -> ProjectPage:
        return await self._client().list_projects(query)

    async def register_project(self, payload: ProjectInput, idempotency_key: UUID) -> ProjectRecord:
        return await self._client().register_project(payload, idempotency_key)

    async def get_project_context(self, project_id: UUID) -> ProjectContext:
        client = self._client()
        project = await client.get_project(project_id)
        records = await client.search(project_id, RecordQuery())
        return ProjectContext(project=project, confirmed_records=records)

    async def search_project_evidence(self, project_id: UUID, query: RecordQuery) -> CheckpointPage:
        return await self._client().search(project_id, query)

    async def get_evidence(self, project_id: UUID, checkpoint_id: UUID) -> CheckpointRecord:
        return await self._client().get_evidence(project_id, checkpoint_id)

    async def save_checkpoint(
        self,
        project_id: UUID,
        payload: CheckpointInput,
        idempotency_key: UUID,
        approved_for_upload: Literal[True],
    ) -> SubmissionResult:
        if approved_for_upload is not True:
            raise AgentError(
                "UPLOAD_NOT_APPROVED", "Select and authorize the excerpt upload first."
            )
        client = self._client()
        packet = PendingCheckpoint(
            packet_id=uuid5(NAMESPACE_URL, f"{client.credentials.user_id}:{idempotency_key}"),
            api_url=self.config.api_url.rstrip("/"),
            user_id=client.credentials.user_id,
            project_id=project_id,
            idempotency_key=idempotency_key,
            payload=payload,
            content_sha256=content_hash(payload),
        )
        name = packet_name(packet.packet_id)
        if not self.store.write(name, packet.model_dump_json().encode("utf-8")):
            existing = self.store.read(name, PendingCheckpoint)
            if existing != packet:
                raise AgentError(
                    "LOCAL_INPUT_CONFLICT", "This key already identifies a different local packet."
                )
        return await self._submit(packet)

    async def replay_checkpoint(self, packet_id: UUID) -> SubmissionResult:
        packet = self.store.read(packet_name(packet_id), PendingCheckpoint)
        if packet.packet_id != packet_id:
            raise AgentError("PACKET_CHANGED", "Packet identity does not match its saved filename.")
        return await self._submit(packet)

    async def _submit(self, packet: PendingCheckpoint) -> SubmissionResult:
        client = self._client()
        expected_id = uuid5(NAMESPACE_URL, f"{packet.user_id}:{packet.idempotency_key}")
        if packet.packet_id != expected_id:
            raise AgentError(
                "PACKET_CHANGED", "The pending packet identity changed; nothing was sent."
            )
        if (
            packet.api_url != self.config.api_url.rstrip("/")
            or packet.user_id != client.credentials.user_id
        ):
            raise AgentError(
                "ACCOUNT_MISMATCH",
                "This packet belongs to a different API or account; nothing was sent.",
            )
        if content_hash(packet.payload) != packet.content_sha256:
            raise AgentError("PACKET_CHANGED", "The pending packet changed; nothing was sent.")
        try:
            record = await client.save_checkpoint(
                packet.project_id, packet.payload, packet.idempotency_key
            )
            if (
                record.project_id != packet.project_id
                or record.content_sha256 != packet.content_sha256
                or content_hash(record.payload) != packet.content_sha256
            ):
                raise AgentError(
                    "INVALID_RECEIPT",
                    "Receipt does not match the packet; keep the original key.",
                    True,
                )
            result = SubmissionResult(
                packet_id=packet.packet_id,
                state="accepted",
                record=record,
                message="Saved as the returned review state; no personal claim was auto-confirmed.",
            )
        except AgentError as exc:
            pending = exc.retryable or exc.code == "LOGIN_REQUIRED"
            result = SubmissionResult(
                packet_id=packet.packet_id,
                state="pending" if pending else "rejected",
                error_code=exc.code,
                message=exc.message,
            )
        try:
            self.store.write(
                receipt_name(packet.packet_id),
                result.model_dump_json().encode("utf-8"),
                replace=True,
            )
        except AgentError:
            # The server may already have committed: preserve the packet and never invent a new key.
            return SubmissionResult(
                packet_id=packet.packet_id,
                state="pending",
                error_code="RECEIPT_NOT_SAVED",
                message="Local receipt was not saved; replay the original packet.",
            )
        return result

    def list_pending_checkpoints(self, limit: int = 20) -> PendingPage:
        if not 1 <= limit <= 100:
            raise AgentError("INVALID_LIMIT", "Pending limit must be between 1 and 100.")
        client = self._client()
        items: list[PendingSummary] = []
        if not self.store.root.exists():
            return PendingPage(items=[], has_more=False)
        for path in sorted(self.store.root.glob("packet-*.bin")):
            packet = self.store.read(path.name, PendingCheckpoint)
            if path.name != packet_name(packet.packet_id):
                raise AgentError(
                    "PACKET_CHANGED", "Packet identity does not match its saved filename."
                )
            if (
                packet.user_id != client.credentials.user_id
                or packet.api_url != self.config.api_url.rstrip("/")
            ):
                continue
            receipt_path = self.store.root / receipt_name(packet.packet_id)
            result = (
                self.store.read(receipt_path.name, SubmissionResult)
                if receipt_path.exists()
                else None
            )
            if result is not None and result.packet_id != packet.packet_id:
                raise AgentError(
                    "INVALID_RECEIPT", "Local receipt identity does not match its packet."
                )
            if result is not None and result.state == "accepted":
                continue
            items.append(
                PendingSummary(
                    packet_id=packet.packet_id,
                    project_id=packet.project_id,
                    title=packet.payload.title,
                    state="rejected"
                    if result is not None and result.state == "rejected"
                    else "pending",
                    error_code=result.error_code if result is not None else None,
                )
            )
            if len(items) > limit:
                break
        return PendingPage(items=items[:limit], has_more=len(items) > limit)


def packet_name(packet_id: UUID) -> str:
    return f"packet-{packet_id}.bin"


def receipt_name(packet_id: UUID) -> str:
    return f"receipt-{packet_id}.bin"
