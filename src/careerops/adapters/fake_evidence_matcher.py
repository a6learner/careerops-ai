from careerops.domain.analysis_runs import FAKE_ANALYSIS_MODEL_NAME, EvidenceMatcherOutput
from careerops.domain.evidence_matching import (
    EvidenceMatcherInput,
    EvidenceSourceInput,
    EvidenceVerdict,
    MatcherExperienceInput,
    MatcherRequirementInput,
    ProposedEvidenceMatch,
)


class FakeEvidenceMatcher:
    @property
    def model_name(self) -> str:
        return FAKE_ANALYSIS_MODEL_NAME

    async def match(
        self,
        matcher_input: EvidenceMatcherInput,
    ) -> EvidenceMatcherOutput:
        requirements = {
            requirement.requirement_id: requirement
            for requirement in matcher_input.requirements
        }
        experiences = {
            experience.experience_id: experience
            for experience in matcher_input.experiences
        }
        proposals = tuple(
            self._match_requirement(
                requirements[candidate_set.requirement_id],
                tuple(
                    experiences[candidate.experience_id]
                    for candidate in candidate_set.candidates
                ),
            )
            for candidate_set in matcher_input.candidate_sets
        )
        return EvidenceMatcherOutput(model_name=self.model_name, matches=proposals)

    def _match_requirement(
        self,
        requirement: MatcherRequirementInput,
        candidates: tuple[MatcherExperienceInput, ...],
    ) -> ProposedEvidenceMatch:
        if not candidates:
            return ProposedEvidenceMatch(
                requirement_id=requirement.requirement_id,
                verdict=EvidenceVerdict.MISSING,
                experience_id=None,
                experience_version=None,
                quote=None,
                confidence=None,
            )

        experience = candidates[0]
        exact_skill = (
            requirement.skill_normalized is not None
            and any(
                requirement.skill_normalized.casefold().strip()
                == source.text.casefold().strip()
                for source in experience.sources
                if source.source_ref.startswith("skill:")
            )
        )
        source = _source_for(requirement, experience.sources)
        return ProposedEvidenceMatch(
            requirement_id=requirement.requirement_id,
            verdict=EvidenceVerdict.MATCHED if exact_skill else EvidenceVerdict.PARTIAL,
            experience_id=experience.experience_id,
            experience_version=experience.experience_version,
            source_ref=source.source_ref,
            quote=source.text,
            confidence=None,
        )


def _source_for(
    requirement: MatcherRequirementInput,
    sources: tuple[EvidenceSourceInput, ...],
) -> EvidenceSourceInput:
    normalized_skill = (
        requirement.skill_normalized.casefold().strip()
        if requirement.skill_normalized is not None
        else None
    )
    if normalized_skill:
        for source in sources:
            if (
                source.source_ref.startswith("skill:")
                and source.text.casefold().strip() == normalized_skill
            ):
                return source
    requirement_tokens = set(requirement.text.casefold().split())
    return max(
        sources,
        key=lambda source: (
            len(requirement_tokens & set(source.text.casefold().split())),
            -len(source.text),
        ),
    )
