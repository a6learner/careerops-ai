class DuplicateEmailError(Exception):
    def __init__(self, email: str) -> None:
        super().__init__("Email is already registered.")
        self.email = email
