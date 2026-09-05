from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from careerops.db.models import Experience
from careerops.domain.experiences import (
    ExperienceCreate,
    ExperienceKind,
    ExperienceRecord,
    ExperienceUpdate,
)


class ExperienceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_experience(
        self,
        payload: ExperienceCreate,
        content_hash: str,
    ) -> ExperienceRecord:
        experience = Experience(
            user_id=payload.user_id,
            title=payload.title,
            kind=payload.kind.value,
            description=payload.description,
            skills=list(payload.skills),
            outcome=payload.outcome,
            content_hash=content_hash,
        )
        self._session.add(experience)
        await self._session.flush()
        await self._session.refresh(experience)
        return to_record(experience)

    async def list_experiences(self, user_id: UUID) -> list[ExperienceRecord]:
        result = await self._session.execute(
            select(Experience)
            .where(Experience.user_id == user_id, Experience.deleted_at.is_(None))
            .order_by(Experience.updated_at.desc(), Experience.id.desc())
        )
        return [to_record(experience) for experience in result.scalars().all()]

    async def get_experience(self, user_id: UUID, experience_id: UUID) -> ExperienceRecord | None:
        result = await self._session.execute(
            select(Experience).where(
                Experience.id == experience_id,
                Experience.user_id == user_id,
                Experience.deleted_at.is_(None),
            )
        )
        experience = result.scalar_one_or_none()
        if experience is None:
            return None
        return to_record(experience)

    async def update_experience(
        self,
        user_id: UUID,
        experience_id: UUID,
        expected_version: int,
        payload: ExperienceUpdate,
        content_hash: str,
    ) -> ExperienceRecord | None:
        values: dict[str, object] = {
            "version": expected_version + 1,
            "content_hash": content_hash,
            "updated_at": datetime.now(UTC),
            "embedding": None,
        }
        if payload.title is not None:
            values["title"] = payload.title
        if payload.kind is not None:
            values["kind"] = payload.kind.value
        if payload.description is not None:
            values["description"] = payload.description
        if payload.skills is not None:
            values["skills"] = list(payload.skills)
        if payload.clear_outcome:
            values["outcome"] = None
        elif payload.outcome is not None:
            values["outcome"] = payload.outcome

        result = await self._session.execute(
            update(Experience)
            .where(
                Experience.id == experience_id,
                Experience.user_id == user_id,
                Experience.deleted_at.is_(None),
                Experience.version == expected_version,
            )
            .values(**values)
            .returning(Experience)
        )
        experience = result.scalar_one_or_none()
        if experience is None:
            return None
        return to_record(experience)

    async def soft_delete_experience(self, user_id: UUID, experience_id: UUID) -> bool:
        result = await self._session.execute(
            update(Experience)
            .where(
                Experience.id == experience_id,
                Experience.user_id == user_id,
                Experience.deleted_at.is_(None),
            )
            .values(deleted_at=datetime.now(UTC), updated_at=datetime.now(UTC))
            .returning(Experience.id)
        )
        return result.scalar_one_or_none() is not None

    async def commit(self) -> None:
        await self._session.commit()


def to_record(experience: Experience) -> ExperienceRecord:
    return ExperienceRecord(
        id=experience.id,
        user_id=experience.user_id,
        title=experience.title,
        kind=ExperienceKind(experience.kind),
        description=experience.description,
        skills=tuple(experience.skills),
        outcome=experience.outcome,
        version=experience.version,
        content_hash=experience.content_hash,
        created_at=experience.created_at,
        updated_at=experience.updated_at,
    )
