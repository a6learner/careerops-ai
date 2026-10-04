import logging
import math
from datetime import datetime
from typing import Protocol
from uuid import UUID

from careerops.domain.embeddings import (
    EmbeddingOutput,
    EmbeddingSpace,
    render_query_embedding_input,
)
from careerops.domain.errors import EmbeddingProviderError
from careerops.domain.evidence_retrieval import (
    DEFAULT_CANDIDATE_LIMIT,
    EvidenceCandidate,
    RequirementCandidateSet,
    retrieve_evidence_candidates,
)
from careerops.domain.experiences import ExperienceRecord
from careerops.domain.parse_runs import JobRequirementRecord
from careerops.domain.ranking import RankedItem, weighted_rrf
from careerops.services.embedding_execution import EmbeddingProvider

logger = logging.getLogger(__name__)

VECTOR_THRESHOLD = 0.65
LEXICAL_WEIGHT = 0.5
VECTOR_WEIGHT = 0.5
RRF_K = 60


class EvidenceVectorStore(Protocol):
    async def exact_cosine_scores(
        self,
        *,
        user_id: UUID,
        experience_ids: tuple[UUID, ...],
        query_vector: tuple[float, ...],
        space: EmbeddingSpace,
        available_before: datetime,
    ) -> dict[UUID, float]: ...


class EvidenceRetriever(Protocol):
    async def retrieve(
        self,
        *,
        user_id: UUID,
        requirements: tuple[JobRequirementRecord, ...],
        experiences: tuple[ExperienceRecord, ...],
        available_before: datetime,
    ) -> tuple[RequirementCandidateSet, ...]: ...


class LexicalEvidenceRetriever:
    async def retrieve(
        self,
        *,
        user_id: UUID,
        requirements: tuple[JobRequirementRecord, ...],
        experiences: tuple[ExperienceRecord, ...],
        available_before: datetime,
    ) -> tuple[RequirementCandidateSet, ...]:
        return retrieve_evidence_candidates(requirements, experiences)


class HybridEvidenceRetriever:
    def __init__(
        self,
        vectors: EvidenceVectorStore,
        provider: EmbeddingProvider,
        space: EmbeddingSpace,
    ) -> None:
        if provider.model_name != space.model_name:
            raise ValueError("Embedding provider and space model must match.")
        self._vectors = vectors
        self._provider = provider
        self._space = space

    async def retrieve(
        self,
        *,
        user_id: UUID,
        requirements: tuple[JobRequirementRecord, ...],
        experiences: tuple[ExperienceRecord, ...],
        available_before: datetime,
    ) -> tuple[RequirementCandidateSet, ...]:
        lexical_sets = retrieve_evidence_candidates(requirements, experiences)
        experience_ids = tuple(experience.id for experience in experiences)
        fused: list[RequirementCandidateSet] = []
        for lexical_set in lexical_sets:
            try:
                output = await self._provider.embed(
                    render_query_embedding_input(
                        lexical_set.requirement.text,
                        self._space.query_input_version,
                    )
                )
                _validate_query_embedding(output, self._space)
                vector_scores = await self._vectors.exact_cosine_scores(
                    user_id=user_id,
                    experience_ids=experience_ids,
                    query_vector=output.vector,
                    space=self._space,
                    available_before=available_before,
                )
            except EmbeddingProviderError as exc:
                logger.warning(
                    "Hybrid retrieval fell back to lexical requirement_id=%s reason=%s",
                    lexical_set.requirement.id,
                    exc.reason.value,
                )
                fused.append(lexical_set)
                continue

            if not vector_scores:
                logger.info(
                    "Hybrid retrieval used lexical requirement_id=%s vector_eligible=0 total=%s",
                    lexical_set.requirement.id,
                    len(experiences),
                )
                fused.append(lexical_set)
                continue

            fused.append(
                RequirementCandidateSet(
                    requirement=lexical_set.requirement,
                    candidates=fuse_rankings(
                        lexical_set.candidates,
                        vector_scores,
                        experiences,
                    ),
                )
            )
            logger.info(
                "Hybrid retrieval used weighted RRF requirement_id=%s vector_eligible=%s total=%s",
                lexical_set.requirement.id,
                len(vector_scores),
                len(experiences),
            )
        return tuple(fused)


def fuse_rankings(
    lexical: tuple[EvidenceCandidate, ...],
    vector_scores: dict[UUID, float],
    experiences: tuple[ExperienceRecord, ...],
) -> tuple[EvidenceCandidate, ...]:
    vector = sorted(
        (
            (experience_id, score)
            for experience_id, score in vector_scores.items()
            if score >= VECTOR_THRESHOLD
        ),
        key=lambda item: (-item[1], str(item[0])),
    )[:DEFAULT_CANDIDATE_LIMIT]
    experiences_by_id = {experience.id: experience for experience in experiences}
    ranked = weighted_rrf(
        tuple(
            RankedItem(item.experience.id, rank, item.score)
            for rank, item in enumerate(lexical, 1)
        ),
        tuple(
            RankedItem(experience_id, rank, score)
            for rank, (experience_id, score) in enumerate(vector, 1)
        ),
        lexical_weight=LEXICAL_WEIGHT,
        vector_weight=VECTOR_WEIGHT,
        k=RRF_K,
        limit=DEFAULT_CANDIDATE_LIMIT,
    )
    return tuple(
        EvidenceCandidate(
            experience=experiences_by_id[item.experience_id],
            score=item.score,
        )
        for item in ranked
    )


def _validate_query_embedding(output: EmbeddingOutput, space: EmbeddingSpace) -> None:
    if (
        output.model_name != space.model_name
        or len(output.vector) != space.dimensions
        or any(not math.isfinite(value) for value in output.vector)
        or not any(value != 0 for value in output.vector)
    ):
        raise EmbeddingProviderError()
