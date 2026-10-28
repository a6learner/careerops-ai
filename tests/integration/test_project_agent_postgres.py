import os
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from careerops.agent.client import login
from careerops.agent.contracts import AgentConfig, RecordQuery
from careerops.agent.gateway import ProjectAgent
from careerops.agent.storage import ProtectedStore
from careerops.db.models import User
from careerops.domain.project_records import CheckpointInput, EvidenceSource, ProjectInput
from careerops.main import create_app

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("CAREEROPS_RUN_INTEGRATION") != "1" or os.name != "nt",
        reason="requires isolated PostgreSQL and Windows DPAPI",
    ),
]


@pytest.mark.asyncio
async def test_local_client_uses_real_api_and_protected_state(tmp_path) -> None:
    app = create_app()
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        email = f"agent-acceptance-{uuid4()}@example.com"
        password = "Synthetic-agent-test-password"
        async with AsyncClient(transport=transport, base_url="http://testserver") as http:
            registered = await http.post(
                "/api/v1/auth/register",
                json={
                    "email": email,
                    "password": password,
                },
            )
        assert registered.status_code == 201
        config = AgentConfig(api_url="http://127.0.0.1:8000", state_dir=tmp_path)
        credentials = await login(config, email, password, transport)
        store = ProtectedStore(tmp_path)
        store.save_credentials(credentials)
        try:
            assert (
                credentials.access_token.get_secret_value().encode()
                not in (tmp_path / "credentials.bin").read_bytes()
            )
            agent = ProjectAgent(config, store, transport)
            project = await agent.register_project(
                ProjectInput(
                    name="Protected project journal",
                    goal="Explain real work later",
                ),
                uuid4(),
            )
            payload = CheckpointInput(
                title="Record an implementation stage",
                objective="Preserve selected evidence",
                changes="Persist a source-grounded draft",
                host="synthetic-local-client",
                sources=(
                    EvidenceSource(
                        kind="user_note",
                        locator="notes/stage.md",
                        content="Retain the original key on retries.",
                        quote="original key",
                    ),
                ),
            )
            result = await agent.save_checkpoint(project.id, payload, uuid4(), True)
            assert result.state == "accepted" and result.record is not None
            assert result.record.status == "draft"
            assert agent.list_pending_checkpoints().items == []
            assert (await agent.search_project_evidence(project.id, RecordQuery())).items == []
            headers = {
                "Authorization": f"Bearer {credentials.access_token.get_secret_value()}",
                "If-Match": "1",
            }
            async with AsyncClient(transport=transport, base_url="http://testserver") as http:
                review = await http.patch(
                    f"/api/v1/projects/{project.id}/checkpoints/{result.record.id}/review",
                    headers=headers,
                    json={
                        "status": "confirmed",
                        "contribution_note": "I reviewed the retry contract.",
                    },
                )
                assert review.status_code == 200
            fresh_agent = ProjectAgent(config, ProtectedStore(tmp_path), transport)
            found = await fresh_agent.search_project_evidence(
                project.id, RecordQuery(query="original")
            )
            assert len(found.items) == 1 and found.items[0].status == "confirmed"
            replay = await fresh_agent.replay_checkpoint(result.packet_id)
            assert replay.record is not None and replay.record.id == result.record.id
            assert replay.record.status == "confirmed"
        finally:
            async with app.state.session_factory() as session:
                await session.execute(delete(User).where(User.id == credentials.user_id))
                await session.commit()
