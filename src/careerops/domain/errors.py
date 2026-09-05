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
