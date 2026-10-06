from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from careerops.domain.experiences import ExperienceRecord
from careerops.domain.parse_runs import RequirementCategory

MATCHER_SCHEMA_VERSION = "evidence-matcher-schema-v1"
MATCHER_PROMPT_VERSION_V1 = "evidence-matcher-prompt-v1"
MATCHER_PROMPT_VERSION_V2 = "evidence-matcher-prompt-v2"
MATCHER_PROMPT_VERSION_V3 = "evidence-matcher-prompt-v3"
MATCHER_PROMPT_VERSION_V4 = "evidence-matcher-prompt-v4"
MATCHER_PROMPT_VERSION_V5 = "evidence-matcher-prompt-v5"
MATCHER_PROMPT_VERSION = MATCHER_PROMPT_VERSION_V4
SUPPORTED_MATCHER_PROMPT_VERSIONS = (
    MATCHER_PROMPT_VERSION_V1,
    MATCHER_PROMPT_VERSION_V2,
    MATCHER_PROMPT_VERSION_V3,
    MATCHER_PROMPT_VERSION_V4,
    MATCHER_PROMPT_VERSION_V5,
)


class EvidenceVerdict(StrEnum):
    MATCHED = "matched"
    PARTIAL = "partial"
    MISSING = "missing"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


@dataclass(frozen=True)
class ProposedEvidenceMatch:
    requirement_id: UUID
    verdict: EvidenceVerdict
    experience_id: UUID | None
    experience_version: int | None
    quote: str | None
    confidence: float | None
    source_ref: str | None = None


@dataclass(frozen=True)
class EvidenceSourceInput:
    source_ref: str
    text: str


@dataclass(frozen=True)
class MatcherRequirementInput:
    requirement_id: UUID
    category: RequirementCategory
    text: str
    skill_normalized: str | None


@dataclass(frozen=True)
class MatcherExperienceInput:
    experience_id: UUID
    experience_version: int
    sources: tuple[EvidenceSourceInput, ...]


@dataclass(frozen=True)
class MatcherCandidateInput:
    experience_id: UUID
    rank: int


@dataclass(frozen=True)
class MatcherCandidateSetInput:
    requirement_id: UUID
    candidates: tuple[MatcherCandidateInput, ...]


@dataclass(frozen=True)
class EvidenceMatcherInput:
    schema_version: str
    prompt_version: str
    requirements: tuple[MatcherRequirementInput, ...]
    experiences: tuple[MatcherExperienceInput, ...]
    candidate_sets: tuple[MatcherCandidateSetInput, ...]


@dataclass(frozen=True)
class ValidatedEvidenceMatch:
    requirement_id: UUID
    verdict: EvidenceVerdict
    experience_id: UUID | None
    experience_version: int | None
    quote: str | None
    quote_valid: bool
    confidence: float | None
    validation_failed: bool


def validate_evidence_match(
    proposal: ProposedEvidenceMatch,
    *,
    user_id: UUID,
    experiences: dict[UUID, ExperienceRecord],
    candidate_experience_ids: set[UUID],
) -> ValidatedEvidenceMatch:
    if proposal.verdict in {EvidenceVerdict.MISSING, EvidenceVerdict.INSUFFICIENT_EVIDENCE}:
        if any(
            value is not None
            for value in (
                proposal.experience_id,
                proposal.experience_version,
                proposal.source_ref,
                proposal.quote,
            )
        ):
            return _insufficient(proposal)
        return ValidatedEvidenceMatch(
            requirement_id=proposal.requirement_id,
            verdict=proposal.verdict,
            experience_id=None,
            experience_version=None,
            quote=None,
            quote_valid=False,
            confidence=proposal.confidence,
            validation_failed=False,
        )

    if (
        proposal.experience_id is None
        or proposal.experience_version is None
        or proposal.source_ref is None
        or proposal.quote is None
    ):
        return _insufficient(proposal)

    experience = experiences.get(proposal.experience_id)
    if (
        experience is None
        or experience.user_id != user_id
        or experience.id not in candidate_experience_ids
        or experience.version != proposal.experience_version
        or derive_quote_span(proposal.source_ref, proposal.quote, experience) is None
    ):
        return _insufficient(proposal)

    return ValidatedEvidenceMatch(
        requirement_id=proposal.requirement_id,
        verdict=proposal.verdict,
        experience_id=experience.id,
        experience_version=experience.version,
        quote=proposal.quote,
        quote_valid=True,
        confidence=proposal.confidence,
        validation_failed=False,
    )


def evidence_sources(experience: ExperienceRecord) -> tuple[EvidenceSourceInput, ...]:
    sources = [
        EvidenceSourceInput(source_ref="title", text=experience.title),
        EvidenceSourceInput(source_ref="description", text=experience.description),
        *(
            EvidenceSourceInput(source_ref=f"skill:{index}", text=skill)
            for index, skill in enumerate(experience.skills)
        ),
    ]
    if experience.outcome is not None:
        sources.append(EvidenceSourceInput(source_ref="outcome", text=experience.outcome))
    return tuple(sources)


def derive_quote_span(
    source_ref: str,
    quote: str,
    experience: ExperienceRecord,
) -> tuple[int, int] | None:
    if not quote.strip():
        return None
    source_text = next(
        (source.text for source in evidence_sources(experience) if source.source_ref == source_ref),
        None,
    )
    if source_text is None:
        return None
    start = source_text.find(quote)
    if start < 0:
        return None
    return start, start + len(quote)


def _insufficient(proposal: ProposedEvidenceMatch) -> ValidatedEvidenceMatch:
    return ValidatedEvidenceMatch(
        requirement_id=proposal.requirement_id,
        verdict=EvidenceVerdict.INSUFFICIENT_EVIDENCE,
        experience_id=None,
        experience_version=None,
        quote=None,
        quote_valid=False,
        confidence=proposal.confidence,
        validation_failed=True,
    )
