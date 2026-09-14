import pytest
from pydantic import ValidationError

from careerops.schemas.action_items import ActionItemCreateRequest, ActionItemUpdateRequest


def test_create_action_item_strips_title() -> None:
    payload = ActionItemCreateRequest(
        job_id="00000000-0000-0000-0000-000000000001",
        title="  Practice system design  ",
    )

    assert payload.title == "Practice system design"
    assert payload.source_evidence_match_id is None


@pytest.mark.parametrize("title", ["", "   "])
def test_create_action_item_rejects_blank_title(title: str) -> None:
    with pytest.raises(ValidationError):
        ActionItemCreateRequest(
            job_id="00000000-0000-0000-0000-000000000001",
            title=title,
        )


def test_update_action_item_rejects_empty_or_null_only_body() -> None:
    with pytest.raises(ValidationError):
        ActionItemUpdateRequest()
    with pytest.raises(ValidationError):
        ActionItemUpdateRequest(title=None)


def test_update_action_item_accepts_title_and_status() -> None:
    payload = ActionItemUpdateRequest(title="  Revised task  ", status="doing")

    assert payload.title == "Revised task"
    assert payload.status == "doing"
