from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from careerops.domain.evidence_retrieval import (
    DEFAULT_CANDIDATE_LIMIT,
    retrieve_evidence_candidates,
)
from careerops.domain.experiences import ExperienceKind, ExperienceRecord
from careerops.domain.parse_runs import JobRequirementRecord, RequirementCategory

RETRIEVER_VERSION = "lexical-skill-v1"
EVALUATION_USER_ID = UUID("00000000-0000-0000-0000-000000000001")
EVALUATION_JOB_ID = UUID("00000000-0000-0000-0000-000000000002")
EVALUATION_PARSE_RUN_ID = UUID("00000000-0000-0000-0000-000000000003")
EVALUATION_TIMESTAMP = datetime(2000, 1, 1, tzinfo=UTC)
MetricValue = TypeVar("MetricValue")


class RetrievalEvalExperience(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    title: str = Field(min_length=1)
    kind: ExperienceKind
    description: str = Field(min_length=1)
    skills: list[str] = Field(min_length=1)
    outcome: str | None = None


class RetrievalEvalRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    category: RequirementCategory
    text: str = Field(min_length=1)
    skill_normalized: str | None


class RetrievalEvalCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    requirement: RetrievalEvalRequirement
    relevant_experience_ids: list[UUID]


class RetrievalEvalDataset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    version: int = Field(ge=1)
    experiences: list[RetrievalEvalExperience] = Field(min_length=1)
    cases: list[RetrievalEvalCase] = Field(min_length=1)


class RankedExperience(BaseModel):
    experience_id: UUID
    rank: int = Field(ge=1)
    score: int = Field(gt=0)
    relevant: bool


class RetrievalEvalCaseResult(BaseModel):
    case_id: str
    description: str
    relevant_experience_ids: list[UUID]
    ranked_experiences: list[RankedExperience]
    recall_at_1: float | None
    recall_at_3: float | None
    recall_at_5: float | None
    reciprocal_rank_at_5: float | None
    no_relevant_returned_at_5: bool | None


class RetrievalEvalSummary(BaseModel):
    query_count: int
    positive_query_count: int
    negative_query_count: int
    recall_at_1: float
    recall_at_3: float
    recall_at_5: float
    mrr_at_5: float
    no_relevant_returned_accuracy_at_5: float


class RetrievalEvalReport(BaseModel):
    created_at: datetime
    git_revision: str
    dataset_name: str
    dataset_version: int
    dataset_sha256: str
    retriever_version: str
    candidate_limit: int
    summary: RetrievalEvalSummary
    cases: list[RetrievalEvalCaseResult]
    limitations: list[str]


def load_dataset(path: Path) -> tuple[RetrievalEvalDataset, str]:
    content = path.read_bytes()
    dataset = RetrievalEvalDataset.model_validate_json(content)
    validate_dataset(dataset)
    return dataset, sha256(content).hexdigest()


def validate_dataset(dataset: RetrievalEvalDataset) -> None:
    experience_ids = [experience.id for experience in dataset.experiences]
    if len(experience_ids) != len(set(experience_ids)):
        raise ValueError("Evaluation Experience IDs must be unique.")

    case_ids = [case.case_id for case in dataset.cases]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("Evaluation case IDs must be unique.")

    requirement_ids = [case.requirement.id for case in dataset.cases]
    if len(requirement_ids) != len(set(requirement_ids)):
        raise ValueError("Evaluation requirement IDs must be unique.")

    known_experience_ids = set(experience_ids)
    for case in dataset.cases:
        relevant_ids = case.relevant_experience_ids
        if len(relevant_ids) != len(set(relevant_ids)):
            raise ValueError(f"Relevant Experience IDs must be unique in case {case.case_id}.")
        unknown_ids = set(relevant_ids) - known_experience_ids
        if unknown_ids:
            raise ValueError(f"Case {case.case_id} references an unknown Experience ID.")


def evaluate_dataset(dataset: RetrievalEvalDataset) -> list[RetrievalEvalCaseResult]:
    experiences = tuple(to_experience_record(item) for item in dataset.experiences)
    return [evaluate_case(case, experiences) for case in dataset.cases]


def evaluate_case(
    case: RetrievalEvalCase,
    experiences: tuple[ExperienceRecord, ...],
) -> RetrievalEvalCaseResult:
    requirement = to_requirement_record(case.requirement)
    candidate_set = retrieve_evidence_candidates(
        (requirement,),
        experiences,
        limit=DEFAULT_CANDIDATE_LIMIT,
    )[0]
    relevant_ids = set(case.relevant_experience_ids)
    ranked = [
        RankedExperience(
            experience_id=candidate.experience.id,
            rank=index,
                score=int(candidate.score),
            relevant=candidate.experience.id in relevant_ids,
        )
        for index, candidate in enumerate(candidate_set.candidates, start=1)
    ]

    if not relevant_ids:
        return RetrievalEvalCaseResult(
            case_id=case.case_id,
            description=case.description,
            relevant_experience_ids=[],
            ranked_experiences=ranked,
            recall_at_1=None,
            recall_at_3=None,
            recall_at_5=None,
            reciprocal_rank_at_5=None,
            no_relevant_returned_at_5=len(ranked) == 0,
        )

    first_relevant_rank = next((item.rank for item in ranked if item.relevant), None)
    return RetrievalEvalCaseResult(
        case_id=case.case_id,
        description=case.description,
        relevant_experience_ids=case.relevant_experience_ids,
        ranked_experiences=ranked,
        recall_at_1=recall_at_k(ranked, relevant_ids, 1),
        recall_at_3=recall_at_k(ranked, relevant_ids, 3),
        recall_at_5=recall_at_k(ranked, relevant_ids, 5),
        reciprocal_rank_at_5=0.0 if first_relevant_rank is None else 1 / first_relevant_rank,
        no_relevant_returned_at_5=None,
    )


def summarize_results(results: list[RetrievalEvalCaseResult]) -> RetrievalEvalSummary:
    positive = [result for result in results if result.recall_at_5 is not None]
    negative = [result for result in results if result.no_relevant_returned_at_5 is not None]
    return RetrievalEvalSummary(
        query_count=len(results),
        positive_query_count=len(positive),
        negative_query_count=len(negative),
        recall_at_1=mean([required(result.recall_at_1) for result in positive]),
        recall_at_3=mean([required(result.recall_at_3) for result in positive]),
        recall_at_5=mean([required(result.recall_at_5) for result in positive]),
        mrr_at_5=mean([required(result.reciprocal_rank_at_5) for result in positive]),
        no_relevant_returned_accuracy_at_5=mean(
            [float(required(result.no_relevant_returned_at_5)) for result in negative]
        ),
    )


def recall_at_k(
    ranked: list[RankedExperience],
    relevant_ids: set[UUID],
    k: int,
) -> float:
    retrieved_ids = {item.experience_id for item in ranked[:k]}
    return len(retrieved_ids & relevant_ids) / len(relevant_ids)


def mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def required(value: MetricValue | None) -> MetricValue:
    if value is None:
        raise ValueError("Expected a defined evaluation metric.")
    return value


def to_experience_record(item: RetrievalEvalExperience) -> ExperienceRecord:
    content_hash = sha256(item.model_dump_json().encode("utf-8")).hexdigest()
    return ExperienceRecord(
        id=item.id,
        user_id=EVALUATION_USER_ID,
        title=item.title,
        kind=item.kind,
        description=item.description,
        skills=tuple(item.skills),
        outcome=item.outcome,
        version=1,
        content_hash=content_hash,
        created_at=EVALUATION_TIMESTAMP,
        updated_at=EVALUATION_TIMESTAMP,
    )


def to_requirement_record(item: RetrievalEvalRequirement) -> JobRequirementRecord:
    return JobRequirementRecord(
        id=item.id,
        job_id=EVALUATION_JOB_ID,
        parse_run_id=EVALUATION_PARSE_RUN_ID,
        category=item.category,
        text=item.text,
        skill_normalized=item.skill_normalized,
        source_span_start=None,
        source_span_end=None,
    )
