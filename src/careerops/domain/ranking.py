import math
from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class RankedItem:
    experience_id: UUID
    rank: int
    secondary_score: float


@dataclass(frozen=True)
class WeightedRrfResult:
    experience_id: UUID
    score: float
    vector_score: float | None
    lexical_score: float | None


def weighted_rrf(
    lexical: tuple[RankedItem, ...],
    vector: tuple[RankedItem, ...],
    *,
    lexical_weight: float,
    vector_weight: float,
    k: int,
    limit: int,
) -> tuple[WeightedRrfResult, ...]:
    lexical_by_id = {item.experience_id: item for item in lexical}
    vector_by_id = {item.experience_id: item for item in vector}
    results: list[WeightedRrfResult] = []
    for experience_id in set(lexical_by_id) | set(vector_by_id):
        lexical_item = lexical_by_id.get(experience_id)
        vector_item = vector_by_id.get(experience_id)
        score = 0.0
        if lexical_item is not None:
            score += lexical_weight / (k + lexical_item.rank)
        if vector_item is not None:
            score += vector_weight / (k + vector_item.rank)
        results.append(
            WeightedRrfResult(
                experience_id=experience_id,
                score=round(score, 12),
                vector_score=(vector_item.secondary_score if vector_item is not None else None),
                lexical_score=(lexical_item.secondary_score if lexical_item is not None else None),
            )
        )
    results.sort(
        key=lambda item: (
            -item.score,
            -(item.vector_score if item.vector_score is not None else -math.inf),
            -(item.lexical_score if item.lexical_score is not None else -1.0),
            str(item.experience_id),
        )
    )
    return tuple(results[:limit])
