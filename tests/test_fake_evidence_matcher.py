import pytest
from tests.test_evidence_retrieval import make_experience, make_requirement

from careerops.adapters.fake_evidence_matcher import FakeEvidenceMatcher
from careerops.domain.evidence_matching import EvidenceVerdict
from careerops.domain.evidence_retrieval import retrieve_evidence_candidates
from careerops.services.evidence_matcher_contract import build_evidence_matcher_input


@pytest.mark.asyncio
async def test_fake_matcher_uses_exact_skill_as_grounded_match() -> None:
    requirement = make_requirement(skill="Python", text="Python required")
    experience = make_experience(
        "00000000-0000-0000-0000-000000000001",
        skills=("Python",),
        description="Built APIs.",
    )

    candidate_sets = retrieve_evidence_candidates((requirement,), (experience,))
    output = await FakeEvidenceMatcher().match(build_evidence_matcher_input(candidate_sets))

    assert output.model_name == "local-fake-evidence-matcher"
    assert output.matches[0].verdict is EvidenceVerdict.MATCHED
    assert output.matches[0].experience_id == experience.id
    assert output.matches[0].source_ref == "skill:0"
    assert output.matches[0].quote == "Python"
    assert output.matches[0].confidence is None


@pytest.mark.asyncio
async def test_fake_matcher_returns_missing_without_candidate() -> None:
    requirement = make_requirement(skill="Kubernetes", text="Kubernetes required")
    experience = make_experience(
        "00000000-0000-0000-0000-000000000001",
        skills=("Python",),
        description="Built APIs.",
    )

    candidate_sets = retrieve_evidence_candidates((requirement,), (experience,))
    output = await FakeEvidenceMatcher().match(build_evidence_matcher_input(candidate_sets))

    assert output.matches[0].verdict is EvidenceVerdict.MISSING
    assert output.matches[0].experience_id is None
    assert output.matches[0].quote is None
