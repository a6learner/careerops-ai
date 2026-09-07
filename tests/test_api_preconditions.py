import pytest

from careerops.api.preconditions import parse_idempotency_key, parse_if_match
from careerops.domain.errors import MissingIdempotencyKeyError, MissingIfMatchHeaderError


@pytest.mark.parametrize("value", [None, "", " ", "abc", "0"])
def test_parse_if_match_rejects_missing_or_malformed_versions(value: str | None) -> None:
    with pytest.raises(MissingIfMatchHeaderError):
        parse_if_match(value)


def test_parse_if_match_accepts_plain_or_quoted_positive_versions() -> None:
    assert parse_if_match("3") == 3
    assert parse_if_match('"3"') == 3


@pytest.mark.parametrize("value", [None, "", " "])
def test_parse_idempotency_key_rejects_missing_or_blank_values(value: str | None) -> None:
    with pytest.raises(MissingIdempotencyKeyError):
        parse_idempotency_key(value)


def test_parse_idempotency_key_strips_valid_values() -> None:
    assert parse_idempotency_key(" parse-key ") == "parse-key"
