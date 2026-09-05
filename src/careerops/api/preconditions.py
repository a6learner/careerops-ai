from careerops.domain.errors import MissingIfMatchHeaderError


def parse_if_match(value: str | None) -> int:
    if value is None:
        raise MissingIfMatchHeaderError()
    normalized = value.strip().strip('"')
    if not normalized.isdecimal():
        raise MissingIfMatchHeaderError()
    version = int(normalized)
    if version < 1:
        raise MissingIfMatchHeaderError()
    return version
