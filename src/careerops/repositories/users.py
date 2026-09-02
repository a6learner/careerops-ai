from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from careerops.db.models import User
from careerops.domain.errors import DuplicateEmailError
from careerops.domain.users import UserAccount


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_user(self, email: str, password_hash: str) -> UserAccount:
        user = User(email=email, password_hash=password_hash)
        self._session.add(user)
        try:
            await self._session.flush()
            await self._session.refresh(user)
        except IntegrityError as exc:
            await self._session.rollback()
            raise DuplicateEmailError(email) from exc

        return UserAccount(id=user.id, email=user.email, created_at=user.created_at)

    async def commit(self) -> None:
        await self._session.commit()
