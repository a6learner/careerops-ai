import base64
import json
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import pytest
from pydantic import SecretStr, ValidationError

from careerops.agent.client import ProjectAgentClient, login
from careerops.agent.contracts import (
    AgentConfig,
    AgentCredentials,
    AgentError,
    PendingCheckpoint,
    RecordQuery,
    SubmissionResult,
)
from careerops.agent.gateway import ProjectAgent, packet_name, receipt_name
from careerops.agent.storage import ProtectedStore, WindowsProtector
from careerops.domain.project_records import CheckpointInput, CheckpointRecord, EvidenceSource
from careerops.services.project_records import content_hash


class FakeProtector:
    """Deterministic test envelope; never used by the production client."""

    def protect(self, data: bytes) -> bytes:
        return b"test-envelope:" + base64.b64encode(data)

    def unprotect(self, data: bytes) -> bytes:
        if not data.startswith(b"test-envelope:"):
            raise ValueError("Invalid test envelope")
        return base64.b64decode(data.removeprefix(b"test-envelope:"), validate=True)


def example_payload(title: str = "Protect duplicate writes") -> CheckpointInput:
    return CheckpointInput(
        title=title,
        objective="Keep retries safe",
        changes="Added a database uniqueness rule",
        host="synthetic-test",
        sources=(
            EvidenceSource(
                kind="repository_excerpt",
                locator="src/example.py",
                content="A unique key prevents duplicate writes.",
                quote="unique key prevents duplicate writes",
            ),
        ),
    )


@dataclass
class FakeBackend:
    owner: UUID
    project: UUID
    store: ProtectedStore
    lose_first_post: bool = False
    rejected_token: str | None = None
    actual_identity: UUID | None = None
    bad_receipt: bool = False
    requests: list[httpx.Request] = field(default_factory=list)
    posts: list[httpx.Request] = field(default_factory=list)
    records: dict[str, CheckpointRecord] = field(default_factory=dict)

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.headers.get("authorization") == f"Bearer {self.rejected_token}":
            return httpx.Response(401, json={"debug": "private server data"})
        if request.url.path == "/api/v1/auth/me":
            return httpx.Response(200, json={"id": str(self.actual_identity or self.owner)})
        if request.method == "POST":
            # The packet must survive a process exit before the server commits anything.
            pending_files = list(self.store.root.glob("packet-*.bin"))
            assert len(pending_files) == 1
            packet = self.store.read(pending_files[0].name, PendingCheckpoint)
            assert str(packet.idempotency_key) == request.headers["idempotency-key"]
            assert packet.payload == CheckpointInput.model_validate_json(request.content)
            self.posts.append(request)
            key = request.headers["idempotency-key"]
            if key not in self.records:
                payload = CheckpointInput.model_validate_json(request.content)
                self.records[key] = CheckpointRecord(
                    id=uuid4(),
                    project_id=self.project,
                    status="draft",
                    version=1,
                    payload=payload,
                    content_sha256=content_hash(payload),
                    contribution_note="",
                    created_at=datetime.now(UTC),
                    reviewed_at=None,
                )
            if self.lose_first_post and len(self.posts) == 1:
                raise httpx.ReadTimeout("private diagnostic: synthetic-token", request=request)
            record = self.records[key]
            if self.bad_receipt:
                record = record.model_copy(update={"project_id": uuid4()})
            return httpx.Response(201, json=record.model_dump(mode="json"))
        return httpx.Response(200, json={"items": [], "next_cursor": None})


@dataclass
class AgentFixture:
    config: AgentConfig
    credentials: AgentCredentials
    store: ProtectedStore
    backend: FakeBackend
    agent: ProjectAgent


def make_agent(tmp_path: Path) -> AgentFixture:
    config = AgentConfig(state_dir=tmp_path / "private-state")
    credentials = AgentCredentials(
        api_url=config.api_url,
        user_id=uuid4(),
        access_token=SecretStr("synthetic-token"),
    )
    store = ProtectedStore(config.state_dir, FakeProtector())
    store.save_credentials(credentials)
    backend = FakeBackend(credentials.user_id, uuid4(), store)
    agent = ProjectAgent(config, store, httpx.MockTransport(backend))
    return AgentFixture(config, credentials, store, backend, agent)


@pytest.mark.asyncio
async def test_packet_is_durable_before_post_and_lost_response_replays_original_key(
    tmp_path: Path,
) -> None:
    fixture = make_agent(tmp_path)
    fixture.backend.lose_first_post = True
    key = uuid4()
    first = await fixture.agent.save_checkpoint(
        fixture.backend.project,
        example_payload(),
        key,
        approved_for_upload=True,
    )
    assert first.state == "pending"
    assert first.record is None
    assert first.error_code == "API_UNAVAILABLE"
    assert "synthetic-token" not in first.model_dump_json()
    assert len(fixture.backend.records) == 1
    summaries = fixture.agent.list_pending_checkpoints()
    assert [item.packet_id for item in summaries.items] == [first.packet_id]
    # A new process/session has no in-memory submission cache.
    second_agent = ProjectAgent(fixture.config, fixture.store, httpx.MockTransport(fixture.backend))
    replay = await second_agent.replay_checkpoint(first.packet_id)
    assert replay.state == "accepted"
    assert replay.record is not None
    assert replay.record.id == fixture.backend.records[str(key)].id
    assert len(fixture.backend.records) == 1
    assert len(fixture.backend.posts) == 2
    assert (
        fixture.backend.posts[0].headers["idempotency-key"]
        == fixture.backend.posts[1].headers["idempotency-key"]
    )
    assert fixture.backend.posts[0].content == fixture.backend.posts[1].content
    assert second_agent.list_pending_checkpoints().items == []


@pytest.mark.asyncio
async def test_same_key_with_changed_payload_is_refused_before_network(tmp_path: Path) -> None:
    fixture = make_agent(tmp_path)
    key = uuid4()
    await fixture.agent.save_checkpoint(fixture.backend.project, example_payload(), key, True)
    request_count = len(fixture.backend.requests)
    with pytest.raises(AgentError) as error:
        await fixture.agent.save_checkpoint(
            fixture.backend.project,
            example_payload("Different stage"),
            key,
            True,
        )
    assert error.value.code == "LOCAL_INPUT_CONFLICT"
    assert len(fixture.backend.requests) == request_count
    assert len(fixture.backend.records) == 1


@pytest.mark.asyncio
async def test_upload_requires_explicit_approval_before_packet_or_network(tmp_path: Path) -> None:
    fixture = make_agent(tmp_path)
    with pytest.raises(AgentError) as error:
        await fixture.agent.save_checkpoint(
            fixture.backend.project,
            example_payload(),
            uuid4(),
            approved_for_upload=False,
        )
    assert error.value.code == "UPLOAD_NOT_APPROVED"
    assert fixture.backend.requests == []
    assert list(fixture.store.root.glob("packet-*.bin")) == []


@pytest.mark.asyncio
async def test_replay_refuses_changed_packet_digest_before_network(tmp_path: Path) -> None:
    fixture = make_agent(tmp_path)
    fixture.backend.lose_first_post = True
    result = await fixture.agent.save_checkpoint(
        fixture.backend.project,
        example_payload(),
        uuid4(),
        True,
    )
    name = packet_name(result.packet_id)
    packet = fixture.store.read(name, PendingCheckpoint)
    corrupted = packet.model_copy(update={"content_sha256": "0" * 64})
    fixture.store.write(name, corrupted.model_dump_json().encode(), replace=True)
    request_count = len(fixture.backend.requests)
    with pytest.raises(AgentError) as error:
        await fixture.agent.replay_checkpoint(result.packet_id)
    assert error.value.code == "PACKET_CHANGED"
    assert len(fixture.backend.requests) == request_count


@pytest.mark.asyncio
async def test_unprotected_state_never_falls_back_to_network(tmp_path: Path) -> None:
    fixture = make_agent(tmp_path)
    (fixture.store.root / "credentials.bin").write_bytes(b"plaintext synthetic-token")
    with pytest.raises(AgentError) as error:
        await fixture.agent.save_checkpoint(
            fixture.backend.project, example_payload(), uuid4(), True
        )
    assert error.value.code == "STATE_UNAVAILABLE"
    assert fixture.backend.requests == []


@pytest.mark.asyncio
async def test_expired_session_keeps_packet_and_reload_credentials_restores_submission(
    tmp_path: Path,
) -> None:
    fixture = make_agent(tmp_path)
    fixture.backend.rejected_token = "synthetic-token"
    result = await fixture.agent.save_checkpoint(
        fixture.backend.project,
        example_payload(),
        uuid4(),
        True,
    )
    assert result.state == "pending" and result.error_code == "LOGIN_REQUIRED"
    assert fixture.backend.posts == []
    renewed = fixture.credentials.model_copy(update={"access_token": SecretStr("renewed-token")})
    fixture.store.save_credentials(renewed)
    replay = await fixture.agent.replay_checkpoint(result.packet_id)
    assert replay.state == "accepted"
    assert fixture.backend.posts[0].headers["authorization"] == "Bearer renewed-token"


@pytest.mark.asyncio
async def test_replay_refuses_changed_account_without_sending_packet(tmp_path: Path) -> None:
    fixture = make_agent(tmp_path)
    fixture.backend.lose_first_post = True
    result = await fixture.agent.save_checkpoint(
        fixture.backend.project,
        example_payload(),
        uuid4(),
        True,
    )
    switched = fixture.credentials.model_copy(update={"user_id": uuid4()})
    fixture.store.save_credentials(switched)
    count = len(fixture.backend.requests)
    with pytest.raises(AgentError) as error:
        await fixture.agent.replay_checkpoint(result.packet_id)
    assert error.value.code == "ACCOUNT_MISMATCH"
    assert len(fixture.backend.requests) == count


@pytest.mark.asyncio
async def test_api_identity_mismatch_does_not_post_and_preserves_rejected_packet(
    tmp_path: Path,
) -> None:
    fixture = make_agent(tmp_path)
    fixture.backend.actual_identity = uuid4()
    result = await fixture.agent.save_checkpoint(
        fixture.backend.project,
        example_payload(),
        uuid4(),
        True,
    )
    assert result.state == "rejected" and result.error_code == "ACCOUNT_MISMATCH"
    assert fixture.backend.posts == []
    assert fixture.agent.list_pending_checkpoints().items[0].state == "rejected"


@pytest.mark.parametrize(
    "origin",
    [
        "https://example.com",
        "http://127.0.0.1.evil.example",
        "http://user:password@localhost",
        "http://127.0.0.1/api",
        "http://127.0.0.1?token=secret",
        "http://127.0.0.1/#fragment",
        "http://192.168.1.1",
        "http://localhost:0",
    ],
)
def test_config_refuses_remote_or_ambiguous_origin(tmp_path: Path, origin: str) -> None:
    with pytest.raises(ValidationError):
        AgentConfig(api_url=origin, state_dir=tmp_path)


def test_credentials_cannot_be_reused_at_another_local_origin(tmp_path: Path) -> None:
    fixture = make_agent(tmp_path)
    with pytest.raises(AgentError) as error:
        ProjectAgentClient(
            fixture.config.model_copy(update={"api_url": "http://127.0.0.1:9999"}),
            fixture.credentials,
        )
    assert error.value.code == "ORIGIN_MISMATCH"


@pytest.mark.asyncio
async def test_evidence_search_defaults_to_confirmed_and_current_api_data(tmp_path: Path) -> None:
    fixture = make_agent(tmp_path)
    page = await fixture.agent.search_project_evidence(
        fixture.backend.project,
        RecordQuery(query="unique", cursor="page-token", limit=7),
    )
    assert page.items == []
    request = fixture.backend.requests[-1]
    assert request.method == "GET"
    assert dict(request.url.params) == {
        "limit": "7",
        "cursor": "page-token",
        "status": "confirmed",
        "q": "unique",
    }


@pytest.mark.parametrize("status", [302, 401, 404, 409, 422, 429, 503])
@pytest.mark.asyncio
async def test_api_errors_never_forward_raw_body_or_access_token(
    tmp_path: Path, status: int
) -> None:
    fixture = make_agent(tmp_path)
    requests: list[httpx.Request] = []

    def response(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            status,
            json={"debug": "sensitive-body synthetic-token"},
            headers={"location": "https://example.test/steal"},
        )

    client = ProjectAgentClient(fixture.config, fixture.credentials, httpx.MockTransport(response))
    with pytest.raises(AgentError) as error:
        await client.list_projects(RecordQuery())
    assert "sensitive-body" not in str(error.value)
    assert "synthetic-token" not in str(error.value)
    assert len(requests) == 1


@pytest.mark.asyncio
async def test_malformed_success_is_not_accepted_or_echoed(tmp_path: Path) -> None:
    fixture = make_agent(tmp_path)
    client = ProjectAgentClient(
        fixture.config,
        fixture.credentials,
        httpx.MockTransport(
            lambda request: httpx.Response(
                200, json={"access_token": "sensitive-body synthetic-token"}
            ),
        ),
    )
    with pytest.raises(AgentError) as error:
        await client.list_projects(RecordQuery())
    assert error.value.code == "INVALID_API_RESPONSE"
    assert error.value.retryable is True
    assert "synthetic-token" not in str(error.value)


@pytest.mark.asyncio
async def test_mismatched_receipt_stays_pending(tmp_path: Path) -> None:
    fixture = make_agent(tmp_path)
    fixture.backend.bad_receipt = True
    result = await fixture.agent.save_checkpoint(
        fixture.backend.project,
        example_payload(),
        uuid4(),
        True,
    )
    assert result.state == "pending" and result.error_code == "INVALID_RECEIPT"
    assert result.record is None
    assert fixture.agent.list_pending_checkpoints().items[0].packet_id == result.packet_id


@pytest.mark.asyncio
async def test_local_receipt_failure_preserves_original_packet_for_safe_replay(
    tmp_path: Path,
) -> None:
    class ReceiptFailureStore(ProtectedStore):
        fail_receipt = True

        def write(self, name: str, data: bytes, replace: bool = False) -> bool:
            if self.fail_receipt and name.startswith("receipt-"):
                raise AgentError("STATE_WRITE_FAILED", "Test receipt write failed")
            return super().write(name, data, replace)

    config = AgentConfig(state_dir=tmp_path)
    credentials = AgentCredentials(
        api_url=config.api_url, user_id=uuid4(), access_token=SecretStr("synthetic-token")
    )
    store = ReceiptFailureStore(tmp_path, FakeProtector())
    store.save_credentials(credentials)
    backend = FakeBackend(credentials.user_id, uuid4(), store)
    agent = ProjectAgent(config, store, httpx.MockTransport(backend))
    result = await agent.save_checkpoint(backend.project, example_payload(), uuid4(), True)
    assert result.state == "pending" and result.error_code == "RECEIPT_NOT_SAVED"
    assert (tmp_path / packet_name(result.packet_id)).exists()
    store.fail_receipt = False
    replay = await agent.replay_checkpoint(result.packet_id)
    assert replay.state == "accepted" and len(backend.records) == 1


@pytest.mark.parametrize("operation", ["mkdir", "mkstemp"])
@pytest.mark.asyncio
async def test_receipt_staging_permission_failure_returns_pending_without_reposting(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    operation: str,
) -> None:
    from careerops.agent import storage as storage_module

    fixture = make_agent(tmp_path)
    calls = 0
    if operation == "mkstemp":
        original_staging = storage_module.tempfile.mkstemp

        def staging(*, prefix: str, dir: Path) -> tuple[int, str]:
            nonlocal calls
            calls += 1
            if calls == 2:
                raise PermissionError("synthetic receipt staging permission failure")
            return original_staging(prefix=prefix, dir=dir)

        monkeypatch.setattr(storage_module.tempfile, "mkstemp", staging)
    else:
        original_mkdir = Path.mkdir

        def mkdir(
            path: Path, mode: int = 0o777, parents: bool = False, exist_ok: bool = False
        ) -> None:
            nonlocal calls
            if path == fixture.store.root:
                calls += 1
                if calls == 2:
                    raise PermissionError("synthetic receipt directory permission failure")
            original_mkdir(path, mode=mode, parents=parents, exist_ok=exist_ok)

        monkeypatch.setattr(Path, "mkdir", mkdir)
    result = await fixture.agent.save_checkpoint(
        fixture.backend.project,
        example_payload(),
        uuid4(),
        True,
    )
    assert result.state == "pending" and result.error_code == "RECEIPT_NOT_SAVED"
    assert len(fixture.backend.posts) == 1 and len(fixture.backend.records) == 1
    assert (fixture.store.root / packet_name(result.packet_id)).exists()
    assert not (fixture.store.root / receipt_name(result.packet_id)).exists()
    assert calls == 2


@pytest.mark.parametrize("change", ["packet_id", "idempotency_key"])
@pytest.mark.asyncio
async def test_replay_rejects_filename_or_derived_packet_identity_mismatch(
    tmp_path: Path,
    change: str,
) -> None:
    fixture = make_agent(tmp_path)
    fixture.backend.lose_first_post = True
    result = await fixture.agent.save_checkpoint(
        fixture.backend.project,
        example_payload(),
        uuid4(),
        True,
    )
    name = packet_name(result.packet_id)
    packet = fixture.store.read(name, PendingCheckpoint)
    altered = packet.model_copy(update={change: uuid4()})
    fixture.store.write(name, altered.model_dump_json().encode(), replace=True)
    request_count = len(fixture.backend.requests)
    with pytest.raises(AgentError) as error:
        await fixture.agent.replay_checkpoint(result.packet_id)
    assert error.value.code == "PACKET_CHANGED"
    assert len(fixture.backend.requests) == request_count


@pytest.mark.asyncio
async def test_receipt_for_another_packet_cannot_hide_submission_from_pending_list(
    tmp_path: Path,
) -> None:
    fixture = make_agent(tmp_path)
    fixture.backend.lose_first_post = True
    pending = await fixture.agent.save_checkpoint(
        fixture.backend.project,
        example_payload(),
        uuid4(),
        True,
    )
    name = receipt_name(pending.packet_id)
    receipt = fixture.store.read(name, SubmissionResult)
    incorrect = receipt.model_copy(update={"packet_id": uuid4(), "state": "accepted"})
    fixture.store.write(name, incorrect.model_dump_json().encode(), replace=True)
    with pytest.raises(AgentError) as error:
        fixture.agent.list_pending_checkpoints()
    assert error.value.code == "INVALID_RECEIPT"


def test_state_uses_protector_and_rejects_corrupt_or_traversing_files(tmp_path: Path) -> None:
    fixture = make_agent(tmp_path)
    raw = (fixture.store.root / "credentials.bin").read_bytes()
    assert b"synthetic-token" not in raw
    assert fixture.store.credentials() == fixture.credentials
    for name in ("../escape.bin", "nested/state.bin", "C:\\state.bin"):
        with pytest.raises(AgentError) as error:
            fixture.store.read(name, AgentCredentials)
        assert error.value.code == "INVALID_STATE_PATH"
    (fixture.store.root / "corrupt.bin").write_bytes(b"not a protected envelope")
    with pytest.raises(AgentError) as corrupt:
        fixture.store.read("corrupt.bin", AgentCredentials)
    assert corrupt.value.code == "STATE_UNAVAILABLE"
    assert list(fixture.store.root.glob(".writing-*")) == []


@pytest.mark.skipif(
    os.name != "nt", reason="Windows DPAPI has no cross-platform plaintext fallback"
)
def test_windows_dpapi_roundtrip_does_not_store_plaintext(tmp_path: Path) -> None:
    protector = WindowsProtector()
    secret = b"synthetic DPAPI test material"
    encrypted = protector.protect(secret)
    assert encrypted != secret and secret not in encrypted
    assert protector.unprotect(encrypted) == secret
    store = ProtectedStore(tmp_path)
    credentials = AgentCredentials(
        api_url="http://127.0.0.1:8000", user_id=uuid4(), access_token=SecretStr("synthetic-token")
    )
    store.save_credentials(credentials)
    assert b"synthetic-token" not in (tmp_path / "credentials.bin").read_bytes()
    assert store.credentials() == credentials


@pytest.mark.asyncio
async def test_login_token_is_secret_and_identity_is_loaded_from_api(tmp_path: Path) -> None:
    identity = uuid4()
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.url.path == "/api/v1/auth/login":
            assert json.loads(request.content) == {
                "email": "candidate@example.com",
                "password": "synthetic-password",
            }
            return httpx.Response(200, json={"access_token": "synthetic-token"})
        assert request.headers["authorization"] == "Bearer synthetic-token"
        return httpx.Response(200, json={"id": str(identity)})

    credentials = await login(
        AgentConfig(state_dir=tmp_path),
        "candidate@example.com",
        "synthetic-password",
        httpx.MockTransport(handler),
    )
    assert credentials.user_id == identity
    assert "synthetic-token" not in repr(credentials)
    assert "synthetic-token" not in credentials.model_dump_json()
    assert len(calls) == 2
