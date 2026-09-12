from careerops.domain.analysis_runs import FAKE_ANALYSIS_MODEL_NAME, EvidenceMatcherOutput
from careerops.domain.evidence_matching import EvidenceVerdict, ProposedEvidenceMatch
from careerops.domain.evidence_retrieval import RequirementCandidateSet, source_quote_for


class FakeEvidenceMatcher:
    @property
    def model_name(self) -> str:
        return FAKE_ANALYSIS_MODEL_NAME

    async def match(
        self,
        candidate_sets: tuple[RequirementCandidateSet, ...],
    ) -> EvidenceMatcherOutput:
        proposals = tuple(
            self._match_requirement(candidate_set) for candidate_set in candidate_sets
        )
        return EvidenceMatcherOutput(model_name=self.model_name, matches=proposals)

    def _match_requirement(self, candidate_set: RequirementCandidateSet) -> ProposedEvidenceMatch:
        if not candidate_set.candidates:
            return ProposedEvidenceMatch(
                requirement_id=candidate_set.requirement.id,
                verdict=EvidenceVerdict.MISSING,
                experience_id=None,
                experience_version=None,
                quote=None,
                confidence=None,
            )

        experience = candidate_set.candidates[0].experience
        exact_skill = (
            candidate_set.requirement.skill_normalized is not None
            and any(
                candidate_set.requirement.skill_normalized.casefold().strip()
                == skill.casefold().strip()
                for skill in experience.skills
            )
        )
        return ProposedEvidenceMatch(
            requirement_id=candidate_set.requirement.id,
            verdict=EvidenceVerdict.MATCHED if exact_skill else EvidenceVerdict.PARTIAL,
            experience_id=experience.id,
            experience_version=experience.version,
            quote=source_quote_for(candidate_set.requirement, experience),
            confidence=None,
        )
