import re
from dataclasses import dataclass

from careerops.domain.experiences import ExperienceRecord
from careerops.domain.parse_runs import JobRequirementRecord

DEFAULT_CANDIDATE_LIMIT = 5

_STOP_WORDS = {
    "a",
    "an",
    "and",
    "be",
    "for",
    "in",
    "of",
    "or",
    "the",
    "to",
    "with",
}


@dataclass(frozen=True)
class EvidenceCandidate:
    experience: ExperienceRecord
    score: int


@dataclass(frozen=True)
class RequirementCandidateSet:
    requirement: JobRequirementRecord
    candidates: tuple[EvidenceCandidate, ...]


def retrieve_evidence_candidates(
    requirements: tuple[JobRequirementRecord, ...],
    experiences: tuple[ExperienceRecord, ...],
    *,
    limit: int = DEFAULT_CANDIDATE_LIMIT,
) -> tuple[RequirementCandidateSet, ...]:
    return tuple(
        RequirementCandidateSet(
            requirement=requirement,
            candidates=_rank_candidates(requirement, experiences, limit),
        )
        for requirement in requirements
    )


def _rank_candidates(
    requirement: JobRequirementRecord,
    experiences: tuple[ExperienceRecord, ...],
    limit: int,
) -> tuple[EvidenceCandidate, ...]:
    scored = [
        EvidenceCandidate(experience=experience, score=_score(requirement, experience))
        for experience in experiences
    ]
    relevant = [candidate for candidate in scored if candidate.score > 0]
    relevant.sort(key=lambda candidate: (-candidate.score, str(candidate.experience.id)))
    return tuple(relevant[:limit])


def _score(requirement: JobRequirementRecord, experience: ExperienceRecord) -> int:
    requirement_tokens = _tokens(requirement.text)
    experience_tokens = _tokens(" ".join(_source_fields(experience)))
    overlap_score = len(requirement_tokens & experience_tokens)

    skill_score = 0
    if requirement.skill_normalized is not None:
        normalized_skill = requirement.skill_normalized.casefold().strip()
        if normalized_skill and any(
            normalized_skill == skill.casefold().strip() for skill in experience.skills
        ):
            skill_score = 100
        elif normalized_skill and normalized_skill in experience_tokens:
            skill_score = 20
    return skill_score + overlap_score


def source_quote_for(requirement: JobRequirementRecord, experience: ExperienceRecord) -> str:
    if requirement.skill_normalized is not None:
        normalized_skill = requirement.skill_normalized.casefold().strip()
        for skill in experience.skills:
            if normalized_skill == skill.casefold().strip():
                return skill

    requirement_tokens = _tokens(requirement.text)
    fields = _source_fields(experience)
    return max(
        fields,
        key=lambda field: (len(requirement_tokens & _tokens(field)), -len(field)),
    )


def _source_fields(experience: ExperienceRecord) -> tuple[str, ...]:
    return (
        experience.title,
        experience.description,
        *experience.skills,
        experience.outcome or "",
    )


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[\w+#.]+", value.casefold())
        if len(token) > 1 and token not in _STOP_WORDS
    }
