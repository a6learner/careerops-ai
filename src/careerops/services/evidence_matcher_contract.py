from uuid import UUID

from careerops.domain.errors import MatcherOutputFailureReason, MatcherOutputValidationError
from careerops.domain.evidence_matching import (
    MATCHER_PROMPT_VERSION,
    MATCHER_SCHEMA_VERSION,
    SUPPORTED_MATCHER_PROMPT_VERSIONS,
    EvidenceMatcherInput,
    MatcherCandidateInput,
    MatcherCandidateSetInput,
    MatcherExperienceInput,
    MatcherRequirementInput,
    evidence_sources,
)
from careerops.domain.evidence_retrieval import (
    DEFAULT_CANDIDATE_LIMIT,
    RequirementCandidateSet,
)


def build_evidence_matcher_input(
    candidate_sets: tuple[RequirementCandidateSet, ...],
    *,
    prompt_version: str = MATCHER_PROMPT_VERSION,
) -> EvidenceMatcherInput:
    if prompt_version not in SUPPORTED_MATCHER_PROMPT_VERSIONS:
        raise MatcherOutputValidationError(MatcherOutputFailureReason.INVALID_CONTRACT)
    requirement_ids = [candidate_set.requirement.id for candidate_set in candidate_sets]
    if len(requirement_ids) != len(set(requirement_ids)):
        raise MatcherOutputValidationError(MatcherOutputFailureReason.INVALID_CONTRACT)

    experiences: dict[UUID, MatcherExperienceInput] = {}
    typed_candidate_sets: list[MatcherCandidateSetInput] = []
    for candidate_set in candidate_sets:
        if len(candidate_set.candidates) > DEFAULT_CANDIDATE_LIMIT:
            raise MatcherOutputValidationError(MatcherOutputFailureReason.INVALID_CONTRACT)
        candidates: list[MatcherCandidateInput] = []
        for rank, candidate in enumerate(candidate_set.candidates, start=1):
            experience = candidate.experience
            typed_experience = MatcherExperienceInput(
                experience_id=experience.id,
                experience_version=experience.version,
                sources=evidence_sources(experience),
            )
            existing = experiences.setdefault(experience.id, typed_experience)
            if existing != typed_experience:
                raise MatcherOutputValidationError(
                    MatcherOutputFailureReason.INVALID_CONTRACT
                )
            candidates.append(
                MatcherCandidateInput(
                    experience_id=experience.id,
                    rank=rank,
                )
            )
        typed_candidate_sets.append(
            MatcherCandidateSetInput(
                requirement_id=candidate_set.requirement.id,
                candidates=tuple(candidates),
            )
        )

    return EvidenceMatcherInput(
        schema_version=MATCHER_SCHEMA_VERSION,
        prompt_version=prompt_version,
        requirements=tuple(
            MatcherRequirementInput(
                requirement_id=candidate_set.requirement.id,
                category=candidate_set.requirement.category,
                text=candidate_set.requirement.text,
                skill_normalized=candidate_set.requirement.skill_normalized,
            )
            for candidate_set in candidate_sets
        ),
        experiences=tuple(experiences.values()),
        candidate_sets=tuple(typed_candidate_sets),
    )
