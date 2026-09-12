import re
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from careerops.domain.experiences import ExperienceRecord


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
            for value in (proposal.experience_id, proposal.experience_version, proposal.quote)
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
        or proposal.quote is None
    ):
        return _insufficient(proposal)

    experience = experiences.get(proposal.experience_id)
    if (
        experience is None
        or experience.user_id != user_id
        or experience.id not in candidate_experience_ids
        or experience.version != proposal.experience_version
        or not _quote_is_grounded(proposal.quote, experience)
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


def _quote_is_grounded(quote: str, experience: ExperienceRecord) -> bool:
    normalized_quote = _normalize_whitespace(quote)
    if not normalized_quote:
        return False
    source_fields = (
        experience.title,
        experience.description,
        *experience.skills,
        experience.outcome or "",
    )
    return any(normalized_quote in _normalize_whitespace(field) for field in source_fields)


def _normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


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
