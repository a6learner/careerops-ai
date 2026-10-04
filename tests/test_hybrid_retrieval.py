from datetime import UTC, datetime
from uuid import UUID

import pytest

from careerops.domain.embeddings import (
    EMBEDDING_DIMENSIONS,
    FAKE_EMBEDDING_SPACE,
    EmbeddingOutput,
)
from careerops.domain.errors import EmbeddingProviderError
from careerops.domain.evidence_retrieval import EvidenceCandidate
from careerops.domain.experiences import ExperienceKind, ExperienceRecord
from careerops.domain.parse_runs import JobRequirementRecord, RequirementCategory
from careerops.services.hybrid_retrieval import HybridEvidenceRetriever, fuse_rankings


class VectorStore:
    def __init__(self, scores: dict[UUID, float]) -> None:
        self.scores = scores

    async def exact_cosine_scores(self, **kwargs: object) -> dict[UUID, float]:
        return self.scores


class QueryProvider:
    @property
    def model_name(self) -> str:
        return FAKE_EMBEDDING_SPACE.model_name

    async def embed(self, input_text: str) -> EmbeddingOutput:
        return EmbeddingOutput(self.model_name, (1.0,) * EMBEDDING_DIMENSIONS)


class FailingQueryProvider(QueryProvider):
    async def embed(self, input_text: str) -> EmbeddingOutput:
        raise EmbeddingProviderError()


@pytest.mark.asyncio
async def test_partial_vectors_are_fused_with_lexical_candidates() -> None:
    first = make_experience("00000000-0000-0000-0000-000000000001", ("Python",))
    second = make_experience("00000000-0000-0000-0000-000000000002", ("React",))
    requirement = make_requirement()
    retriever = HybridEvidenceRetriever(
        vectors=VectorStore({second.id: 0.9}),
        provider=QueryProvider(),
        space=FAKE_EMBEDDING_SPACE,
    )

    result = await retriever.retrieve(
        user_id=first.user_id,
        requirements=(requirement,),
        experiences=(first, second),
        available_before=datetime.now(UTC),
    )

    assert [item.experience.id for item in result[0].candidates] == [second.id, first.id]


@pytest.mark.asyncio
async def test_provider_failure_falls_back_to_lexical() -> None:
    first = make_experience("00000000-0000-0000-0000-000000000001", ("Python",))
    second = make_experience("00000000-0000-0000-0000-000000000002", ("React",))
    retriever = HybridEvidenceRetriever(
        vectors=VectorStore({second.id: 0.9}),
        provider=FailingQueryProvider(),
        space=FAKE_EMBEDDING_SPACE,
    )

    result = await retriever.retrieve(
        user_id=first.user_id,
        requirements=(make_requirement(),),
        experiences=(first, second),
        available_before=datetime.now(UTC),
    )

    assert [item.experience.id for item in result[0].candidates] == [first.id]


def test_rrf_ties_use_vector_then_lexical_then_uuid() -> None:
    first = make_experience("00000000-0000-0000-0000-000000000001", ("Python",))
    second = make_experience("00000000-0000-0000-0000-000000000002", ("Python",))
    result = fuse_rankings(
        (EvidenceCandidate(first, 100.0), EvidenceCandidate(second, 100.0)),
        {first.id: 0.8, second.id: 0.9},
        (first, second),
    )

    assert [item.experience.id for item in result] == [second.id, first.id]


def make_requirement() -> JobRequirementRecord:
    return JobRequirementRecord(
        id=UUID("10000000-0000-0000-0000-000000000001"),
        job_id=UUID("20000000-0000-0000-0000-000000000001"),
        parse_run_id=UUID("30000000-0000-0000-0000-000000000001"),
        category=RequirementCategory.MUST_HAVE,
        text="Python backend experience",
        skill_normalized="Python",
        source_span_start=0,
        source_span_end=25,
    )


def make_experience(experience_id: str, skills: tuple[str, ...]) -> ExperienceRecord:
    now = datetime.now(UTC)
    description = "Built backend services." if "Python" in skills else "Built frontend interfaces."
    return ExperienceRecord(
        id=UUID(experience_id),
        user_id=UUID("40000000-0000-0000-0000-000000000001"),
        title="Project",
        kind=ExperienceKind.PROJECT,
        description=description,
        skills=skills,
        outcome=None,
        version=1,
        content_hash="a" * 64,
        created_at=now,
        updated_at=now,
    )
