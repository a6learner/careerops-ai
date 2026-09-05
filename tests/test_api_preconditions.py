import pytest

from careerops.api.preconditions import parse_if_match
from careerops.domain.errors import MissingIfMatchHeaderError


@pytest.mark.parametrize("value", [None, "", " ", "abc", "0"])
def test_parse_if_match_rejects_missing_or_malformed_versions(value: str | None) -> None:
    with pytest.raises(MissingIfMatchHeaderError):
        parse_if_match(value)


def test_parse_if_match_accepts_plain_or_quoted_positive_versions() -> None:
    assert parse_if_match("3") == 3
    assert parse_if_match('"3"') == 3
