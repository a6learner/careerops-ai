import asyncio
import os
import socket
import subprocess
import sys
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncEngine

from careerops.agent.client import login
from careerops.agent.contracts import AgentConfig, PendingPage, SubmissionResult
from careerops.agent.storage import ProtectedStore
from careerops.core.config import Settings
from careerops.db.models import User
from careerops.db.session import create_session_factory
from careerops.domain.project_records import (
    CheckpointInput,
    CheckpointPage,
    CheckpointRecord,
    EvidenceSource,
    ProjectPage,
    ProjectRecord,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("CAREEROPS_RUN_INTEGRATION") != "1" or os.name != "nt",
        reason="requires an isolated PostgreSQL database and Windows DPAPI",
    ),
]


def available_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


async def await_api(process: subprocess.Popen[bytes], origin: str) -> None:
    async with httpx.AsyncClient(timeout=1, trust_env=False) as client:
        for _ in range(100):
            if process.poll() is not None:
                pytest.fail("Owned test API exited before becoming ready; inspect its local log.")
            try:
                response = await client.get(origin + "/healthz")
                if response.status_code == 200:
                    return
            except httpx.TransportError:
                pass
            await asyncio.sleep(0.1)
    pytest.fail("Owned test API did not become ready in time.")


async def cli(
    root: Path,
    environment: dict[str, str],
    *arguments: str,
    secrets: tuple[str, ...] = (),
) -> str:
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "careerops.agent",
        *arguments,
        cwd=root,
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        output, errors = await asyncio.wait_for(process.communicate(), timeout=20)
    except TimeoutError:
        process.kill()
        await process.wait()
        pytest.fail("Owned CLI subprocess timed out.")
    stdout, stderr = output.decode("utf-8"), errors.decode("utf-8")
    if any(secret in stdout or secret in stderr for secret in secrets):
        pytest.fail("CLI leaked synthetic credential material.")
    if process.returncode != 0:
        pytest.fail(f"CLI exited with {process.returncode}: {stderr}")
    return stdout


@pytest.mark.asyncio
async def test_cli_cross_process_records_review_search_and_replay(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    origin = f"http://127.0.0.1:{available_port()}"
    state = tmp_path / "protected-state"
    environment = dict(os.environ)
    environment.update(
        {
            "CAREEROPS_ENV": "local",
            "CAREEROPS_DATABASE_URL": Settings().database_url,
            "CAREEROPS_LLM_PROVIDER": "fake",
            "CAREEROPS_EMBEDDING_PROVIDER": "fake",
            "CAREEROPS_EVIDENCE_MATCHER_PROVIDER": "fake",
            "CAREEROPS_RUN_EMBEDDING_INTEGRATION": "0",
            "CAREEROPS_RUN_REAL_MATCHER_WORKER": "0",
            "CAREEROPS_JWT_SECRET": "synthetic-cli-acceptance-secret-32-bytes-minimum",
            "CAREEROPS_AGENT_API_URL": origin,
            "CAREEROPS_AGENT_STATE_DIR": str(state),
            "PYTHONIOENCODING": "utf-8",
        }
    )
    owner: UUID | None = None
    with (tmp_path / "owned-api.log").open("wb") as log:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "careerops.main:create_app",
                "--factory",
                "--host",
                "127.0.0.1",
                "--port",
                str(httpx.URL(origin).port),
            ],
            cwd=root,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            await await_api(process, origin)
            email = f"cli-agent-{uuid4()}@example.com"
            password = "Synthetic-cli-agent-password"
            async with httpx.AsyncClient(base_url=origin, timeout=5, trust_env=False) as client:
                registered = await client.post(
                    "/api/v1/auth/register",
                    json={
                        "email": email,
                        "password": password,
                    },
                )
                assert registered.status_code == 201
                owner = UUID(registered.json()["id"])
            config = AgentConfig(api_url=origin, state_dir=state)
            credentials = await login(config, email, password)
            assert credentials.user_id == owner
            ProtectedStore(state).save_credentials(credentials)
            token = credentials.access_token.get_secret_value()
            assert token.encode() not in (state / "credentials.bin").read_bytes()
            hidden = (password, token)
            project_key = str(uuid4())
            register_arguments = (
                "register",
                "--name",
                "Cross-process evidence project",
                "--goal",
                "Recall development decisions later",
                "--key",
                project_key,
            )
            project = ProjectRecord.model_validate_json(
                await cli(
                    root,
                    environment,
                    *register_arguments,
                    secrets=hidden,
                )
            )
            project_replay = ProjectRecord.model_validate_json(
                await cli(
                    root,
                    environment,
                    *register_arguments,
                    secrets=hidden,
                )
            )
            assert project_replay.id == project.id
            projects = ProjectPage.model_validate_json(
                await cli(
                    root,
                    environment,
                    "projects",
                    secrets=hidden,
                )
            )
            assert [item.id for item in projects.items] == [project.id]
            second_project = ProjectRecord.model_validate_json(
                await cli(
                    root,
                    environment,
                    "register",
                    "--name",
                    "Second cross-process project",
                    "--goal",
                    "Exercise stable project pagination",
                    "--key",
                    str(uuid4()),
                    secrets=hidden,
                )
            )
            first_page = ProjectPage.model_validate_json(
                await cli(root, environment, "projects", "--limit", "1", secrets=hidden)
            )
            assert len(first_page.items) == 1 and first_page.next_cursor is not None
            second_page = ProjectPage.model_validate_json(
                await cli(
                    root,
                    environment,
                    "projects",
                    "--limit",
                    "1",
                    "--cursor",
                    first_page.next_cursor,
                    secrets=hidden,
                )
            )
            assert len(second_page.items) == 1 and second_page.next_cursor is None
            assert first_page.items[0].id != second_page.items[0].id
            assert {first_page.items[0].id, second_page.items[0].id} == {
                project.id,
                second_project.id,
            }
            packet = CheckpointInput(
                title="Preserve retry behavior",
                objective="Recover an accepted write without creating duplicates",
                changes="Use a durable packet and the original idempotency key",
                host="synthetic-cli-acceptance",
                sources=(
                    EvidenceSource(
                        kind="user_note",
                        locator="notes/retry-contract.md",
                        content="Retain the original idempotency key after a lost response.",
                        quote="original idempotency key",
                    ),
                ),
            )
            packet_path = tmp_path / "selected-checkpoint.json"
            packet_path.write_text(packet.model_dump_json(), encoding="utf-8")
            submitted = SubmissionResult.model_validate_json(
                await cli(
                    root,
                    environment,
                    "submit",
                    "--project",
                    str(project.id),
                    "--key",
                    str(uuid4()),
                    "--packet",
                    str(packet_path),
                    secrets=hidden,
                )
            )
            assert submitted.state == "accepted" and submitted.record is not None
            assert submitted.record.status == "draft"
            record_id = submitted.record.id
            before_review = CheckpointPage.model_validate_json(
                await cli(
                    root,
                    environment,
                    "search",
                    "--project",
                    str(project.id),
                    "--query",
                    "original",
                    secrets=hidden,
                )
            )
            assert before_review.items == []
            async with httpx.AsyncClient(base_url=origin, timeout=5, trust_env=False) as client:
                review = await client.patch(
                    f"/api/v1/projects/{project.id}/checkpoints/{record_id}/review",
                    headers={"Authorization": f"Bearer {token}", "If-Match": "1"},
                    json={
                        "status": "confirmed",
                        "contribution_note": "I reviewed the retry contract.",
                    },
                )
                assert review.status_code == 200
            found = CheckpointPage.model_validate_json(
                await cli(
                    root,
                    environment,
                    "search",
                    "--project",
                    str(project.id),
                    "--query",
                    "original",
                    secrets=hidden,
                )
            )
            assert len(found.items) == 1 and found.items[0].id == record_id
            assert found.items[0].status == "confirmed"
            unfiltered = CheckpointPage.model_validate_json(
                await cli(
                    root,
                    environment,
                    "search",
                    "--project",
                    str(project.id),
                    "--limit",
                    "1",
                    secrets=hidden,
                )
            )
            assert [item.id for item in unfiltered.items] == [record_id]
            assert unfiltered.items[0].status == "confirmed"
            assert unfiltered.next_cursor is None
            detailed = CheckpointRecord.model_validate_json(
                await cli(
                    root,
                    environment,
                    "get",
                    "--project",
                    str(project.id),
                    "--record",
                    str(record_id),
                    secrets=hidden,
                )
            )
            assert detailed.payload.sources[0].quote == "original idempotency key"
            replayed = SubmissionResult.model_validate_json(
                await cli(
                    root,
                    environment,
                    "replay",
                    str(submitted.packet_id),
                    secrets=hidden,
                )
            )
            assert replayed.state == "accepted" and replayed.record is not None
            assert replayed.record.id == record_id and replayed.record.status == "confirmed"
            pending = PendingPage.model_validate_json(
                await cli(
                    root,
                    environment,
                    "pending",
                    secrets=hidden,
                )
            )
            assert pending.items == []
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            if owner is not None:
                factory = create_session_factory(environment["CAREEROPS_DATABASE_URL"])
                try:
                    async with factory() as session:
                        await session.execute(delete(User).where(User.id == owner))
                        await session.commit()
                finally:
                    engine = factory.kw["bind"]
                    assert isinstance(engine, AsyncEngine)
                    await engine.dispose()
