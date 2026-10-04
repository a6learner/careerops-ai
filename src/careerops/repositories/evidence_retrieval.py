from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from careerops.db.models import Experience
from careerops.domain.embeddings import EmbeddingSpace


class EvidenceVectorRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def exact_cosine_scores(
        self,
        *,
        user_id: UUID,
        experience_ids: tuple[UUID, ...],
        query_vector: tuple[float, ...],
        space: EmbeddingSpace,
        available_before: datetime,
    ) -> dict[UUID, float]:
        if not experience_ids:
            return {}
        cosine_distance = Experience.embedding.cosine_distance(list(query_vector))
        result = await self._session.execute(
            select(Experience.id, cosine_distance.label("cosine_distance")).where(
                Experience.id.in_(experience_ids),
                Experience.user_id == user_id,
                Experience.deleted_at.is_(None),
                Experience.embedding.is_not(None),
                Experience.embedding_content_hash == Experience.content_hash,
                Experience.embedding_model == space.model_name,
                Experience.embedding_input_version == space.document_input_version,
                Experience.embedded_at.is_not(None),
                Experience.embedded_at <= available_before,
            )
        )
        return {
            row.id: round(1.0 - float(row.cosine_distance), 12)
            for row in result.all()
        }
