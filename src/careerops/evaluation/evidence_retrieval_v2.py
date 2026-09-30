from __future__ import annotations

import re
from collections import Counter
from datetime import datetime
from enum import StrEnum
from hashlib import sha256
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from careerops.domain.evidence_retrieval import (
    DEFAULT_CANDIDATE_LIMIT,
    retrieve_evidence_candidates,
)
from careerops.domain.experiences import ExperienceRecord
from careerops.evaluation.evidence_retrieval import (
    RETRIEVER_VERSION,
    RankedExperience,
    RetrievalEvalExperience,
    RetrievalEvalRequirement,
    mean,
    required,
    to_experience_record,
    to_requirement_record,
)


class RetrievalSplit(StrEnum):
    DEVELOPMENT = "development"
    HOLDOUT = "holdout"


class SupportLevel(StrEnum):
    FULL = "full"
    PARTIAL = "partial"


class ReviewStatus(StrEnum):
    PENDING_AUTHOR_REVIEW = "pending_author_review"
    APPROVED_FROZEN = "approved_frozen"


class DifficultyTag(StrEnum):
    EXACT_SKILL = "exact_skill"
    LEXICAL = "lexical"
    PARAPHRASE = "paraphrase"
    HARD_NEGATIVE = "hard_negative"
    MULTI_RELEVANT = "multi_relevant"
    COMPOSITE = "composite"
    ZH_ZH = "zh_zh"
    ZH_EN = "zh_en"
    EN_ZH = "en_zh"


class RetrievalProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    experiences: list[RetrievalEvalExperience] = Field(min_length=1)


class RetrievalV2Corpus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    version: int = Field(ge=2)
    profiles: list[RetrievalProfile] = Field(min_length=1)


class RetrievalRelevanceLabel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    experience_id: UUID
    support_level: SupportLevel
    supporting_quote: str = Field(min_length=1)
    rationale: str = Field(min_length=1)


class RetrievalV2Query(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query_id: str = Field(min_length=1)
    profile_id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    requirement: RetrievalEvalRequirement
    labels: list[RetrievalRelevanceLabel]
    hard_negative_experience_ids: list[UUID]
    hard_negative_rationale: str | None = None
    negative_rationale: str | None
    tags: list[DifficultyTag] = Field(min_length=1)


class RetrievalV2QuerySet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    version: int = Field(ge=2)
    split: RetrievalSplit
    queries: list[RetrievalV2Query] = Field(min_length=1)


class RetrievalV2ReviewManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    version: int = Field(ge=2)
    status: ReviewStatus
    reviewer: str | None
    reviewed_at: datetime | None
    corpus_sha256: str = Field(min_length=64, max_length=64)
    development_queries_sha256: str = Field(min_length=64, max_length=64)
    holdout_queries_sha256: str = Field(min_length=64, max_length=64)
    notes: list[str]


class RetrievalV2QueryResult(BaseModel):
    query_id: str
    profile_id: str
    description: str
    tags: list[DifficultyTag]
    relevant_experience_ids: list[UUID]
    support_levels: dict[UUID, SupportLevel]
    ranked_experiences: list[RankedExperience]
    returned_candidate_count: int
    recall_at_1: float | None
    recall_at_3: float | None
    recall_at_5: float | None
    precision_at_5: float | None
    hit_at_1: float | None
    hit_at_3: float | None
    hit_at_5: float | None
    reciprocal_rank_at_5: float | None
    no_relevant_returned_at_5: bool | None


class RetrievalV2Summary(BaseModel):
    query_count: int
    positive_query_count: int
    negative_query_count: int
    recall_at_1: float
    recall_at_3: float
    recall_at_5: float
    precision_at_5: float
    hit_at_1: float
    hit_at_3: float
    hit_at_5: float
    mrr_at_5: float
    no_relevant_returned_accuracy_at_5: float
    mean_returned_candidate_count: float


def load_corpus(path: Path) -> tuple[RetrievalV2Corpus, str]:
    content = path.read_bytes()
    corpus = RetrievalV2Corpus.model_validate_json(content)
    validate_corpus(corpus)
    return corpus, sha256(content).hexdigest()


def load_query_set(
    path: Path,
    corpus: RetrievalV2Corpus,
) -> tuple[RetrievalV2QuerySet, str]:
    content = path.read_bytes()
    query_set = RetrievalV2QuerySet.model_validate_json(content)
    validate_query_set(query_set, corpus)
    return query_set, sha256(content).hexdigest()


def load_review_manifest(path: Path) -> RetrievalV2ReviewManifest:
    return RetrievalV2ReviewManifest.model_validate_json(path.read_bytes())


def validate_review_manifest(
    manifest: RetrievalV2ReviewManifest,
    *,
    corpus_sha256: str,
    query_set_sha256: str,
    split: RetrievalSplit,
) -> None:
    if manifest.status is not ReviewStatus.APPROVED_FROZEN:
        raise ValueError("Retrieval v2 labels have not been approved and frozen.")
    if manifest.reviewer is None or manifest.reviewer.strip() == "":
        raise ValueError("An approved review manifest requires a reviewer.")
    if manifest.reviewed_at is None:
        raise ValueError("An approved review manifest requires a review timestamp.")
    if manifest.corpus_sha256 != corpus_sha256:
        raise ValueError("The reviewed corpus hash does not match the current file.")
    expected_query_hash = (
        manifest.development_queries_sha256
        if split is RetrievalSplit.DEVELOPMENT
        else manifest.holdout_queries_sha256
    )
    if expected_query_hash != query_set_sha256:
        raise ValueError("The reviewed query-set hash does not match the current file.")


def validate_corpus(corpus: RetrievalV2Corpus) -> None:
    profile_ids = [profile.profile_id for profile in corpus.profiles]
    if len(profile_ids) != len(set(profile_ids)):
        raise ValueError("Retrieval profile IDs must be unique.")

    experience_ids = [
        experience.id for profile in corpus.profiles for experience in profile.experiences
    ]
    if len(experience_ids) != len(set(experience_ids)):
        raise ValueError("V2 Experience IDs must be globally unique.")


def validate_query_set(query_set: RetrievalV2QuerySet, corpus: RetrievalV2Corpus) -> None:
    if query_set.version != corpus.version:
        raise ValueError("Corpus and query-set versions must match.")

    query_ids = [query.query_id for query in query_set.queries]
    if len(query_ids) != len(set(query_ids)):
        raise ValueError("V2 query IDs must be unique within a split.")

    requirement_ids = [query.requirement.id for query in query_set.queries]
    if len(requirement_ids) != len(set(requirement_ids)):
        raise ValueError("V2 requirement IDs must be unique within a split.")

    experiences_by_profile = {
        profile.profile_id: {experience.id: experience for experience in profile.experiences}
        for profile in corpus.profiles
    }
    for query in query_set.queries:
        profile_experiences = experiences_by_profile.get(query.profile_id)
        if profile_experiences is None:
            raise ValueError(f"Query {query.query_id} references an unknown profile.")
        validate_query(query, profile_experiences)


def validate_query(
    query: RetrievalV2Query,
    profile_experiences: dict[UUID, RetrievalEvalExperience],
) -> None:
    labels_by_id = {label.experience_id: label for label in query.labels}
    if len(labels_by_id) != len(query.labels):
        raise ValueError(f"Relevant labels must be unique in query {query.query_id}.")

    hard_negative_ids = query.hard_negative_experience_ids
    if len(hard_negative_ids) != len(set(hard_negative_ids)):
        raise ValueError(f"Hard-negative IDs must be unique in query {query.query_id}.")

    referenced_ids = set(labels_by_id) | set(hard_negative_ids)
    if referenced_ids - set(profile_experiences):
        raise ValueError(f"Query {query.query_id} references an Experience outside its profile.")
    if set(labels_by_id) & set(hard_negative_ids):
        raise ValueError(f"Query {query.query_id} overlaps relevant and hard-negative IDs.")

    if query.labels:
        if query.negative_rationale is not None:
            raise ValueError(f"Positive query {query.query_id} cannot have a negative rationale.")
    else:
        if query.negative_rationale is None or query.negative_rationale.strip() == "":
            raise ValueError(f"Negative query {query.query_id} requires a rationale.")
        if not hard_negative_ids:
            raise ValueError(f"Negative query {query.query_id} requires a hard negative.")

    if DifficultyTag.HARD_NEGATIVE in query.tags and not hard_negative_ids:
        raise ValueError(f"Hard-negative query {query.query_id} requires a labeled distractor.")
    if query.hard_negative_rationale is not None:
        if not hard_negative_ids:
            raise ValueError(
                f"Hard-negative rationale in query {query.query_id} requires a distractor."
            )
        if query.hard_negative_rationale.strip() == "":
            raise ValueError(
                f"Hard-negative rationale in query {query.query_id} cannot be blank."
            )
    if len(query.tags) != len(set(query.tags)):
        raise ValueError(f"Difficulty tags must be unique in query {query.query_id}.")

    skill = query.requirement.skill_normalized
    if skill is not None and skill != skill.strip().casefold():
        raise ValueError(f"Requirement skill is not normalized in query {query.query_id}.")

    for label in query.labels:
        experience = profile_experiences[label.experience_id]
        if not quote_is_grounded(label.supporting_quote, experience):
            raise ValueError(f"Label quote is not grounded in query {query.query_id}.")


def validate_acceptance_dataset(
    corpus: RetrievalV2Corpus,
    development: RetrievalV2QuerySet,
    holdout: RetrievalV2QuerySet,
) -> None:
    if development.split is not RetrievalSplit.DEVELOPMENT:
        raise ValueError("Development query file has the wrong split.")
    if holdout.split is not RetrievalSplit.HOLDOUT:
        raise ValueError("Holdout query file has the wrong split.")

    all_query_ids = [query.query_id for query in (*development.queries, *holdout.queries)]
    if len(all_query_ids) != len(set(all_query_ids)):
        raise ValueError("Query IDs must be unique across development and holdout.")

    all_requirement_ids = [
        query.requirement.id for query in (*development.queries, *holdout.queries)
    ]
    if len(all_requirement_ids) != len(set(all_requirement_ids)):
        raise ValueError("Requirement IDs must be unique across development and holdout.")

    profile_sizes = [len(profile.experiences) for profile in corpus.profiles]
    if len(corpus.profiles) != 4 or profile_sizes != [10, 10, 10, 10]:
        raise ValueError("P1-2b requires four profiles with ten Experiences each.")
    if len(development.queries) != 40 or len(holdout.queries) != 20:
        raise ValueError("P1-2b requires 40 development and 20 holdout queries.")

    validate_split_quotas(development, negatives=10, semantic=10, multi=8, composite=7, cjk=5)
    validate_split_quotas(holdout, negatives=5, semantic=5, multi=4, composite=3, cjk=3)

    hard_negative_count = sum(
        DifficultyTag.HARD_NEGATIVE in query.tags
        for query in (*development.queries, *holdout.queries)
    )
    if hard_negative_count < 20:
        raise ValueError("P1-2b requires at least 20 hard-negative queries.")


def validate_split_quotas(
    query_set: RetrievalV2QuerySet,
    *,
    negatives: int,
    semantic: int,
    multi: int,
    composite: int,
    cjk: int,
) -> None:
    queries = query_set.queries
    counts = Counter(
        {
            "negative": sum(not query.labels for query in queries),
            "semantic": sum(is_semantic_positive(query) for query in queries),
            "multi": sum(DifficultyTag.MULTI_RELEVANT in query.tags for query in queries),
            "composite": sum(DifficultyTag.COMPOSITE in query.tags for query in queries),
            "cjk": sum(has_cjk_tag(query) for query in queries),
        }
    )
    required_counts = {
        "negative": negatives,
        "semantic": semantic,
        "multi": multi,
        "composite": composite,
        "cjk": cjk,
    }
    for name, required_count in required_counts.items():
        actual = counts[name]
        exact = name == "negative"
        if (exact and actual != required_count) or (not exact and actual < required_count):
            comparison = "exactly" if exact else "at least"
            raise ValueError(
                f"{query_set.split.value} requires {comparison} {required_count} {name} queries; "
                f"found {actual}."
            )


def evaluate_query_set(
    corpus: RetrievalV2Corpus,
    query_set: RetrievalV2QuerySet,
) -> list[RetrievalV2QueryResult]:
    profiles = {
        profile.profile_id: tuple(
            to_experience_record(experience) for experience in profile.experiences
        )
        for profile in corpus.profiles
    }
    return [evaluate_query(query, profiles[query.profile_id]) for query in query_set.queries]


def evaluate_query(
    query: RetrievalV2Query,
    experiences: tuple[ExperienceRecord, ...],
) -> RetrievalV2QueryResult:
    requirement = to_requirement_record(query.requirement)
    candidates = retrieve_evidence_candidates(
        (requirement,),
        experiences,
        limit=DEFAULT_CANDIDATE_LIMIT,
    )[0].candidates
    support_levels = {label.experience_id: label.support_level for label in query.labels}
    relevant_ids = set(support_levels)
    ranked = [
        RankedExperience(
            experience_id=candidate.experience.id,
            rank=index,
            score=candidate.score,
            relevant=candidate.experience.id in relevant_ids,
        )
        for index, candidate in enumerate(candidates, start=1)
    ]
    if not relevant_ids:
        return RetrievalV2QueryResult(
            query_id=query.query_id,
            profile_id=query.profile_id,
            description=query.description,
            tags=query.tags,
            relevant_experience_ids=[],
            support_levels={},
            ranked_experiences=ranked,
            returned_candidate_count=len(ranked),
            recall_at_1=None,
            recall_at_3=None,
            recall_at_5=None,
            precision_at_5=None,
            hit_at_1=None,
            hit_at_3=None,
            hit_at_5=None,
            reciprocal_rank_at_5=None,
            no_relevant_returned_at_5=len(ranked) == 0,
        )

    first_relevant_rank = next((item.rank for item in ranked if item.relevant), None)
    return RetrievalV2QueryResult(
        query_id=query.query_id,
        profile_id=query.profile_id,
        description=query.description,
        tags=query.tags,
        relevant_experience_ids=list(support_levels),
        support_levels=support_levels,
        ranked_experiences=ranked,
        returned_candidate_count=len(ranked),
        recall_at_1=recall_at_k(ranked, relevant_ids, 1),
        recall_at_3=recall_at_k(ranked, relevant_ids, 3),
        recall_at_5=recall_at_k(ranked, relevant_ids, 5),
        precision_at_5=precision_at_k(ranked, relevant_ids, 5),
        hit_at_1=hit_at_k(ranked, relevant_ids, 1),
        hit_at_3=hit_at_k(ranked, relevant_ids, 3),
        hit_at_5=hit_at_k(ranked, relevant_ids, 5),
        reciprocal_rank_at_5=0.0 if first_relevant_rank is None else 1 / first_relevant_rank,
        no_relevant_returned_at_5=None,
    )


def summarize_results(results: list[RetrievalV2QueryResult]) -> RetrievalV2Summary:
    positive = [result for result in results if result.recall_at_5 is not None]
    negative = [result for result in results if result.no_relevant_returned_at_5 is not None]
    return RetrievalV2Summary(
        query_count=len(results),
        positive_query_count=len(positive),
        negative_query_count=len(negative),
        recall_at_1=mean([required(result.recall_at_1) for result in positive]),
        recall_at_3=mean([required(result.recall_at_3) for result in positive]),
        recall_at_5=mean([required(result.recall_at_5) for result in positive]),
        precision_at_5=mean([required(result.precision_at_5) for result in positive]),
        hit_at_1=mean([required(result.hit_at_1) for result in positive]),
        hit_at_3=mean([required(result.hit_at_3) for result in positive]),
        hit_at_5=mean([required(result.hit_at_5) for result in positive]),
        mrr_at_5=mean([required(result.reciprocal_rank_at_5) for result in positive]),
        no_relevant_returned_accuracy_at_5=mean(
            [float(required(result.no_relevant_returned_at_5)) for result in negative]
        ),
        mean_returned_candidate_count=mean(
            [float(result.returned_candidate_count) for result in results]
        ),
    )


def recall_at_k(ranked: list[RankedExperience], relevant_ids: set[UUID], k: int) -> float:
    return relevant_count_at_k(ranked, relevant_ids, k) / len(relevant_ids)


def precision_at_k(ranked: list[RankedExperience], relevant_ids: set[UUID], k: int) -> float:
    return relevant_count_at_k(ranked, relevant_ids, k) / k


def hit_at_k(ranked: list[RankedExperience], relevant_ids: set[UUID], k: int) -> float:
    return float(relevant_count_at_k(ranked, relevant_ids, k) > 0)


def relevant_count_at_k(
    ranked: list[RankedExperience], relevant_ids: set[UUID], k: int
) -> int:
    return sum(item.experience_id in relevant_ids for item in ranked[:k])


def quote_is_grounded(quote: str, experience: RetrievalEvalExperience) -> bool:
    normalized_quote = normalize_whitespace(quote)
    if not normalized_quote:
        return False
    source_fields = (
        experience.title,
        experience.description,
        *experience.skills,
        experience.outcome or "",
    )
    return any(normalized_quote in normalize_whitespace(field) for field in source_fields)


def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def is_semantic_positive(query: RetrievalV2Query) -> bool:
    semantic_tags = {DifficultyTag.PARAPHRASE, DifficultyTag.ZH_EN, DifficultyTag.EN_ZH}
    return bool(query.labels and semantic_tags & set(query.tags))


def has_cjk_tag(query: RetrievalV2Query) -> bool:
    cjk_tags = {DifficultyTag.ZH_ZH, DifficultyTag.ZH_EN, DifficultyTag.EN_ZH}
    return bool(cjk_tags & set(query.tags))


__all__ = [
    "DEFAULT_CANDIDATE_LIMIT",
    "RETRIEVER_VERSION",
    "DifficultyTag",
    "RetrievalProfile",
    "RetrievalV2ReviewManifest",
    "RetrievalRelevanceLabel",
    "ReviewStatus",
    "RetrievalSplit",
    "RetrievalV2Corpus",
    "RetrievalV2Query",
    "RetrievalV2QueryResult",
    "RetrievalV2QuerySet",
    "RetrievalV2Summary",
    "SupportLevel",
    "evaluate_query",
    "evaluate_query_set",
    "hit_at_k",
    "load_corpus",
    "load_query_set",
    "load_review_manifest",
    "precision_at_k",
    "recall_at_k",
    "summarize_results",
    "validate_acceptance_dataset",
    "validate_review_manifest",
]
