from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import json
import math
import platform
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import perf_counter_ns
from urllib.parse import quote
from uuid import UUID, uuid4

import httpx
from redis.asyncio import Redis
from sqlalchemy import select, text

from careerops.cache.dashboard import cache_key
from careerops.db.models import ActionItem, AnalysisRun, Experience, Job, JobRequirement, ParseRun
from careerops.db.session import create_session_factory

JOB_COUNT = 5_000
PAGE_LIMIT = 50
DEFAULT_WARMUPS = 25
DEFAULT_SAMPLES = 200
COLD_DASHBOARD_SAMPLES = 50


class BenchmarkError(RuntimeError):
    pass


@dataclass(frozen=True)
class Fixture:
    user_id: UUID
    token: str
    experience_id: UUID
    first_job_id: UUID
    parse_run_id: UUID
    analysis_run_id: UUID
    deep_cursor: str


@dataclass(frozen=True)
class TimingResult:
    name: str
    path: str
    warmups: int
    samples: int
    p50_ms: float
    p95_ms: float
    timings_ms: tuple[float, ...]


@dataclass(frozen=True)
class BenchmarkReport:
    measured_at: str
    run_id: str
    git_revision: str
    environment: str
    python: str
    job_count: int
    page_limit: int
    percentile_method: str
    cursor_traversal_unique_jobs: int
    cursor_insertion_stability: str
    indexed_plan: object
    unindexed_plan: object
    results: tuple[TimingResult, ...]
    limitations: tuple[str, ...]


def nearest_rank(values: Sequence[float], percentile: float) -> float:
    if not values:
        raise ValueError("At least one value is required.")
    if percentile <= 0 or percentile > 1:
        raise ValueError("Percentile must be in (0, 1].")
    ordered = sorted(values)
    return ordered[math.ceil(percentile * len(ordered)) - 1]


def plan_execution_time_ms(plan: object) -> float:
    if not isinstance(plan, list) or not plan or not isinstance(plan[0], dict):
        raise BenchmarkError("EXPLAIN output must contain one JSON plan.")
    value = plan[0].get("Execution Time")
    if not isinstance(value, int | float):
        raise BenchmarkError("EXPLAIN output is missing Execution Time.")
    return float(value)


def encode_cursor(updated_at: datetime, job_id: UUID) -> str:
    payload = {"updated_at": updated_at.isoformat(), "id": str(job_id)}
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode("ascii")


async def require_success(response: httpx.Response) -> object:
    if response.status_code != 200:
        raise BenchmarkError(
            f"{response.request.method} {response.request.url} returned {response.status_code}."
        )
    return response.json()


async def measure(
    client: httpx.AsyncClient,
    name: str,
    path: str,
    *,
    warmups: int = DEFAULT_WARMUPS,
    samples: int = DEFAULT_SAMPLES,
    before_each: Callable[[], Awaitable[None]] | None = None,
) -> TimingResult:
    for _ in range(warmups):
        if before_each is not None:
            await before_each()
        await require_success(await client.get(path))

    timings: list[float] = []
    for _ in range(samples):
        if before_each is not None:
            await before_each()
        started = perf_counter_ns()
        response = await client.get(path)
        elapsed_ms = (perf_counter_ns() - started) / 1_000_000
        await require_success(response)
        timings.append(round(elapsed_ms, 6))

    return TimingResult(
        name=name,
        path=path,
        warmups=warmups,
        samples=samples,
        p50_ms=round(nearest_rank(timings, 0.50), 3),
        p95_ms=round(nearest_rank(timings, 0.95), 3),
        timings_ms=tuple(timings),
    )


async def register_and_login(client: httpx.AsyncClient) -> tuple[UUID, str]:
    email = f"p111-{uuid4()}@example.com"
    password = "P1-11-synthetic-benchmark-password"
    registration = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )
    if registration.status_code != 201:
        raise BenchmarkError(f"Synthetic registration failed: {registration.status_code}.")
    user_id = UUID(str(registration.json()["id"]))
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    if login.status_code != 200:
        raise BenchmarkError(f"Synthetic login failed: {login.status_code}.")
    return user_id, str(login.json()["access_token"])


async def seed_fixture(
    database_url: str,
    client: httpx.AsyncClient,
) -> Fixture:
    user_id, token = await register_and_login(client)
    now = datetime.now(UTC)
    experience_id = uuid4()
    job_ids = [uuid4() for _ in range(JOB_COUNT)]
    parse_run_id = uuid4()
    analysis_run_id = uuid4()
    requirement_id = uuid4()
    session_factory = create_session_factory(database_url)
    try:
        async with session_factory() as session:
            session.add(
                Experience(
                    id=experience_id,
                    user_id=user_id,
                    title="Synthetic backend project",
                    kind="project",
                    description="Built a typed FastAPI service with PostgreSQL.",
                    skills=["Python", "FastAPI", "PostgreSQL"],
                    outcome="Synthetic benchmark fixture only.",
                    version=1,
                    content_hash=hashlib.sha256(b"synthetic-experience").hexdigest(),
                    created_at=now,
                    updated_at=now,
                )
            )
            session.add_all(
                [
                    Job(
                        id=job_id,
                        user_id=user_id,
                        company=f"Synthetic Company {index:04d}",
                        title=f"Backend Engineer {index:04d}",
                        raw_description="Python and PostgreSQL experience required.",
                        description_hash=hashlib.sha256(
                            f"synthetic-job-{index}".encode()
                        ).hexdigest(),
                        status="saved",
                        version=1,
                        created_at=now - timedelta(seconds=index),
                        updated_at=now - timedelta(seconds=index),
                    )
                    for index, job_id in enumerate(job_ids)
                ]
            )
            await session.flush()
            session.add_all(
                [
                    ActionItem(
                        id=uuid4(),
                        user_id=user_id,
                        job_id=job_ids[index],
                        title=f"Synthetic action item {index:03d}",
                        status="todo",
                        version=1,
                        idempotency_key=f"p111-action-{index:03d}",
                        request_fingerprint=hashlib.sha256(
                            f"p111-action-{index:03d}".encode()
                        ).hexdigest(),
                        created_at=now - timedelta(seconds=index),
                        updated_at=now - timedelta(seconds=index),
                    )
                    for index in range(100)
                ]
            )
            session.add(
                ParseRun(
                    id=parse_run_id,
                    user_id=user_id,
                    job_id=job_ids[0],
                    status="succeeded",
                    idempotency_key="p111-parse",
                    input_fingerprint="a" * 64,
                    input_text="Python and PostgreSQL experience required.",
                    model_name="fake-requirement-parser",
                    prompt_version="synthetic-benchmark",
                    attempt=1,
                    latency_ms=0,
                    input_tokens=0,
                    output_tokens=0,
                    started_at=now,
                    finished_at=now,
                    created_at=now,
                )
            )
            await session.flush()
            session.add(
                JobRequirement(
                    id=requirement_id,
                    job_id=job_ids[0],
                    parse_run_id=parse_run_id,
                    category="must_have",
                    text="Python experience required",
                    skill_normalized="Python",
                    source_span_start=0,
                    source_span_end=26,
                )
            )
            session.add(
                AnalysisRun(
                    id=analysis_run_id,
                    user_id=user_id,
                    job_id=job_ids[0],
                    parse_run_id=parse_run_id,
                    status="succeeded",
                    idempotency_key="p111-analysis",
                    input_fingerprint="b" * 64,
                    model_name="fake-evidence-matcher",
                    prompt_version="synthetic-benchmark",
                    attempt=1,
                    validation_failure_count=0,
                    latency_ms=0,
                    input_tokens=0,
                    output_tokens=0,
                    started_at=now,
                    finished_at=now,
                    created_at=now,
                )
            )
            await session.commit()

            deep_job = await session.scalar(
                select(Job)
                .where(Job.user_id == user_id, Job.status == "saved")
                .order_by(Job.updated_at.desc(), Job.id.desc())
                .offset(JOB_COUNT - PAGE_LIMIT)
                .limit(1)
            )
            if deep_job is None:
                raise BenchmarkError("Unable to resolve the deep cursor fixture.")
            deep_cursor = encode_cursor(deep_job.updated_at, deep_job.id)
    finally:
        await session_factory.kw["bind"].dispose()
    return Fixture(
        user_id=user_id,
        token=token,
        experience_id=experience_id,
        first_job_id=job_ids[0],
        parse_run_id=parse_run_id,
        analysis_run_id=analysis_run_id,
        deep_cursor=deep_cursor,
    )


async def verify_cursor_stability(
    database_url: str,
    client: httpx.AsyncClient,
    fixture: Fixture,
) -> int:
    seen: set[str] = set()
    cursor: str | None = None
    inserted_job_id = uuid4()
    for page_number in range(JOB_COUNT // PAGE_LIMIT):
        path = f"/api/v1/jobs?status=saved&limit={PAGE_LIMIT}"
        if cursor is not None:
            path += f"&cursor={quote(cursor, safe='')}"
        payload = await require_success(await client.get(path))
        if not isinstance(payload, dict):
            raise BenchmarkError("Job list response must be an object.")
        items = payload.get("items")
        if not isinstance(items, list):
            raise BenchmarkError("Job list response must contain items.")
        ids = [str(item["id"]) for item in items if isinstance(item, dict)]
        if len(ids) != len(items) or seen.intersection(ids):
            raise BenchmarkError("Cursor traversal returned an invalid or duplicate row.")
        seen.update(ids)
        cursor_value = payload.get("next_cursor")
        cursor = str(cursor_value) if cursor_value is not None else None
        if page_number == 0:
            session_factory = create_session_factory(database_url)
            try:
                async with session_factory() as session:
                    now = datetime.now(UTC) + timedelta(seconds=1)
                    session.add(
                        Job(
                            id=inserted_job_id,
                            user_id=fixture.user_id,
                            company="Synthetic insertion probe",
                            title="Newer cursor probe",
                            raw_description="Synthetic insertion stability probe.",
                            description_hash=hashlib.sha256(b"cursor-probe").hexdigest(),
                            status="saved",
                            version=1,
                            created_at=now,
                            updated_at=now,
                        )
                    )
                    await session.commit()
            finally:
                await session_factory.kw["bind"].dispose()
    if len(seen) != JOB_COUNT or str(inserted_job_id) in seen:
        raise BenchmarkError("Cursor insertion stability verification failed.")

    session_factory = create_session_factory(database_url)
    try:
        async with session_factory() as session:
            inserted = await session.get(Job, inserted_job_id)
            if inserted is not None:
                await session.delete(inserted)
                await session.commit()
    finally:
        await session_factory.kw["bind"].dispose()
    return len(seen)


async def explain_deep_query(database_url: str, fixture: Fixture) -> object:
    cursor = json.loads(base64.urlsafe_b64decode(fixture.deep_cursor.encode()).decode())
    session_factory = create_session_factory(database_url)
    try:
        async with session_factory() as session:
            result = await session.scalar(
                text(
                    "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) "
                    "SELECT * FROM jobs WHERE user_id = :user_id AND deleted_at IS NULL "
                    "AND status = 'saved' AND (updated_at < :updated_at OR "
                    "(updated_at = :updated_at AND id < :job_id)) "
                    "ORDER BY updated_at DESC, id DESC LIMIT 51"
                ),
                {
                    "user_id": fixture.user_id,
                    "updated_at": datetime.fromisoformat(str(cursor["updated_at"])),
                    "job_id": UUID(str(cursor["id"])),
                },
            )
            return result
    finally:
        await session_factory.kw["bind"].dispose()


async def drop_job_index(database_url: str) -> None:
    session_factory = create_session_factory(database_url)
    try:
        async with session_factory() as session:
            await session.execute(text("DROP INDEX idx_jobs_user_status_updated"))
            await session.commit()
    finally:
        await session_factory.kw["bind"].dispose()


async def run_benchmark(
    *,
    base_url: str,
    database_url: str,
    redis_url: str,
    run_id: str,
    git_revision: str,
) -> BenchmarkReport:
    async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as unauthenticated:
        fixture = await seed_fixture(database_url, unauthenticated)

    headers = {"Authorization": f"Bearer {fixture.token}"}
    redis_client = Redis.from_url(redis_url, decode_responses=True)
    try:
        async with httpx.AsyncClient(base_url=base_url, headers=headers, timeout=10.0) as client:
            traversed = await verify_cursor_stability(database_url, client, fixture)
            deep_path = (
                f"/api/v1/jobs?status=saved&limit={PAGE_LIMIT}"
                f"&cursor={quote(fixture.deep_cursor, safe='')}"
            )
            results = [
                await measure(client, "auth_me", "/api/v1/auth/me"),
                await measure(client, "experiences_list", "/api/v1/experiences"),
                await measure(
                    client,
                    "experience_detail",
                    f"/api/v1/experiences/{fixture.experience_id}",
                ),
                await measure(
                    client,
                    "jobs_first_page",
                    f"/api/v1/jobs?status=saved&limit={PAGE_LIMIT}",
                ),
                await measure(client, "jobs_deep_cursor_indexed", deep_path),
                await measure(client, "job_detail", f"/api/v1/jobs/{fixture.first_job_id}"),
                await measure(
                    client,
                    "parse_run_detail",
                    f"/api/v1/jobs/{fixture.first_job_id}/parse-runs/{fixture.parse_run_id}",
                ),
                await measure(
                    client,
                    "analysis_run_detail",
                    f"/api/v1/jobs/{fixture.first_job_id}/analysis-runs/{fixture.analysis_run_id}",
                ),
                await measure(
                    client,
                    "action_items_first_page",
                    f"/api/v1/action-items?status=todo&limit={PAGE_LIMIT}",
                ),
            ]

            async def invalidate_dashboard() -> None:
                await redis_client.delete(cache_key(fixture.user_id))

            results.append(
                await measure(
                    client,
                    "dashboard_cold",
                    "/api/v1/dashboard/summary",
                    warmups=0,
                    samples=COLD_DASHBOARD_SAMPLES,
                    before_each=invalidate_dashboard,
                )
            )
            results.append(
                await measure(client, "dashboard_warm", "/api/v1/dashboard/summary")
            )
            indexed_plan = await explain_deep_query(database_url, fixture)
            await drop_job_index(database_url)
            unindexed_plan = await explain_deep_query(database_url, fixture)
            results.append(await measure(client, "jobs_deep_cursor_unindexed", deep_path))
    finally:
        await redis_client.aclose()

    return BenchmarkReport(
        measured_at=datetime.now(UTC).isoformat(),
        run_id=run_id,
        git_revision=git_revision,
        environment="isolated local Docker PostgreSQL 16 + pgvector and Redis 7",
        python=platform.python_version(),
        job_count=JOB_COUNT,
        page_limit=PAGE_LIMIT,
        percentile_method="nearest-rank: sorted[ceil(p * n) - 1]",
        cursor_traversal_unique_jobs=traversed,
        cursor_insertion_stability="passed",
        indexed_plan=indexed_plan,
        unindexed_plan=unindexed_plan,
        results=tuple(results),
        limitations=(
            "Single-machine sequential local measurements are not production capacity evidence.",
            "The fixture is synthetic and contains no real user data.",
            "The benchmark measures API-observed latency and does not isolate network, "
            "serialization, or database time.",
            "Dropping the Job index occurs only in the disposable benchmark database.",
        ),
    )


def write_report(report: BenchmarkReport, json_path: Path, markdown_path: Path) -> None:
    if json_path.exists() or markdown_path.exists():
        raise BenchmarkError("Refusing to overwrite an existing benchmark artifact.")
    json_path.write_text(
        json.dumps(asdict(report), indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    rows = "\n".join(
        f"| `{result.name}` | {result.warmups} | {result.samples} | "
        f"{result.p50_ms:.3f} | {result.p95_ms:.3f} |"
        for result in report.results
    )
    indexed = next(
        result for result in report.results if result.name == "jobs_deep_cursor_indexed"
    )
    unindexed = next(
        result for result in report.results if result.name == "jobs_deep_cursor_unindexed"
    )
    indexed_plan_ms = plan_execution_time_ms(report.indexed_plan)
    unindexed_plan_ms = plan_execution_time_ms(report.unindexed_plan)
    markdown_path.write_text(
        "# Read Endpoint Performance — 2026-10-10\n\n"
        "## Scope\n\n"
        "Local synthetic evidence for the main authenticated read endpoints. This is not "
        "production latency, throughput, availability, or capacity evidence.\n\n"
        f"- Git revision: `{report.git_revision}`\n"
        f"- Run ID: `{report.run_id}`\n"
        f"- Jobs: {report.job_count:,}\n"
        f"- Cursor traversal: {report.cursor_traversal_unique_jobs:,} unique original Jobs\n"
        f"- Insertion stability: {report.cursor_insertion_stability}\n"
        f"- Percentiles: {report.percentile_method}\n\n"
        "## Results\n\n"
        "| Scenario | Warmups | Samples | P50 ms | P95 ms |\n"
        "|---|---:|---:|---:|---:|\n"
        f"{rows}\n\n"
        "The raw JSON artifact preserves every timing sample and both indexed and "
        "unindexed `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)` plans.\n\n"
        "## Interpretation\n\n"
        "The indexed deep-cursor request measured "
        f"{indexed.p50_ms:.3f} ms P50 / {indexed.p95_ms:.3f} ms P95; after the "
        "Job index was dropped in the disposable database it measured "
        f"{unindexed.p50_ms:.3f} ms P50 / {unindexed.p95_ms:.3f} ms P95. The "
        f"captured database-only execution times were {indexed_plan_ms:.3f} ms "
        f"indexed and {unindexed_plan_ms:.3f} ms unindexed. A changed plan or "
        "small API-observed difference at 5,000 rows does not by itself prove a "
        "database execution-time improvement.\n\n"
        "## Limitations\n\n"
        + "\n".join(f"- {limitation}" for limitation in report.limitations)
        + "\n",
        encoding="utf-8",
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Measure isolated P1-11 read endpoints.")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--redis-url", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--git-revision", required=True)
    parser.add_argument("--json-output", type=Path, required=True)
    parser.add_argument("--markdown-output", type=Path, required=True)
    args = parser.parse_args(argv)
    report = asyncio.run(
        run_benchmark(
            base_url=str(args.base_url),
            database_url=str(args.database_url),
            redis_url=str(args.redis_url),
            run_id=str(args.run_id),
            git_revision=str(args.git_revision),
        )
    )
    write_report(report, args.json_output, args.markdown_output)
    print(json.dumps(asdict(report), indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
