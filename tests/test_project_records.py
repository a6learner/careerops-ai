import base64
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from careerops.domain.errors import InvalidCursorError
from careerops.domain.project_records import (
    CheckpointInput,
    EvidenceSource,
    ProjectInput,
    ProjectRecord,
    RecordStatus,
    ReviewInput,
)
from careerops.services.project_records import content_hash, decode_cursor, next_cursor


@pytest.mark.parametrize(
    "locator",
    [
        "../secret",
        "/etc/passwd",
        "C:\\secret",
        "https://host/data",
        ".env",
        ".env.local",
        "folder/.ssh/key",
        "folder/.aws/config",
        ".git/config",
    ],
)
def test_sources_reject_unsafe_locators(locator: str) -> None:
    with pytest.raises(ValidationError):
        EvidenceSource(kind="repository_excerpt", locator=locator, content="real", quote="real")


def test_sources_require_real_quotes_and_forbid_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        EvidenceSource(kind="user_note", locator="notes", content="actual", quote="invented")
    with pytest.raises(ValidationError):
        EvidenceSource.model_validate(
            {
                "kind": "test_output",
                "locator": "tests",
                "content": "passed",
                "quote": "passed",
                "server_verified": True,
            }
        )


def test_record_inputs_require_evidence_and_explicit_contribution() -> None:
    with pytest.raises(ValidationError):
        CheckpointInput(title="Stage", objective="Goal", changes="Code", host="manual", sources=())
    with pytest.raises(ValidationError):
        ReviewInput(status=RecordStatus.CONFIRMED, contribution_note="  ")
    with pytest.raises(ValidationError):
        ProjectInput(name="Bad\x00name", goal="Goal")
    assert ReviewInput(status=RecordStatus.WITHDRAWN).contribution_note == ""


def test_packet_utf8_size_is_bounded() -> None:
    source = EvidenceSource(
        kind="repository_excerpt",
        locator="src/example.py",
        content="数" * 8000,
        quote="数",
    )
    with pytest.raises(ValidationError):
        CheckpointInput(
            title="Stage",
            objective="Goal",
            changes="Code",
            host="manual",
            sources=(source,) * 8,
        )


def test_normalized_input_hash_is_stable_but_changes_with_content() -> None:
    first = ProjectInput(name=" Project ", goal="Goal")
    assert content_hash(first) == content_hash(ProjectInput(name="Project", goal="Goal"))
    assert content_hash(first) != content_hash(ProjectInput(name="Project", goal="New goal"))


def test_cursor_roundtrip_and_page_end() -> None:
    record = ProjectRecord(id=uuid4(), name="P", goal="G", created_at=datetime.now(UTC))
    cursor = next_cursor([record], 2, 1)
    assert cursor is not None
    decoded = decode_cursor(cursor)
    assert decoded is not None and decoded.id == record.id
    assert next_cursor([record], 1, 1) is None
    assert decode_cursor(None) is None


@pytest.mark.parametrize(
    "value",
    [
        "!!!!",
        "你好",
        base64.urlsafe_b64encode(b"{}").decode(),
        base64.urlsafe_b64encode(
            b'{"created_at":"2026-10-27T00:00:00","id":"00000000-0000-0000-0000-000000000000"}'
        ).decode(),
    ],
)
def test_invalid_cursor_is_a_domain_error(value: str) -> None:
    with pytest.raises(InvalidCursorError):
        decode_cursor(value)
