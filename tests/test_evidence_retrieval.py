from datetime import UTC, datetime
from uuid import UUID

from careerops.domain.evidence_retrieval import retrieve_evidence_candidates
from careerops.domain.experiences import ExperienceKind, ExperienceRecord
from careerops.domain.parse_runs import JobRequirementRecord, RequirementCategory


def test_retrieval_prefers_exact_skill_and_uses_stable_id_tie_break() -> None:
    requirement = make_requirement(skill="Python", text="Python backend experience required.")
    exact_later = make_experience(
        "00000000-0000-0000-0000-000000000002",
        skills=("Python",),
        description="Built backend services.",
    )
    exact_first = make_experience(
        "00000000-0000-0000-0000-000000000001",
        skills=("Python",),
        description="Built backend services.",
    )

    result = retrieve_evidence_candidates(
        (requirement,),
        (exact_later, exact_first),
    )

    assert [candidate.experience.id for candidate in result[0].candidates] == [
        exact_first.id,
        exact_later.id,
    ]


def test_retrieval_excludes_unrelated_experiences_and_applies_limit() -> None:
    requirement = make_requirement(skill=None, text="Redis caching")
    related = tuple(
        make_experience(
            f"00000000-0000-0000-0000-{index:012d}",
            skills=("Redis",),
            description="Implemented Redis caching.",
        )
        for index in range(1, 4)
    )
    unrelated = make_experience(
        "00000000-0000-0000-0000-000000000099",
        skills=("React",),
        description="Built a frontend.",
    )

    result = retrieve_evidence_candidates((requirement,), (*related, unrelated), limit=2)

    assert len(result[0].candidates) == 2
    assert unrelated.id not in {candidate.experience.id for candidate in result[0].candidates}


def make_requirement(*, skill: str | None, text: str) -> JobRequirementRecord:
    return JobRequirementRecord(
        id=UUID("10000000-0000-0000-0000-000000000001"),
        job_id=UUID("20000000-0000-0000-0000-000000000001"),
        parse_run_id=UUID("30000000-0000-0000-0000-000000000001"),
        category=RequirementCategory.MUST_HAVE,
        text=text,
        skill_normalized=skill,
        source_span_start=0,
        source_span_end=len(text),
    )


def make_experience(
    experience_id: str,
    *,
    skills: tuple[str, ...],
    description: str,
) -> ExperienceRecord:
    now = datetime.now(UTC)
    return ExperienceRecord(
        id=UUID(experience_id),
        user_id=UUID("40000000-0000-0000-0000-000000000001"),
        title="Project",
        kind=ExperienceKind.PROJECT,
        description=description,
        skills=skills,
        outcome=None,
        version=1,
        content_hash="a" * 64,
        created_at=now,
        updated_at=now,
    )
