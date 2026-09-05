import pytest
from pydantic import ValidationError

from careerops.domain.experiences import ExperienceKind
from careerops.schemas.experiences import ExperienceCreateRequest, ExperienceUpdateRequest


def test_create_experience_normalizes_text_and_skills() -> None:
    payload = ExperienceCreateRequest(
        title="  Backend API  ",
        kind=ExperienceKind.PROJECT,
        description="  Built FastAPI endpoints.  ",
        skills=[" Python ", "python", "FastAPI"],
    )

    assert payload.title == "Backend API"
    assert payload.description == "Built FastAPI endpoints."
    assert payload.skills == ["Python", "FastAPI"]


def test_create_experience_rejects_blank_skill() -> None:
    with pytest.raises(ValidationError):
        ExperienceCreateRequest(
            title="Backend API",
            kind=ExperienceKind.PROJECT,
            description="Built FastAPI endpoints.",
            skills=["Python", " "],
        )


def test_update_experience_can_distinguish_clear_outcome_from_omitted_outcome() -> None:
    omitted = ExperienceUpdateRequest(title="New title")
    cleared = ExperienceUpdateRequest(outcome=None)

    assert "outcome" not in omitted.model_fields_set
    assert "outcome" in cleared.model_fields_set


def test_update_experience_rejects_empty_body() -> None:
    with pytest.raises(ValidationError):
        ExperienceUpdateRequest()
