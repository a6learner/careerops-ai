import base64
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import pytest
from pydantic import SecretStr

pytest.importorskip("mcp")

from mcp import Client
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.types import CallToolResult

from careerops.agent.contracts import AgentConfig, AgentCredentials, PendingCheckpoint
from careerops.agent.gateway import ProjectAgent
from careerops.agent.mcp_server import build_server
from careerops.agent.storage import ProtectedStore
from careerops.domain.project_records import (
    CheckpointInput,
    CheckpointRecord,
    EvidenceSource,
    RecordStatus,
)
from careerops.services.project_records import content_hash

TOOLS = {
    "list_projects",
    "register_project",
    "get_project_context",
    "save_checkpoint",
    "search_project_evidence",
    "get_evidence",
    "replay_checkpoint",
    "list_pending_checkpoints",
}
PRIVATE = "synthetic-private-token-and-server-diagnostic"


class FakeProtector:
    def protect(self, data: bytes) -> bytes:
        return b"test:" + base64.b64encode(data)

    def unprotect(self, data: bytes) -> bytes:
        assert data.startswith(b"test:")
        return base64.b64decode(data[5:], validate=True)


def payload() -> CheckpointInput:
    return CheckpointInput(
        title="Retry safely",
        objective="Avoid duplicate records",
        changes="Added idempotency",
        host="synthetic-sdk-test",
        sources=(
            EvidenceSource(
                kind="test_output",
                locator="tests/example.txt",
                content="Duplicate retries return the original record.",
                quote="original record",
            ),
        ),
    )


@dataclass
class Backend:
    owner: UUID
    project: UUID
    store: ProtectedStore
    lose_response: bool = False
    requests: list[httpx.Request] = field(default_factory=list)
    posts: list[httpx.Request] = field(default_factory=list)
    records: dict[str, CheckpointRecord] = field(default_factory=dict)

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.url.path == "/api/v1/auth/me":
            return httpx.Response(200, json={"id": str(self.owner)})
        if request.method == "POST":
            packets = list(self.store.root.glob("packet-*.bin"))
            assert len(packets) == 1
            packet = self.store.read(packets[0].name, PendingCheckpoint)
            key = request.headers["idempotency-key"]
            assert str(packet.idempotency_key) == key
            self.posts.append(request)
            if key not in self.records:
                body = CheckpointInput.model_validate_json(request.content)
                self.records[key] = CheckpointRecord(
                    id=uuid4(),
                    project_id=self.project,
                    status="draft",
                    version=1,
                    payload=body,
                    content_sha256=content_hash(body),
                    contribution_note="",
                    created_at=datetime.now(UTC),
                    reviewed_at=None,
                )
            if self.lose_response and len(self.posts) == 1:
                raise httpx.ReadTimeout(PRIVATE, request=request)
            return httpx.Response(201, json=self.records[key].model_dump(mode="json"))
        if request.url.path == f"/api/v1/projects/{self.project}":
            return httpx.Response(
                200,
                json={
                    "id": str(self.project),
                    "name": "Synthetic project",
                    "goal": "Reliability",
                    "created_at": datetime.now(UTC).isoformat(),
                },
            )
        if request.url.path.endswith("/checkpoints"):
            items = [
                r.model_dump(mode="json")
                for r in self.records.values()
                if r.status == request.url.params.get("status")
            ]
            return httpx.Response(200, json={"items": items, "next_cursor": None})
        for record in self.records.values():
            if request.url.path.endswith(f"/{record.id}"):
                return httpx.Response(200, json=record.model_dump(mode="json"))
        return httpx.Response(200, json={"items": [], "next_cursor": None})


def fixture_agent(tmp_path: Path) -> tuple[ProjectAgent, Backend]:
    config = AgentConfig(state_dir=tmp_path / "protected")
    store = ProtectedStore(config.state_dir, FakeProtector())
    credentials = AgentCredentials(
        api_url=config.api_url,
        user_id=uuid4(),
        access_token=SecretStr(PRIVATE),
    )
    store.save_credentials(credentials)
    backend = Backend(credentials.user_id, uuid4(), store)
    return ProjectAgent(config, store, httpx.MockTransport(backend)), backend


def output(result: CallToolResult, *, expected_error: bool = False) -> dict[str, object]:
    assert bool(result.is_error) is expected_error, result.model_dump_json()
    assert isinstance(result.structured_content, dict)
    return result.structured_content


def safe_error(result: CallToolResult) -> str:
    assert result.is_error
    text = result.model_dump_json()
    assert PRIVATE not in text
    assert "Traceback" not in text
    return text


@pytest.mark.asyncio
async def test_official_stdio_discovery_and_unauthenticated_error(tmp_path: Path) -> None:
    private_state = tmp_path / "never-signed-in"
    environment = dict(os.environ)
    environment.update(
        {
            "CAREEROPS_AGENT_STATE_DIR": str(private_state),
            "CAREEROPS_AGENT_API_URL": "http://127.0.0.1:1",
            "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src"),
        }
    )
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "careerops.agent.mcp_server"],
        env=environment,
        cwd=Path(__file__).resolve().parents[1],
    )
    error_log = tmp_path / "server-stderr.txt"
    with error_log.open("w", encoding="utf-8") as stderr:
        async with Client(
            stdio_client(parameters, errlog=stderr), read_timeout_seconds=15
        ) as client:
            tools = await client.list_tools()
            assert {tool.name for tool in tools.tools} == TOOLS
            result = await client.call_tool("list_projects", {})
            assert "STATE_UNAVAILABLE" in safe_error(result)
            assert str(private_state) not in result.model_dump_json()
            invalid = await client.call_tool(
                "save_checkpoint",
                {
                    "project_id": PRIVATE,
                    "payload": {"title": PRIVATE},
                    "idempotency_key": PRIVATE,
                    "approved_for_upload": False,
                },
            )
            assert "INVALID_TOOL_INPUT" in safe_error(invalid)
            # A handled tool error must leave the protocol session usable.
            assert {tool.name for tool in (await client.list_tools()).tools} == TOOLS
    logged = error_log.read_text(encoding="utf-8")
    assert PRIVATE not in logged
    assert "Traceback" not in logged
    assert not private_state.exists()


@pytest.mark.asyncio
async def test_sdk_discovery_publishes_typed_upload_and_pagination_contract(tmp_path: Path) -> None:
    agent, _ = fixture_agent(tmp_path)
    async with Client(build_server(agent)) as client:
        tools = {tool.name: tool for tool in (await client.list_tools()).tools}
        assert set(tools) == TOOLS
        save = tools["save_checkpoint"].input_schema
        assert set(save["required"]) == {
            "project_id",
            "payload",
            "idempotency_key",
            "approved_for_upload",
        }
        assert save["properties"]["approved_for_upload"]["const"] is True
        assert save["properties"]["idempotency_key"]["format"] == "uuid"
        assert save["$defs"]["EvidenceSource"]["additionalProperties"] is False
        assert save["$defs"]["CheckpointInput"]["properties"]["sources"]["minItems"] == 1
        for name in ("list_projects", "search_project_evidence"):
            schema = tools[name].input_schema
            assert schema["properties"]["limit"]["minimum"] == 1
            assert schema["properties"]["limit"]["maximum"] == 100
            assert "cursor" in schema["properties"]
        assert "query" not in tools["search_project_evidence"].input_schema["required"]
        assert "status" not in tools["search_project_evidence"].input_schema["properties"]
        for name, tool in tools.items():
            assert tool.output_schema is not None
            assert tool.annotations is not None
            assert tool.annotations.read_only_hint == (
                name
                not in {
                    "register_project",
                    "save_checkpoint",
                    "replay_checkpoint",
                }
            )


@pytest.mark.asyncio
async def test_sdk_save_lost_receipt_replay_and_confirmed_filter(tmp_path: Path) -> None:
    agent, backend = fixture_agent(tmp_path)
    backend.lose_response = True
    key = str(uuid4())
    arguments = {
        "project_id": str(backend.project),
        "payload": payload().model_dump(mode="json"),
        "idempotency_key": key,
        "approved_for_upload": True,
    }
    async with Client(build_server(agent)) as client:
        await client.list_tools()
        pending = output(await client.call_tool("save_checkpoint", arguments), expected_error=True)
        assert pending["state"] == "pending"
        assert pending["error_code"] == "API_UNAVAILABLE"
        assert PRIVATE not in json.dumps(pending)
        listed = output(await client.call_tool("list_pending_checkpoints", {}))
        assert listed["items"][0]["packet_id"] == pending["packet_id"]
    # A different official client/server instance recovers from protected state.
    restarted = ProjectAgent(agent.config, backend.store, httpx.MockTransport(backend))
    async with Client(build_server(restarted)) as client:
        await client.list_tools()
        replay = output(
            await client.call_tool("replay_checkpoint", {"packet_id": pending["packet_id"]})
        )
        assert replay["state"] == "accepted"
        original_id = str(next(iter(backend.records.values())).id)
        assert replay["record"]["id"] == original_id
        again = output(await client.call_tool("save_checkpoint", arguments))
        assert again["record"]["id"] == original_id
        assert len(backend.records) == 1
        assert {request.headers["idempotency-key"] for request in backend.posts} == {key}
        post_count = len(backend.posts)
        conflicting = {
            **arguments,
            "payload": {
                **payload().model_dump(mode="json"),
                "title": "Changed content for the same key",
            },
        }
        assert "LOCAL_INPUT_CONFLICT" in safe_error(
            await client.call_tool("save_checkpoint", conflicting)
        )
        assert len(backend.posts) == post_count
        assert output(await client.call_tool("list_pending_checkpoints", {}))["items"] == []
        project_arguments = {"project_id": str(backend.project)}
        assert (
            output(await client.call_tool("search_project_evidence", project_arguments))["items"]
            == []
        )
        current = backend.records[key]
        backend.records[key] = current.model_copy(update={"status": RecordStatus.CONFIRMED})
        found = output(
            await client.call_tool(
                "search_project_evidence",
                {
                    **project_arguments,
                    "query": "Retry",
                    "cursor": "synthetic-cursor",
                    "limit": 1,
                },
            )
        )
        assert found["items"][0]["id"] == original_id
        search = backend.requests[-1]
        assert dict(search.url.params) == {
            "q": "Retry",
            "status": "confirmed",
            "cursor": "synthetic-cursor",
            "limit": "1",
        }
        context = output(await client.call_tool("get_project_context", project_arguments))
        assert context["confirmed_records"]["items"][0]["id"] == original_id
        backend.records[key] = current.model_copy(update={"status": RecordStatus.WITHDRAWN})
        evidence = output(
            await client.call_tool(
                "get_evidence",
                {
                    **project_arguments,
                    "checkpoint_id": original_id,
                },
            )
        )
        assert evidence["status"] == "withdrawn"
        assert (
            output(await client.call_tool("search_project_evidence", project_arguments))["items"]
            == []
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "state", "code"),
    [
        (400, "rejected", "API_REJECTED"),
        (401, "pending", "LOGIN_REQUIRED"),
        (503, "pending", "API_UNAVAILABLE"),
    ],
)
async def test_sdk_failed_save_and_replay_preserve_recovery_fields_with_error_flag(
    tmp_path: Path,
    status: int,
    state: str,
    code: str,
) -> None:
    agent, backend = fixture_agent(tmp_path)

    def refusing_api(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/auth/me":
            return backend(request)
        backend.posts.append(request)
        return httpx.Response(status, json={"private": PRIVATE})

    gateway = ProjectAgent(agent.config, backend.store, httpx.MockTransport(refusing_api))
    key = str(uuid4())
    async with Client(build_server(gateway)) as client:
        await client.list_tools()
        result = await client.call_tool(
            "save_checkpoint",
            {
                "project_id": str(backend.project),
                "payload": payload().model_dump(mode="json"),
                "idempotency_key": key,
                "approved_for_upload": True,
            },
        )
        safe_error(result)
        failed = output(result, expected_error=True)
        assert failed["state"] == state
        assert failed["error_code"] == code
        assert failed["record"] is None
        assert failed["message"]
        packet_id = UUID(failed["packet_id"])
        assert backend.store.read(
            f"packet-{packet_id}.bin", PendingCheckpoint
        ).idempotency_key == UUID(key)
        pending = output(await client.call_tool("list_pending_checkpoints", {}))
        assert pending["items"][0]["packet_id"] == str(packet_id)
        replay = await client.call_tool("replay_checkpoint", {"packet_id": str(packet_id)})
        safe_error(replay)
        retried = output(replay, expected_error=True)
        assert retried == failed
        assert len(backend.posts) == 2
        assert {request.headers["idempotency-key"] for request in backend.posts} == {key}


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["approval", "uuid", "quote", "limit"])
async def test_sdk_invalid_input_never_reaches_transport_or_leaks_input(
    tmp_path: Path,
    change: str,
) -> None:
    agent, backend = fixture_agent(tmp_path)
    arguments = {
        "project_id": str(backend.project),
        "payload": payload().model_dump(mode="json"),
        "idempotency_key": str(uuid4()),
        "approved_for_upload": True,
    }
    name = "save_checkpoint"
    if change == "approval":
        arguments["approved_for_upload"] = False
    elif change == "uuid":
        arguments["project_id"] = PRIVATE
    elif change == "quote":
        arguments["payload"]["sources"][0]["quote"] = PRIVATE
    else:
        name, arguments = "list_projects", {"limit": 0}
    async with Client(build_server(agent)) as client:
        await client.list_tools()
        assert "INVALID_TOOL_INPUT" in safe_error(await client.call_tool(name, arguments))
    assert backend.requests == []
    assert list(backend.store.root.glob("packet-*.bin")) == []


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [401, 500, "malformed", "unexpected"])
async def test_sdk_api_and_unexpected_errors_do_not_expose_private_details(
    tmp_path: Path,
    failure: int | str,
) -> None:
    agent, _ = fixture_agent(tmp_path)

    def failing_transport(request: httpx.Request) -> httpx.Response:
        if failure == "unexpected":
            raise RuntimeError(PRIVATE)
        if failure == "malformed":
            return httpx.Response(200, json={"private": PRIVATE})
        return httpx.Response(failure, json={"private": PRIVATE})

    isolated = ProjectAgent(agent.config, agent.store, httpx.MockTransport(failing_transport))
    async with Client(build_server(isolated)) as client:
        await client.list_tools()
        safe_error(await client.call_tool("list_projects", {}))
