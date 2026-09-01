from dataclasses import dataclass

from pwdlib import PasswordHash


@dataclass(frozen=True)
class PasswordHasher:
    _password_hash: PasswordHash

    @classmethod
    def recommended(cls) -> "PasswordHasher":
        return cls(_password_hash=PasswordHash.recommended())

    def hash(self, plain_password: str) -> str:
        return self._password_hash.hash(plain_password)

    def verify(self, plain_password: str, password_hash: str) -> bool:
        return self._password_hash.verify(plain_password, password_hash)
