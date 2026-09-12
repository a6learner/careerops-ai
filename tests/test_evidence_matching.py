from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from careerops.domain.evidence_matching import (
    EvidenceVerdict,
    ProposedEvidenceMatch,
    validate_evidence_match,
)
from careerops.domain.experiences import ExperienceKind, ExperienceRecord


def test_valid_match_requires_owned_candidate_with_current_version_and_source_quote() -> None:
    user_id = uuid4()
    requirement_id = uuid4()
    experience = make_experience(user_id=user_id)

    result = validate_evidence_match(
        ProposedEvidenceMatch(
            requirement_id=requirement_id,
            verdict=EvidenceVerdict.MATCHED,
            experience_id=experience.id,
            experience_version=experience.version,
            quote="Built   reliable APIs",
            confidence=0.9,
        ),
        user_id=user_id,
        experiences={experience.id: experience},
        candidate_experience_ids={experience.id},
    )

    assert result.verdict is EvidenceVerdict.MATCHED
    assert result.experience_id == experience.id
    assert result.quote_valid
    assert not result.validation_failed


@pytest.mark.parametrize("failure", ["unknown", "other_user", "not_candidate", "stale", "quote"])
def test_invalid_positive_claim_is_downgraded_and_stripped(failure: str) -> None:
    user_id = uuid4()
    experience = make_experience(user_id=user_id)
    experiences = {experience.id: experience}
    candidate_ids = {experience.id}
    proposal_id = experience.id
    proposal_version = experience.version
    quote = "Built reliable APIs"

    if failure == "unknown":
        proposal_id = uuid4()
    elif failure == "other_user":
        experience = make_experience(user_id=uuid4())
        experiences = {experience.id: experience}
        candidate_ids = {experience.id}
        proposal_id = experience.id
    elif failure == "not_candidate":
        candidate_ids = set()
    elif failure == "stale":
        proposal_version -= 1
    elif failure == "quote":
        quote = "Invented Kubernetes production experience"

    result = validate_evidence_match(
        ProposedEvidenceMatch(
            requirement_id=uuid4(),
            verdict=EvidenceVerdict.PARTIAL,
            experience_id=proposal_id,
            experience_version=proposal_version,
            quote=quote,
            confidence=0.6,
        ),
        user_id=user_id,
        experiences=experiences,
        candidate_experience_ids=candidate_ids,
    )

    assert result.verdict is EvidenceVerdict.INSUFFICIENT_EVIDENCE
    assert result.experience_id is None
    assert result.experience_version is None
    assert result.quote is None
    assert not result.quote_valid
    assert result.validation_failed


def test_missing_verdict_without_evidence_is_valid_gap() -> None:
    result = validate_evidence_match(
        ProposedEvidenceMatch(
            requirement_id=uuid4(),
            verdict=EvidenceVerdict.MISSING,
            experience_id=None,
            experience_version=None,
            quote=None,
            confidence=None,
        ),
        user_id=uuid4(),
        experiences={},
        candidate_experience_ids=set(),
    )

    assert result.verdict is EvidenceVerdict.MISSING
    assert not result.quote_valid
    assert not result.validation_failed


def test_gap_that_carries_claimed_evidence_is_downgraded() -> None:
    result = validate_evidence_match(
        ProposedEvidenceMatch(
            requirement_id=uuid4(),
            verdict=EvidenceVerdict.MISSING,
            experience_id=uuid4(),
            experience_version=1,
            quote="claim",
            confidence=None,
        ),
        user_id=uuid4(),
        experiences={},
        candidate_experience_ids=set(),
    )

    assert result.verdict is EvidenceVerdict.INSUFFICIENT_EVIDENCE
    assert result.validation_failed


def make_experience(*, user_id: UUID) -> ExperienceRecord:
    now = datetime.now(UTC)
    return ExperienceRecord(
        id=uuid4(),
        user_id=user_id,
        title="CareerOps AI",
        kind=ExperienceKind.PROJECT,
        description="Built reliable APIs with FastAPI and PostgreSQL.",
        skills=("Python", "FastAPI"),
        outcome="Added deterministic integration tests.",
        version=3,
        content_hash="a" * 64,
        created_at=now,
        updated_at=now,
    )
