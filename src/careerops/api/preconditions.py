from careerops.domain.errors import MissingIdempotencyKeyError, MissingIfMatchHeaderError

MAX_IDEMPOTENCY_KEY_LENGTH = 255


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


def parse_idempotency_key(value: str | None) -> str:
    if value is None:
        raise MissingIdempotencyKeyError()
    normalized = value.strip()
    if normalized == "":
        raise MissingIdempotencyKeyError()
    return normalized
