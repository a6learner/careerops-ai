class DuplicateEmailError(Exception):
    def __init__(self, email: str) -> None:
        super().__init__("Email is already registered.")
        self.email = email


class InvalidCredentialsError(Exception):
    def __init__(self) -> None:
        super().__init__("Invalid email or password.")


class MissingTokenError(Exception):
    def __init__(self) -> None:
        super().__init__("Missing bearer token.")


class InvalidTokenError(Exception):
    def __init__(self) -> None:
        super().__init__("Invalid bearer token.")


class ExpiredTokenError(Exception):
    def __init__(self) -> None:
        super().__init__("Expired bearer token.")


class ExperienceNotFoundError(Exception):
    def __init__(self) -> None:
        super().__init__("Experience was not found.")


class ExperienceVersionConflictError(Exception):
    def __init__(self, current_version: int) -> None:
        super().__init__("Experience version conflict.")
        self.current_version = current_version


class EmbeddingRunDispatchError(Exception):
    def __init__(self) -> None:
        super().__init__("Embedding run queue is unavailable.")


class EmbeddingProviderError(Exception):
    def __init__(self) -> None:
        super().__init__("Embedding provider failed.")


class EmbeddingOutputValidationError(Exception):
    def __init__(self) -> None:
        super().__init__("Embedding provider returned invalid output.")


class MissingIfMatchHeaderError(Exception):
    def __init__(self) -> None:
        super().__init__("Missing If-Match header.")


class JobNotFoundError(Exception):
    def __init__(self) -> None:
        super().__init__("Job was not found.")


class JobVersionConflictError(Exception):
    def __init__(self, current_version: int) -> None:
        super().__init__("Job version conflict.")
        self.current_version = current_version


class InvalidCursorError(Exception):
    def __init__(self) -> None:
        super().__init__("Invalid pagination cursor.")


class MissingIdempotencyKeyError(Exception):
    def __init__(self) -> None:
        super().__init__("Missing Idempotency-Key header.")


class IdempotencyKeyConflictError(Exception):
    def __init__(self) -> None:
        super().__init__("Idempotency key was already used with different input.")


class ParseRunNotFoundError(Exception):
    def __init__(self) -> None:
        super().__init__("Parse run was not found.")


class ParseRunDispatchError(Exception):
    def __init__(self) -> None:
        super().__init__("Parse run queue is unavailable.")


class RequirementParserError(Exception):
    def __init__(self) -> None:
        super().__init__("Requirement parser failed.")


class ParserOutputValidationError(Exception):
    def __init__(self) -> None:
        super().__init__("Requirement parser returned invalid output.")


class AnalysisRunNotFoundError(Exception):
    def __init__(self) -> None:
        super().__init__("Analysis run was not found.")


class AnalysisRunDispatchError(Exception):
    def __init__(self) -> None:
        super().__init__("Analysis run queue is unavailable.")


class ParseRunNotReadyError(Exception):
    def __init__(self) -> None:
        super().__init__("Parse run is not ready for analysis.")


class NoActiveExperiencesError(Exception):
    def __init__(self) -> None:
        super().__init__("At least one active experience is required.")


class EvidenceMatcherError(Exception):
    def __init__(self) -> None:
        super().__init__("Evidence matcher failed.")


class MatcherOutputValidationError(Exception):
    def __init__(self) -> None:
        super().__init__("Evidence matcher returned invalid output.")


class ActionItemNotFoundError(Exception):
    def __init__(self) -> None:
        super().__init__("Action item was not found.")


class ActionItemVersionConflictError(Exception):
    def __init__(self, current_version: int) -> None:
        super().__init__("Action item version conflict.")
        self.current_version = current_version


class ActionItemSourceNotFoundError(Exception):
    def __init__(self) -> None:
        super().__init__("Action item source was not found.")


class ActionItemSourceNotActionableError(Exception):
    def __init__(self) -> None:
        super().__init__("Action item source is not actionable.")
