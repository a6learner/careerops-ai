import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Final
from uuid import UUID

from redis import Redis
from sqlalchemy import func, select

from careerops.db.models import (
    AnalysisRun,
    EvidenceMatch,
    Experience,
    ExperienceEmbeddingRun,
    Job,
    JobRequirement,
    ParseRun,
    User,
)
from careerops.db.session import create_session_factory
from careerops.domain.analysis_runs import ANALYSIS_PROMPT_VERSION, FAKE_ANALYSIS_MODEL_NAME
from careerops.domain.embeddings import EMBEDDING_INPUT_VERSION, FAKE_EMBEDDING_MODEL_NAME
from careerops.domain.experiences import ExperienceCreate, ExperienceKind
from careerops.domain.jobs import JobCreate, JobStatus
from careerops.domain.parse_runs import FAKE_PARSE_MODEL_NAME, PARSE_PROMPT_VERSION
from careerops.repositories.experiences import ExperienceRepository
from careerops.services.analysis_runs import compute_analysis_fingerprint
from careerops.services.experiences import compute_experience_content_hash
from careerops.services.jobs import compute_description_hash

from .backup_restore_drill import (
    RUN_ID_PATTERN,
    DrillSafetyError,
    ensure_no_linked_existing_components,
)
from .backup_restore_execution import (
    ALEMBIC_HEAD,
    DATABASE_URL_PREFIX,
    POSTGRES_USER,
    REPOSITORY_ROOT,
    docker_postgres_command,
    run_text,
)

EXECUTION_GATE: Final = "CAREEROPS_RUN_WORKER_RECOVERY_DRILL"
DATABASE_PREFIX: Final = "careerops_p18b_"
DATABASE_COMMENT_PREFIX: Final = "careerops-p1-8b:"
REDIS_CONTAINER_PREFIX: Final = "careerops-p18b-"
REDIS_IMAGE: Final = "redis:7-alpine"
DATABASE_IDENTIFIER_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,62}$")

USER_ID: Final = UUID("82000000-0000-4000-8000-000000000001")
READY_EXPERIENCE_ID: Final = UUID("82000000-0000-4000-8000-000000000002")
RECOVERED_EXPERIENCE_ID: Final = UUID("82000000-0000-4000-8000-000000000003")
READY_EMBEDDING_RUN_ID: Final = UUID("82000000-0000-4000-8000-000000000004")
PARSE_JOB_ID: Final = UUID("82000000-0000-4000-8000-000000000005")
STALE_PARSE_RUN_ID: Final = UUID("82000000-0000-4000-8000-000000000006")
ANALYSIS_JOB_ID: Final = UUID("82000000-0000-4000-8000-000000000007")
READY_PARSE_RUN_ID: Final = UUID("82000000-0000-4000-8000-000000000008")
REQUIREMENT_ID: Final = UUID("82000000-0000-4000-8000-000000000009")
STALE_ANALYSIS_RUN_ID: Final = UUID("82000000-0000-4000-8000-00000000000a")


class WorkerRecoveryDrillError(RuntimeError):
    pass


@dataclass(frozen=True)
class WorkerRecoveryResources:
    run_id: str
    database_name: str
    database_comment: str
    redis_container_name: str
    artifact_directory: Path
    worker_log_path: Path


@dataclass(frozen=True)
class WorkerRecoveryDrillResult:
    run_id: str
    recovery_summary: object
    parse_attempt: int
    analysis_attempt: int
    embedding_attempt: int
    parse_requirement_count: int
    evidence_match_count: int
    total_elapsed_ms: int
    database_cleaned: bool
    redis_cleaned: bool
    synthetic_only: bool
    provider_calls: bool


def build_resources(run_id: str, *, temp_root: Path | None = None) -> WorkerRecoveryResources:
    validate_run_id(run_id)
    suffix = run_id.replace("_", "-")
    database_name = f"{DATABASE_PREFIX}{run_id}"
    validate_database_name(database_name)
    redis_container_name = f"{REDIS_CONTAINER_PREFIX}{suffix}"
    root = (temp_root or Path(tempfile.gettempdir())).resolve(strict=True)
    artifact_root = (root / "careerops-ai" / "p1-8b").resolve(strict=False)
    if not artifact_root.is_relative_to(root):
        raise WorkerRecoveryDrillError("Artifact root escaped the system temporary directory.")
    artifact_directory = (artifact_root / run_id).resolve(strict=False)
    if not artifact_directory.is_relative_to(artifact_root):
        raise WorkerRecoveryDrillError("Artifact directory escaped the fixed drill root.")
    ensure_no_linked_existing_components(artifact_directory, root)
    return WorkerRecoveryResources(
        run_id=run_id,
        database_name=database_name,
        database_comment=f"{DATABASE_COMMENT_PREFIX}{run_id}",
        redis_container_name=redis_container_name,
        artifact_directory=artifact_directory,
        worker_log_path=artifact_directory / "worker.log",
    )


def validate_run_id(run_id: str) -> None:
    if RUN_ID_PATTERN.fullmatch(run_id) is None:
        raise WorkerRecoveryDrillError("Run ID must use the P1 drill format.")


def validate_database_name(database_name: str) -> None:
    if (
        DATABASE_IDENTIFIER_PATTERN.fullmatch(database_name) is None
        or not database_name.startswith(DATABASE_PREFIX)
    ):
        raise WorkerRecoveryDrillError("Database is outside the P1-8b temporary namespace.")


def render_plan(resources: WorkerRecoveryResources) -> str:
    return json.dumps(
        {
            "mode": "dry_run",
            "mutates_state": False,
            "provider_calls": False,
            "resources": {
                **asdict(resources),
                "artifact_directory": str(resources.artifact_directory),
                "worker_log_path": str(resources.worker_log_path),
            },
            "stages": [
                "create sentinel-protected temporary PostgreSQL database",
                "start one labeled temporary Redis container",
                "migrate and seed synthetic stale work",
                "run one fake-only recovery cycle",
                "start one fake-only worker and verify completion",
                "verify sentinels and clean exact temporary resources",
            ],
        },
        indent=2,
        sort_keys=True,
    )


def execute_drill(run_id: str, *, confirmation_run_id: str) -> WorkerRecoveryDrillResult:
    require_execution_gate()
    resources = build_resources(run_id)
    if confirmation_run_id != run_id:
        raise WorkerRecoveryDrillError("Cleanup confirmation must equal the run ID.")
    preflight(resources)
    started = time.perf_counter()
    resources.artifact_directory.mkdir(parents=True, exist_ok=False)
    worker: subprocess.Popen[str] | None = None
    redis_started = False
    database_created = False
    completed = False
    try:
        create_database(resources)
        database_created = True
        upgrade_database(resources)
        redis_url = start_redis(resources)
        redis_started = True
        environment = fake_environment(resources, redis_url)
        asyncio.run(seed_synthetic_work(database_url(resources)))
        recovery_summary = run_recovery_cycle(environment)
        worker = start_worker(environment, resources.worker_log_path)
        verification = asyncio.run(wait_for_completion(database_url(resources), worker))
        completed = True
        return WorkerRecoveryDrillResult(
            run_id=run_id,
            recovery_summary=recovery_summary,
            parse_attempt=verification.parse_attempt,
            analysis_attempt=verification.analysis_attempt,
            embedding_attempt=verification.embedding_attempt,
            parse_requirement_count=verification.parse_requirement_count,
            evidence_match_count=verification.evidence_match_count,
            total_elapsed_ms=round((time.perf_counter() - started) * 1_000),
            database_cleaned=True,
            redis_cleaned=True,
            synthetic_only=True,
            provider_calls=False,
        )
    finally:
        if worker is not None:
            stop_worker(worker)
        cleanup_errors: list[str] = []
        if redis_started:
            try:
                stop_redis(resources)
            except Exception as exc:
                cleanup_errors.append(type(exc).__name__)
        if database_created:
            try:
                drop_database(resources)
            except Exception as exc:
                cleanup_errors.append(type(exc).__name__)
        if completed and not cleanup_errors:
            resources.worker_log_path.unlink(missing_ok=True)
            resources.artifact_directory.rmdir()
        if cleanup_errors:
            raise WorkerRecoveryDrillError(
                "Temporary resource cleanup failed: " + ", ".join(cleanup_errors)
            )


@dataclass(frozen=True)
class VerificationResult:
    parse_attempt: int
    analysis_attempt: int
    embedding_attempt: int
    parse_requirement_count: int
    evidence_match_count: int


def require_execution_gate() -> None:
    if os.getenv(EXECUTION_GATE) != "1":
        raise WorkerRecoveryDrillError(f"Set invocation-local {EXECUTION_GATE}=1.")


def preflight(resources: WorkerRecoveryResources) -> None:
    services = set(
        run_text(
            ("docker", "compose", "ps", "--services", "--status", "running")
        ).split()
    )
    if "postgres" not in services:
        raise WorkerRecoveryDrillError("Compose PostgreSQL is not running.")
    if database_exists(resources):
        raise WorkerRecoveryDrillError("Temporary database already exists.")
    container_names = run_text(("docker", "ps", "-a", "--format", "{{.Names}}")).splitlines()
    if resources.redis_container_name in container_names:
        raise WorkerRecoveryDrillError("Temporary Redis container already exists.")
    if resources.artifact_directory.exists():
        raise WorkerRecoveryDrillError("Artifact directory already exists.")
    run_text(("docker", "image", "inspect", REDIS_IMAGE, "--format", "{{.Id}}"))


def create_database(resources: WorkerRecoveryResources) -> None:
    quoted = quote_database(resources.database_name)
    postgres_sql(f"CREATE DATABASE {quoted} OWNER {POSTGRES_USER} TEMPLATE template0;")
    postgres_sql(f"COMMENT ON DATABASE {quoted} IS '{resources.database_comment}';")


def upgrade_database(resources: WorkerRecoveryResources) -> None:
    environment = fake_environment(resources, "redis://127.0.0.1:1/0")
    run_text((sys.executable, "-m", "alembic", "upgrade", "head"), environment=environment)
    revision = database_sql(resources, "SELECT version_num FROM alembic_version;")
    if revision != ALEMBIC_HEAD:
        raise WorkerRecoveryDrillError("Temporary database did not reach Alembic head.")


def start_redis(resources: WorkerRecoveryResources) -> str:
    run_text(
        (
            "docker",
            "run",
            "--detach",
            "--rm",
            "--name",
            resources.redis_container_name,
            "--label",
            "careerops.drill=p1-8b",
            "--label",
            f"careerops.run-id={resources.run_id}",
            "--publish",
            "127.0.0.1::6379",
            REDIS_IMAGE,
        )
    )
    port_output = run_text(("docker", "port", resources.redis_container_name, "6379/tcp"))
    port = port_output.rsplit(":", 1)[-1]
    if not port.isdigit():
        raise WorkerRecoveryDrillError("Temporary Redis port could not be resolved.")
    redis_url = f"redis://127.0.0.1:{port}/0"
    client = Redis.from_url(redis_url, socket_timeout=0.5)
    try:
        for _ in range(40):
            try:
                if client.ping():
                    return redis_url
            except Exception:
                time.sleep(0.1)
    finally:
        client.close()
    raise WorkerRecoveryDrillError("Temporary Redis did not become ready.")


def fake_environment(resources: WorkerRecoveryResources, redis_url: str) -> dict[str, str]:
    environment = dict(os.environ)
    environment.update(
        {
            "CAREEROPS_DATABASE_URL": database_url(resources),
            "CAREEROPS_REDIS_URL": redis_url,
            "CAREEROPS_LLM_PROVIDER": "fake",
            "CAREEROPS_EMBEDDING_PROVIDER": "fake",
            "CAREEROPS_EVIDENCE_MATCHER_PROVIDER": "fake",
            "CAREEROPS_RUN_LLM_INTEGRATION": "0",
            "CAREEROPS_RUN_EMBEDDING_INTEGRATION": "0",
            "CAREEROPS_RUN_REAL_MATCHER_WORKER": "0",
            "CAREEROPS_PARSE_RUN_STALE_AFTER_SECONDS": "30",
            "CAREEROPS_ANALYSIS_RUN_STALE_AFTER_SECONDS": "30",
            "CAREEROPS_EMBEDDING_RUN_STALE_AFTER_SECONDS": "30",
        }
    )
    return environment


async def seed_synthetic_work(target_database_url: str) -> None:
    now = datetime.now(UTC)
    stale = now - timedelta(minutes=10)
    ready_experience = ExperienceCreate(
        user_id=USER_ID,
        title="Ready Recovery Evidence",
        kind=ExperienceKind.PROJECT,
        description="Built reliable Python recovery workflows.",
        skills=("Python", "PostgreSQL"),
        outcome="Verified deterministic recovery.",
    )
    recovered_experience = ExperienceCreate(
        user_id=USER_ID,
        title="Embedding Recovery Target",
        kind=ExperienceKind.PROJECT,
        description="Implemented Redis queue recovery.",
        skills=("Redis",),
        outcome="Recovered missing durable work.",
    )
    parse_job = JobCreate(
        user_id=USER_ID,
        company="Synthetic Parse",
        title="Backend Intern",
        raw_description="Python experience required. Preferred Redis.",
        source_url=None,
        location=None,
        deadline=None,
        status=JobStatus.SAVED,
    )
    analysis_job = JobCreate(
        user_id=USER_ID,
        company="Synthetic Analysis",
        title="Backend Intern",
        raw_description="Python experience required.",
        source_url=None,
        location=None,
        deadline=None,
        status=JobStatus.SAVED,
    )
    ready_hash = compute_experience_content_hash(ready_experience)
    recovered_hash = compute_experience_content_hash(recovered_experience)
    vector = [1.0] + [0.0] * 1535
    session_factory = create_session_factory(target_database_url)
    async with session_factory() as session:
        session.add(User(id=USER_ID, email="p1-8b@example.invalid", password_hash="synthetic"))
        await session.flush()
        session.add_all(
            (
                Experience(
                    id=READY_EXPERIENCE_ID,
                    user_id=USER_ID,
                    title=ready_experience.title,
                    kind=ready_experience.kind.value,
                    description=ready_experience.description,
                    skills=list(ready_experience.skills),
                    outcome=ready_experience.outcome,
                    version=1,
                    content_hash=ready_hash,
                    embedding=vector,
                    embedding_content_hash=ready_hash,
                    embedding_model=FAKE_EMBEDDING_MODEL_NAME,
                    embedding_input_version=EMBEDDING_INPUT_VERSION,
                    embedded_at=stale,
                    created_at=stale,
                    updated_at=stale,
                ),
                Experience(
                    id=RECOVERED_EXPERIENCE_ID,
                    user_id=USER_ID,
                    title=recovered_experience.title,
                    kind=recovered_experience.kind.value,
                    description=recovered_experience.description,
                    skills=list(recovered_experience.skills),
                    outcome=recovered_experience.outcome,
                    version=1,
                    content_hash=recovered_hash,
                    created_at=stale,
                    updated_at=stale,
                ),
            )
        )
        await session.flush()
        session.add(
            ExperienceEmbeddingRun(
                id=READY_EMBEDDING_RUN_ID,
                user_id=USER_ID,
                experience_id=READY_EXPERIENCE_ID,
                experience_version=1,
                content_hash=ready_hash,
                status="succeeded",
                model_name=FAKE_EMBEDDING_MODEL_NAME,
                input_version=EMBEDDING_INPUT_VERSION,
                attempt=1,
                started_at=stale,
                finished_at=stale,
                created_at=stale,
            )
        )
        session.add_all(
            (
                make_job(PARSE_JOB_ID, parse_job, stale),
                make_job(ANALYSIS_JOB_ID, analysis_job, stale),
            )
        )
        await session.flush()
        session.add_all(
            (
                ParseRun(
                    id=STALE_PARSE_RUN_ID,
                    user_id=USER_ID,
                    job_id=PARSE_JOB_ID,
                    status="running",
                    idempotency_key="p1-8b-parse",
                    input_fingerprint="a" * 64,
                    input_text=parse_job.raw_description,
                    model_name=FAKE_PARSE_MODEL_NAME,
                    prompt_version=PARSE_PROMPT_VERSION,
                    attempt=1,
                    started_at=stale,
                    created_at=stale,
                ),
                ParseRun(
                    id=READY_PARSE_RUN_ID,
                    user_id=USER_ID,
                    job_id=ANALYSIS_JOB_ID,
                    status="succeeded",
                    idempotency_key="p1-8b-ready-parse",
                    input_fingerprint="b" * 64,
                    input_text=analysis_job.raw_description,
                    model_name=FAKE_PARSE_MODEL_NAME,
                    prompt_version=PARSE_PROMPT_VERSION,
                    attempt=1,
                    started_at=stale,
                    finished_at=stale,
                    created_at=stale,
                ),
            )
        )
        await session.flush()
        session.add(
            JobRequirement(
                id=REQUIREMENT_ID,
                job_id=ANALYSIS_JOB_ID,
                parse_run_id=READY_PARSE_RUN_ID,
                category="must_have",
                text="Python experience required",
                skill_normalized="Python",
                source_span_start=0,
                source_span_end=26,
            )
        )
        await session.flush()
        experiences = tuple(await ExperienceRepository(session).list_experiences(USER_ID))
        fingerprint = compute_analysis_fingerprint(
            READY_PARSE_RUN_ID,
            "b" * 64,
            experiences,
            ANALYSIS_PROMPT_VERSION,
        )
        session.add(
            AnalysisRun(
                id=STALE_ANALYSIS_RUN_ID,
                user_id=USER_ID,
                job_id=ANALYSIS_JOB_ID,
                parse_run_id=READY_PARSE_RUN_ID,
                status="running",
                idempotency_key="p1-8b-analysis",
                input_fingerprint=fingerprint,
                model_name=FAKE_ANALYSIS_MODEL_NAME,
                prompt_version=ANALYSIS_PROMPT_VERSION,
                attempt=1,
                started_at=stale,
                created_at=stale,
            )
        )
        await session.commit()
    await session_factory.kw["bind"].dispose()


def make_job(job_id: UUID, payload: JobCreate, created_at: datetime) -> Job:
    return Job(
        id=job_id,
        user_id=USER_ID,
        company=payload.company,
        title=payload.title,
        raw_description=payload.raw_description,
        description_hash=compute_description_hash(payload.raw_description),
        source_url=payload.source_url,
        location=payload.location,
        deadline=payload.deadline,
        status=payload.status.value,
        version=1,
        created_at=created_at,
        updated_at=created_at,
    )


def run_recovery_cycle(environment: Mapping[str, str]) -> object:
    output = run_text(
        (sys.executable, "-m", "careerops.workers.recovery_cycle"),
        environment=environment,
    )
    summary: object = json.loads(output.splitlines()[-1])
    expected = [
        ("parse", 0, 1, 1, 0),
        ("analysis", 0, 1, 1, 0),
        ("embedding", 1, 0, 1, 0),
    ]
    if not isinstance(summary, dict) or not isinstance(summary.get("steps"), list):
        raise WorkerRecoveryDrillError("Recovery cycle did not return its JSON summary.")
    actual = [
        (
            step.get("name"),
            step.get("reconciled"),
            step.get("requeued"),
            step.get("dispatched"),
            step.get("dispatch_failed"),
        )
        for step in summary["steps"]
        if isinstance(step, dict)
    ]
    if actual != expected:
        raise WorkerRecoveryDrillError("Recovery counts did not match the synthetic fixture.")
    return summary


def start_worker(environment: Mapping[str, str], log_path: Path) -> subprocess.Popen[str]:
    log_file = log_path.open("x", encoding="utf-8")
    try:
        return subprocess.Popen(
            (
                sys.executable,
                "-m",
                "dramatiq",
                "careerops.workers.tasks",
                "--processes",
                "1",
                "--threads",
                "4",
            ),
            cwd=REPOSITORY_ROOT,
            env=environment,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True,
        )
    finally:
        log_file.close()


async def wait_for_completion(
    target_database_url: str,
    worker: subprocess.Popen[str],
) -> VerificationResult:
    session_factory = create_session_factory(target_database_url)
    try:
        for _ in range(300):
            if worker.poll() is not None:
                raise WorkerRecoveryDrillError("Dedicated worker exited before verification.")
            async with session_factory() as session:
                parse_run = await session.get(ParseRun, STALE_PARSE_RUN_ID)
                analysis_run = await session.get(AnalysisRun, STALE_ANALYSIS_RUN_ID)
                embedding_run = await session.scalar(
                    select(ExperienceEmbeddingRun).where(
                        ExperienceEmbeddingRun.experience_id == RECOVERED_EXPERIENCE_ID
                    )
                )
                recovered_experience = await session.get(Experience, RECOVERED_EXPERIENCE_ID)
                if (
                    parse_run is not None
                    and analysis_run is not None
                    and embedding_run is not None
                    and recovered_experience is not None
                    and parse_run.status == "succeeded"
                    and analysis_run.status == "succeeded"
                    and embedding_run.status == "succeeded"
                    and recovered_experience.embedding is not None
                ):
                    requirement_count = await session.scalar(
                        select(func.count()).select_from(JobRequirement).where(
                            JobRequirement.parse_run_id == STALE_PARSE_RUN_ID
                        )
                    )
                    match_count = await session.scalar(
                        select(func.count()).select_from(EvidenceMatch).where(
                            EvidenceMatch.analysis_run_id == STALE_ANALYSIS_RUN_ID
                        )
                    )
                    if not isinstance(requirement_count, int) or not isinstance(match_count, int):
                        raise WorkerRecoveryDrillError("Verification counts were not integers.")
                    return VerificationResult(
                        parse_attempt=parse_run.attempt,
                        analysis_attempt=analysis_run.attempt,
                        embedding_attempt=embedding_run.attempt,
                        parse_requirement_count=requirement_count,
                        evidence_match_count=match_count,
                    )
            await asyncio.sleep(0.1)
    finally:
        await session_factory.kw["bind"].dispose()
    raise WorkerRecoveryDrillError("Recovered work did not complete before timeout.")


def stop_worker(worker: subprocess.Popen[str]) -> None:
    if worker.poll() is None:
        if os.name == "nt":
            completed = subprocess.run(
                ("taskkill", "/PID", str(worker.pid), "/T", "/F"),
                capture_output=True,
                text=True,
                check=False,
            )
            if completed.returncode != 0:
                raise WorkerRecoveryDrillError("Dedicated worker process tree did not stop.")
            worker.wait(timeout=10)
            return
        worker.terminate()
        try:
            worker.wait(timeout=10)
        except subprocess.TimeoutExpired:
            worker.kill()
            worker.wait(timeout=10)


def stop_redis(resources: WorkerRecoveryResources) -> None:
    label = run_text(
        (
            "docker",
            "inspect",
            resources.redis_container_name,
            "--format",
            '{{ index .Config.Labels "careerops.run-id" }}',
        )
    )
    verify_redis_cleanup_identity(resources, label)
    run_text(("docker", "stop", resources.redis_container_name))


def drop_database(resources: WorkerRecoveryResources) -> None:
    observed = postgres_sql(
        "SELECT COALESCE(shobj_description(oid, 'pg_database'), '') "
        f"FROM pg_database WHERE datname = '{resources.database_name}';"
    )
    verify_database_cleanup_identity(resources, observed)
    postgres_sql(f"DROP DATABASE {quote_database(resources.database_name)} WITH (FORCE);")
    if database_exists(resources):
        raise WorkerRecoveryDrillError("Temporary database still exists after cleanup.")


def verify_redis_cleanup_identity(
    resources: WorkerRecoveryResources,
    observed_run_id: str,
) -> None:
    if observed_run_id != resources.run_id:
        raise WorkerRecoveryDrillError("Temporary Redis run-id label changed.")


def verify_database_cleanup_identity(
    resources: WorkerRecoveryResources,
    observed_comment: str,
) -> None:
    if observed_comment != resources.database_comment:
        raise WorkerRecoveryDrillError("Temporary database comment sentinel changed.")


def database_exists(resources: WorkerRecoveryResources) -> bool:
    return postgres_sql(
        "SELECT EXISTS (SELECT 1 FROM pg_database "
        f"WHERE datname = '{resources.database_name}');"
    ) == "t"


def database_url(resources: WorkerRecoveryResources) -> str:
    validate_database_name(resources.database_name)
    return f"{DATABASE_URL_PREFIX}{resources.database_name}"


def quote_database(database_name: str) -> str:
    validate_database_name(database_name)
    return f'"{database_name}"'


def postgres_sql(sql: str) -> str:
    return run_text(
        docker_postgres_command(
            "psql",
            "-U",
            POSTGRES_USER,
            "-d",
            "postgres",
            "-X",
            "-v",
            "ON_ERROR_STOP=1",
            "-Atc",
            sql,
        )
    )


def database_sql(resources: WorkerRecoveryResources, sql: str) -> str:
    return run_text(
        docker_postgres_command(
            "psql",
            "-U",
            POSTGRES_USER,
            "-d",
            resources.database_name,
            "-X",
            "-v",
            "ON_ERROR_STOP=1",
            "-Atc",
            sql,
        )
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Plan or run the isolated P1-8b worker drill.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    plan = subparsers.add_parser("plan")
    plan.add_argument("--run-id", required=True)
    run = subparsers.add_parser("run")
    run.add_argument("--run-id", required=True)
    run.add_argument("--confirm-cleanup-run-id", required=True)
    args = parser.parse_args(argv)
    try:
        resources = build_resources(str(args.run_id))
        if args.command == "plan":
            print(render_plan(resources))
            return 0
        result = execute_drill(
            resources.run_id,
            confirmation_run_id=str(args.confirm_cleanup_run_id),
        )
    except (DrillSafetyError, WorkerRecoveryDrillError) as exc:
        parser.error(str(exc))
    print(json.dumps(asdict(result), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
