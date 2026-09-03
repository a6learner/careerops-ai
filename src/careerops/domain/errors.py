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
