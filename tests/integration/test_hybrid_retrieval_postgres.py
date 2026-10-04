import os
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from careerops.core.config import Settings
from careerops.db.models import Experience, User
from careerops.db.session import create_session_factory
from careerops.domain.embeddings import FAKE_EMBEDDING_SPACE
from careerops.repositories.evidence_retrieval import EvidenceVectorRepository

pytestmark = pytest.mark.integration


@pytest.mark.skipif(
    os.getenv("CAREEROPS_RUN_INTEGRATION") != "1",
    reason="requires local PostgreSQL container",
)
@pytest.mark.asyncio
async def test_exact_vector_query_fences_owner_provenance_and_snapshot_time() -> None:
    session_factory = create_session_factory(Settings().database_url)
    owner_id = uuid4()
    other_id = uuid4()
    now = datetime.now(UTC)
    valid_id = uuid4()
    future_id = uuid4()
    wrong_model_id = uuid4()
    wrong_input_id = uuid4()
    deleted_id = uuid4()
    other_user_id = uuid4()
    vector = [1.0] * 1536

    async with session_factory() as setup:
        setup.add_all(
            [
                User(id=owner_id, email=f"vector-owner-{uuid4()}@example.com", password_hash="x"),
                User(id=other_id, email=f"vector-other-{uuid4()}@example.com", password_hash="x"),
            ]
        )
        await setup.flush()
        setup.add_all(
            [
                make_experience(valid_id, owner_id, vector, now - timedelta(seconds=1)),
                make_experience(future_id, owner_id, vector, now + timedelta(seconds=1)),
                make_experience(
                    wrong_model_id,
                    owner_id,
                    vector,
                    now - timedelta(seconds=1),
                    model="other-model",
                ),
                make_experience(other_user_id, other_id, vector, now - timedelta(seconds=1)),
                make_experience(
                    wrong_input_id,
                    owner_id,
                    vector,
                    now - timedelta(seconds=1),
                    input_version="other-input-version",
                ),
                make_experience(
                    deleted_id,
                    owner_id,
                    vector,
                    now - timedelta(seconds=1),
                    deleted_at=now - timedelta(seconds=1),
                ),
            ]
        )
        await setup.commit()

    async with session_factory() as session:
        scores = await EvidenceVectorRepository(session).exact_cosine_scores(
            user_id=owner_id,
            experience_ids=(
                valid_id,
                future_id,
                wrong_model_id,
                wrong_input_id,
                deleted_id,
                other_user_id,
            ),
            query_vector=tuple(vector),
            space=FAKE_EMBEDDING_SPACE,
            available_before=now,
        )
        assert scores == {valid_id: 1.0}

        owner = await session.get(User, owner_id)
        other = await session.get(User, other_id)
        assert owner is not None and other is not None
        await session.delete(owner)
        await session.delete(other)
        await session.commit()
    await session_factory.kw["bind"].dispose()


def make_experience(
    experience_id: UUID,
    user_id: UUID,
    vector: list[float],
    embedded_at: datetime,
    *,
    model: str = FAKE_EMBEDDING_SPACE.model_name,
    input_version: str = FAKE_EMBEDDING_SPACE.document_input_version,
    deleted_at: datetime | None = None,
) -> Experience:
    return Experience(
        id=experience_id,
        user_id=user_id,
        title="Vector fixture",
        kind="project",
        description="Deterministic vector fixture.",
        skills=["Python"],
        version=1,
        content_hash="a" * 64,
        embedding=vector,
        embedding_content_hash="a" * 64,
        embedding_model=model,
        embedding_input_version=input_version,
        embedded_at=embedded_at,
        deleted_at=deleted_at,
    )
