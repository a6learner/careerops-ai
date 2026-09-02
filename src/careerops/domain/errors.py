class DuplicateEmailError(Exception):
    def __init__(self, email: str) -> None:
        super().__init__("Email is already registered.")
        self.email = email


class InvalidCredentialsError(Exception):
    def __init__(self) -> None:
        super().__init__("Invalid email or password.")
