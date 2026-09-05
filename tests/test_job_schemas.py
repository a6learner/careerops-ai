from datetime import date

import pytest
from pydantic import ValidationError

from careerops.domain.jobs import JobStatus
from careerops.schemas.jobs import JobCreateRequest, JobUpdateRequest


def test_create_job_normalizes_required_and_optional_text() -> None:
    payload = JobCreateRequest(
        company="  OpenAI  ",
        title="  Backend Engineer Intern  ",
        raw_description="  Build reliable APIs.  ",
        source_url="  https://example.com/job  ",
        location="  San Francisco  ",
        deadline=date(2027, 1, 15),
    )

    assert payload.company == "OpenAI"
    assert payload.title == "Backend Engineer Intern"
    assert payload.raw_description == "Build reliable APIs."
    assert payload.source_url == "https://example.com/job"
    assert payload.location == "San Francisco"
    assert payload.status == JobStatus.SAVED


def test_create_job_allows_unclear_optional_fields_to_be_missing() -> None:
    payload = JobCreateRequest(
        company="OpenAI",
        title="Backend Engineer Intern",
        raw_description="Build reliable APIs.",
    )

    assert payload.source_url is None
    assert payload.location is None
    assert payload.deadline is None


def test_create_job_rejects_blank_required_text() -> None:
    with pytest.raises(ValidationError):
        JobCreateRequest(company=" ", title="Backend", raw_description="Build APIs.")


def test_update_job_can_distinguish_cleared_optional_fields_from_omitted_fields() -> None:
    omitted = JobUpdateRequest(title="Backend Engineer Intern")
    cleared = JobUpdateRequest(source_url=None, location=None, deadline=None)

    assert "source_url" not in omitted.model_fields_set
    assert "location" not in omitted.model_fields_set
    assert "deadline" not in omitted.model_fields_set
    assert "source_url" in cleared.model_fields_set
    assert "location" in cleared.model_fields_set
    assert "deadline" in cleared.model_fields_set


def test_update_job_rejects_empty_body() -> None:
    with pytest.raises(ValidationError):
        JobUpdateRequest()
