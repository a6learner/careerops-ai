import hashlib
import re
from time import perf_counter
from typing import Protocol
from uuid import UUID

from careerops.domain.errors import JobNotFoundError, ParseRunNotFoundError
from careerops.domain.jobs import JobRecord
from careerops.domain.parse_runs import (
    PARSE_PROMPT_VERSION,
    ParsedRequirement,
    ParseRunRecord,
    RequirementCategory,
)


class JobReader(Protocol):
    async def get_job(self, user_id: UUID, job_id: UUID) -> JobRecord | None: ...


class ParseRunStore(Protocol):
    async def get_parse_run_by_idempotency_key(
        self,
        user_id: UUID,
        idempotency_key: str,
    ) -> ParseRunRecord | None: ...

    async def get_parse_run(
        self,
        user_id: UUID,
        job_id: UUID,
        parse_run_id: UUID,
    ) -> ParseRunRecord | None: ...

    async def create_succeeded_parse_run(
        self,
        user_id: UUID,
        job: JobRecord,
        idempotency_key: str,
        input_fingerprint: str,
        requirements: tuple[ParsedRequirement, ...],
        latency_ms: int,
    ) -> ParseRunRecord: ...

    async def commit(self) -> None: ...


class ParseRunService:
    def __init__(self, jobs: JobReader, parse_runs: ParseRunStore) -> None:
        self._jobs = jobs
        self._parse_runs = parse_runs

    async def submit_parse_run(
        self,
        user_id: UUID,
        job_id: UUID,
        idempotency_key: str,
    ) -> ParseRunRecord:
        existing = await self._parse_runs.get_parse_run_by_idempotency_key(
            user_id=user_id,
            idempotency_key=idempotency_key,
        )
        if existing is not None:
            return existing

        job = await self._jobs.get_job(user_id, job_id)
        if job is None:
            raise JobNotFoundError()

        started = perf_counter()
        requirements = parse_requirements_deterministically(job.raw_description)
        latency_ms = int((perf_counter() - started) * 1000)
        run = await self._parse_runs.create_succeeded_parse_run(
            user_id=user_id,
            job=job,
            idempotency_key=idempotency_key,
            input_fingerprint=compute_parse_input_fingerprint(job),
            requirements=requirements,
            latency_ms=latency_ms,
        )
        await self._parse_runs.commit()
        return run

    async def get_parse_run(
        self,
        user_id: UUID,
        job_id: UUID,
        parse_run_id: UUID,
    ) -> ParseRunRecord:
        job = await self._jobs.get_job(user_id, job_id)
        if job is None:
            raise JobNotFoundError()

        run = await self._parse_runs.get_parse_run(
            user_id=user_id,
            job_id=job_id,
            parse_run_id=parse_run_id,
        )
        if run is None:
            raise ParseRunNotFoundError()
        return run


def compute_parse_input_fingerprint(job: JobRecord) -> str:
    raw = f"{job.id}:{job.version}:{job.description_hash}:{PARSE_PROMPT_VERSION}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def parse_requirements_deterministically(raw_description: str) -> tuple[ParsedRequirement, ...]:
    requirements: list[ParsedRequirement] = []
    for match in re.finditer(r"[^.\n;•-][^.\n;]*", raw_description):
        text = " ".join(match.group(0).split())
        if len(text) < 4:
            continue
        requirements.append(
            ParsedRequirement(
                category=classify_requirement(text),
                text=text,
                skill_normalized=extract_skill(text),
                source_span_start=match.start(),
                source_span_end=match.end(),
            )
        )
    if requirements:
        return tuple(requirements)
    stripped = raw_description.strip()
    if stripped == "":
        return ()
    start = raw_description.index(stripped)
    return (
        ParsedRequirement(
            category=RequirementCategory.RESPONSIBILITY,
            text=stripped,
            skill_normalized=extract_skill(stripped),
            source_span_start=start,
            source_span_end=start + len(stripped),
        ),
    )


def classify_requirement(text: str) -> RequirementCategory:
    lowered = text.lower()
    if any(word in lowered for word in ("degree", "student", "bachelor", "master")):
        return RequirementCategory.EDUCATION
    if any(word in lowered for word in ("nice to have", "preferred", "plus", "bonus")):
        return RequirementCategory.NICE_TO_HAVE
    if any(word in lowered for word in ("required", "must", "experience", "proficient")):
        return RequirementCategory.MUST_HAVE
    return RequirementCategory.RESPONSIBILITY


def extract_skill(text: str) -> str | None:
    lowered = text.lower()
    known_skills = (
        "python",
        "fastapi",
        "postgresql",
        "redis",
        "sql",
        "docker",
        "kubernetes",
        "aws",
        "java",
        "typescript",
        "react",
    )
    for skill in known_skills:
        if skill in lowered:
            return skill
    return None
