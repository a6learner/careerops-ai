import asyncio
import hashlib
import json
import os
import subprocess
import sys
import time
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Final
from uuid import UUID

from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from careerops.core.config import get_settings
from careerops.db.models import (
    ActionItem,
    AnalysisRun,
    Base,
    EvidenceMatch,
    Experience,
    ExperienceEmbeddingRun,
    Job,
    JobRequirement,
    ParseRun,
    User,
)
from careerops.db.session import create_session_factory
from careerops.domain.action_items import ActionItemStatus
from careerops.domain.analysis_runs import ANALYSIS_PROMPT_VERSION, FAKE_ANALYSIS_MODEL_NAME
from careerops.domain.embeddings import EMBEDDING_INPUT_VERSION, FAKE_EMBEDDING_MODEL_NAME
from careerops.domain.experiences import ExperienceCreate, ExperienceKind
from careerops.domain.jobs import JobCreate, JobStatus
from careerops.repositories.action_items import ActionItemRepository
from careerops.repositories.analysis_runs import AnalysisRunRepository
from careerops.repositories.experiences import ExperienceRepository
from careerops.repositories.jobs import JobRepository
from careerops.repositories.parse_runs import ParseRunRepository
from careerops.security.tokens import TokenIssuer
from careerops.services.experiences import compute_experience_content_hash
from careerops.services.jobs import compute_description_hash

from .backup_restore_drill import (
    DrillManifest,
    DrillResources,
    DrillSafetyError,
    ObservedDatabaseComments,
    build_resources,
    validate_database_identifier,
    verify_cleanup_contract,
    verify_failed_cleanup_contract,
)

ALEMBIC_HEAD: Final = "202610060001"
EXECUTION_GATE: Final = "CAREEROPS_RUN_BACKUP_RESTORE_DRILL"
REPOSITORY_ROOT: Final = Path(__file__).resolve().parents[3]
POSTGRES_USER: Final = "careerops"
DATABASE_URL_PREFIX: Final = "postgresql+asyncpg://careerops:careerops@127.0.0.1:5432/"

USER_ID: Final = UUID("81000000-0000-4000-8000-000000000001")
EXPERIENCE_ID: Final = UUID("81000000-0000-4000-8000-000000000002")
EMBEDDING_RUN_ID: Final = UUID("81000000-0000-4000-8000-000000000003")
JOB_ID: Final = UUID("81000000-0000-4000-8000-000000000004")
PARSE_RUN_ID: Final = UUID("81000000-0000-4000-8000-000000000005")
POSITIVE_REQUIREMENT_ID: Final = UUID("81000000-0000-4000-8000-000000000006")
GAP_REQUIREMENT_ID: Final = UUID("81000000-0000-4000-8000-000000000007")
ANALYSIS_RUN_ID: Final = UUID("81000000-0000-4000-8000-000000000008")
POSITIVE_MATCH_ID: Final = UUID("81000000-0000-4000-8000-000000000009")
GAP_MATCH_ID: Final = UUID("81000000-0000-4000-8000-00000000000a")
ACTION_ITEM_ID: Final = UUID("81000000-0000-4000-8000-00000000000b")
EVIDENCE_QUOTE: Final = "Implemented crash-safe PostgreSQL workflows."


class DrillExecutionError(RuntimeError):
    """Raised when an authorized drill cannot complete safely."""


@dataclass(frozen=True)
class RowCounts:
    users: int
    experiences: int
    experience_embedding_runs: int
    jobs: int
    parse_runs: int
    job_requirements: int
    analysis_runs: int
    evidence_matches: int
    action_items: int


@dataclass(frozen=True)
class SyntheticFixture:
    experience_content_hash: str
    job_description_hash: str
    row_counts: RowCounts


@dataclass(frozen=True)
class DrillResult:
    run_id: str
    alembic_revision: str
    postgres_server_version: str
    pg_dump_version: str
    dump_sha256: str
    dump_bytes: int
    backup_elapsed_ms: int
    restore_elapsed_ms: int
    verification_elapsed_ms: int
    total_elapsed_ms: int
    row_counts: RowCounts
    repository_readback: bool
    api_readback: bool
    constraint_checks: int
    cleaned_up: bool
    synthetic_only: bool
    production_rto_rpo_claim: bool


def execute_drill(run_id: str, *, confirmation_run_id: str) -> DrillResult:
    require_execution_gate()
    resources = build_resources(run_id)
    if confirmation_run_id != run_id:
        raise DrillSafetyError("Execution cleanup confirmation must equal the run ID.")

    started = time.perf_counter()
    try:
        server_version, pg_dump_version = preflight(resources)
        resources.artifact_directory.mkdir(parents=True, exist_ok=False)
        manifest = DrillManifest.from_resources(resources)
        write_manifest(resources.manifest_path, manifest)

        create_temporary_database(resources.source_database, resources.source_comment)
        upgrade_database(resources.source_database)
        fixture = asyncio.run(seed_synthetic_data(database_url(resources.source_database)))
        asyncio.run(verify_database(database_url(resources.source_database), fixture))

        backup_started = time.perf_counter()
        create_custom_dump(resources)
        backup_elapsed_ms = elapsed_ms(backup_started)

        create_temporary_database(resources.restore_database, resources.restore_comment)
        restore_started = time.perf_counter()
        restore_custom_dump(resources)
        restore_elapsed_ms = elapsed_ms(restore_started)

        verification_started = time.perf_counter()
        asyncio.run(verify_database(database_url(resources.restore_database), fixture, full=True))
        verification_elapsed_ms = elapsed_ms(verification_started)
        dump_sha256 = file_sha256(resources.dump_path)
        dump_bytes = resources.dump_path.stat().st_size

        loaded_manifest = load_manifest(resources.manifest_path, manifest)
        observed_comments = read_database_comments(resources)
        verify_cleanup_contract(
            resources,
            loaded_manifest,
            observed_comments,
            confirmation_run_id=confirmation_run_id,
        )
        cleanup_successful_drill(resources)

        return DrillResult(
            run_id=run_id,
            alembic_revision=ALEMBIC_HEAD,
            postgres_server_version=server_version,
            pg_dump_version=pg_dump_version,
            dump_sha256=dump_sha256,
            dump_bytes=dump_bytes,
            backup_elapsed_ms=backup_elapsed_ms,
            restore_elapsed_ms=restore_elapsed_ms,
            verification_elapsed_ms=verification_elapsed_ms,
            total_elapsed_ms=elapsed_ms(started),
            row_counts=fixture.row_counts,
            repository_readback=True,
            api_readback=True,
            constraint_checks=4,
            cleaned_up=True,
            synthetic_only=True,
            production_rto_rpo_claim=False,
        )
    except Exception as exc:
        preserve_failure_diagnostic(resources, exc)
        raise

def require_execution_gate() -> None:
    if os.getenv(EXECUTION_GATE) != "1":
        raise DrillSafetyError(f"Set invocation-local {EXECUTION_GATE}=1 to authorize the drill.")


def preflight(resources: DrillResources) -> tuple[str, str]:
    heads = run_text((sys.executable, "-m", "alembic", "heads"))
    if ALEMBIC_HEAD not in heads or "(head)" not in heads:
        raise DrillExecutionError("The repository Alembic head is not the expected revision.")

    services = set(
        run_text(("docker", "compose", "ps", "--services", "--status", "running")).split()
    )
    if "postgres" not in services:
        raise DrillExecutionError("The existing Compose PostgreSQL service is not running.")

    server_version = psql("postgres", "SHOW server_version;")
    pg_dump_version = run_text(docker_postgres_command("pg_dump", "--version"))
    pg_restore_version = run_text(docker_postgres_command("pg_restore", "--version"))
    versions = (server_version, pg_dump_version, pg_restore_version)
    if any("16." not in version for version in versions):
        raise DrillExecutionError(
            "PostgreSQL server and backup tools must all use major version 16."
        )

    for database_name in (resources.source_database, resources.restore_database):
        if database_exists(database_name):
            raise DrillSafetyError(f"Temporary database already exists: {database_name}")
    if resources.artifact_directory.exists():
        raise DrillSafetyError("Drill artifact directory already exists; refusing overwrite.")
    return server_version, pg_dump_version


def create_temporary_database(database_name: str, comment: str) -> None:
    validate_database_identifier(database_name)
    quoted_name = quote_identifier(database_name)
    psql("postgres", f"CREATE DATABASE {quoted_name} OWNER {POSTGRES_USER} TEMPLATE template0;")
    psql("postgres", f"COMMENT ON DATABASE {quoted_name} IS '{comment}';")


def upgrade_database(database_name: str) -> None:
    validate_database_identifier(database_name)
    environment = safe_process_environment(database_url(database_name))
    run_text((sys.executable, "-m", "alembic", "upgrade", "head"), environment=environment)
    revision = psql(database_name, "SELECT version_num FROM alembic_version;")
    if revision != ALEMBIC_HEAD:
        raise DrillExecutionError("Temporary source database did not reach the expected revision.")


async def seed_synthetic_data(target_database_url: str) -> SyntheticFixture:
    now = datetime(2026, 10, 6, 12, 0, tzinfo=UTC)
    experience_payload = ExperienceCreate(
        user_id=USER_ID,
        title="Synthetic Recovery Project",
        kind=ExperienceKind.PROJECT,
        description=(
            "Built a synthetic storage service. "
            "Implemented crash-safe PostgreSQL workflows. "
            "Verified deterministic recovery behavior."
        ),
        skills=("Python", "PostgreSQL", "Recovery testing"),
        outcome="Recovered all synthetic committed records.",
    )
    job_payload = JobCreate(
        user_id=USER_ID,
        company="Synthetic Systems",
        title="Backend Intern",
        raw_description="Build PostgreSQL backup workflows and document recovery gaps.",
        source_url="https://example.invalid/synthetic-job",
        location="Synthetic Remote",
        deadline=None,
        status=JobStatus.SAVED,
    )
    experience_hash = compute_experience_content_hash(experience_payload)
    job_hash = compute_description_hash(job_payload.raw_description)
    embedding = [1.0] + [0.0] * 1535

    session_factory = create_session_factory(target_database_url)
    async with session_factory() as session:
        session.add(
            User(
                id=USER_ID,
                email="p1-8a-synthetic@example.invalid",
                password_hash="synthetic",
            )
        )
        await session.flush()
        session.add(
            Experience(
                id=EXPERIENCE_ID,
                user_id=USER_ID,
                title=experience_payload.title,
                kind=experience_payload.kind.value,
                description=experience_payload.description,
                skills=list(experience_payload.skills),
                outcome=experience_payload.outcome,
                version=1,
                content_hash=experience_hash,
                embedding=embedding,
                embedding_content_hash=experience_hash,
                embedding_model=FAKE_EMBEDDING_MODEL_NAME,
                embedding_input_version=EMBEDDING_INPUT_VERSION,
                embedded_at=now,
                created_at=now,
                updated_at=now,
            )
        )
        await session.flush()
        session.add(
            ExperienceEmbeddingRun(
                id=EMBEDDING_RUN_ID,
                user_id=USER_ID,
                experience_id=EXPERIENCE_ID,
                experience_version=1,
                content_hash=experience_hash,
                status="succeeded",
                model_name=FAKE_EMBEDDING_MODEL_NAME,
                input_version=EMBEDDING_INPUT_VERSION,
                attempt=1,
                started_at=now,
                finished_at=now,
                created_at=now,
            )
        )
        session.add(
            Job(
                id=JOB_ID,
                user_id=USER_ID,
                company=job_payload.company,
                title=job_payload.title,
                raw_description=job_payload.raw_description,
                description_hash=job_hash,
                source_url=job_payload.source_url,
                location=job_payload.location,
                deadline=job_payload.deadline,
                status=job_payload.status.value,
                version=1,
                created_at=now,
                updated_at=now,
            )
        )
        await session.flush()
        session.add(
            ParseRun(
                id=PARSE_RUN_ID,
                user_id=USER_ID,
                job_id=JOB_ID,
                status="succeeded",
                idempotency_key="p1-8a-parse",
                input_fingerprint="a" * 64,
                input_text=job_payload.raw_description,
                model_name="local-fake-parser",
                prompt_version="parse-v2",
                attempt=1,
                latency_ms=1,
                started_at=now,
                finished_at=now,
                created_at=now,
            )
        )
        await session.flush()
        session.add_all(
            (
                JobRequirement(
                    id=POSITIVE_REQUIREMENT_ID,
                    job_id=JOB_ID,
                    parse_run_id=PARSE_RUN_ID,
                    category="must_have",
                    text="PostgreSQL recovery",
                    skill_normalized="PostgreSQL",
                ),
                JobRequirement(
                    id=GAP_REQUIREMENT_ID,
                    job_id=JOB_ID,
                    parse_run_id=PARSE_RUN_ID,
                    category="nice_to_have",
                    text="Production point-in-time recovery",
                    skill_normalized="PITR",
                ),
            )
        )
        await session.flush()
        session.add(
            AnalysisRun(
                id=ANALYSIS_RUN_ID,
                user_id=USER_ID,
                job_id=JOB_ID,
                parse_run_id=PARSE_RUN_ID,
                status="succeeded",
                idempotency_key="p1-8a-analysis",
                input_fingerprint="b" * 64,
                model_name=FAKE_ANALYSIS_MODEL_NAME,
                prompt_version=ANALYSIS_PROMPT_VERSION,
                attempt=1,
                validation_failure_count=0,
                latency_ms=1,
                started_at=now,
                finished_at=now,
                created_at=now,
            )
        )
        await session.flush()
        session.add_all(
            (
                EvidenceMatch(
                    id=POSITIVE_MATCH_ID,
                    analysis_run_id=ANALYSIS_RUN_ID,
                    requirement_id=POSITIVE_REQUIREMENT_ID,
                    experience_id=EXPERIENCE_ID,
                    experience_version=1,
                    verdict="matched",
                    quote=EVIDENCE_QUOTE,
                    quote_valid=True,
                    confidence=0.99,
                ),
                EvidenceMatch(
                    id=GAP_MATCH_ID,
                    analysis_run_id=ANALYSIS_RUN_ID,
                    requirement_id=GAP_REQUIREMENT_ID,
                    experience_id=None,
                    experience_version=None,
                    verdict="missing",
                    quote=None,
                    quote_valid=False,
                    confidence=None,
                ),
            )
        )
        await session.flush()
        session.add(
            ActionItem(
                id=ACTION_ITEM_ID,
                user_id=USER_ID,
                job_id=JOB_ID,
                source_evidence_match_id=GAP_MATCH_ID,
                title="Study PostgreSQL PITR",
                status="todo",
                version=1,
                idempotency_key="p1-8a-action",
                request_fingerprint="c" * 64,
                created_at=now,
                updated_at=now,
            )
        )
        await session.commit()
    await session_factory.kw["bind"].dispose()

    return SyntheticFixture(
        experience_content_hash=experience_hash,
        job_description_hash=job_hash,
        row_counts=RowCounts(
            users=1,
            experiences=1,
            experience_embedding_runs=1,
            jobs=1,
            parse_runs=1,
            job_requirements=2,
            analysis_runs=1,
            evidence_matches=2,
            action_items=1,
        ),
    )


async def verify_database(
    target_database_url: str,
    fixture: SyntheticFixture,
    *,
    full: bool = False,
) -> None:
    session_factory = create_session_factory(target_database_url)
    async with session_factory() as session:
        revision = await session.scalar(text("SELECT version_num FROM alembic_version"))
        if revision != ALEMBIC_HEAD:
            raise DrillExecutionError("Restored Alembic revision does not match head.")

        actual_counts = RowCounts(
            users=await count_rows(session, User),
            experiences=await count_rows(session, Experience),
            experience_embedding_runs=await count_rows(session, ExperienceEmbeddingRun),
            jobs=await count_rows(session, Job),
            parse_runs=await count_rows(session, ParseRun),
            job_requirements=await count_rows(session, JobRequirement),
            analysis_runs=await count_rows(session, AnalysisRun),
            evidence_matches=await count_rows(session, EvidenceMatch),
            action_items=await count_rows(session, ActionItem),
        )
        if actual_counts != fixture.row_counts:
            raise DrillExecutionError("Restored table counts differ from the synthetic fixture.")

        experience = await session.get(Experience, EXPERIENCE_ID)
        job = await session.get(Job, JOB_ID)
        positive_match = await session.get(EvidenceMatch, POSITIVE_MATCH_ID)
        if experience is None or job is None or positive_match is None:
            raise DrillExecutionError("A required restored record is missing.")
        if experience.content_hash != fixture.experience_content_hash:
            raise DrillExecutionError("Experience content hash changed during recovery.")
        if job.description_hash != fixture.job_description_hash:
            raise DrillExecutionError("Job description hash changed during recovery.")
        if positive_match.quote != EVIDENCE_QUOTE or EVIDENCE_QUOTE not in experience.description:
            raise DrillExecutionError("Grounded evidence quote did not survive recovery.")
        if (
            experience.embedding is None
            or len(experience.embedding) != 1536
            or experience.embedding_content_hash != experience.content_hash
            or experience.embedding_model != FAKE_EMBEDDING_MODEL_NAME
            or experience.embedding_input_version != EMBEDDING_INPUT_VERSION
            or experience.embedded_at is None
        ):
            raise DrillExecutionError("Embedding provenance did not survive recovery.")

    if full:
        await verify_repository_readback(session_factory)
        await verify_constraint_rejections(session_factory)
        await verify_api_readback(target_database_url)
        await verify_schema_objects(session_factory)
    await session_factory.kw["bind"].dispose()


async def count_rows(session: AsyncSession, model: type[Base]) -> int:
    scalar = await session.scalar(select(func.count()).select_from(model))
    if not isinstance(scalar, int):
        raise DrillExecutionError("A table count did not return an integer.")
    return scalar


async def verify_repository_readback(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        experiences = await ExperienceRepository(session).list_experiences(USER_ID)
        job = await JobRepository(session).get_job(USER_ID, JOB_ID)
        parse_run = await ParseRunRepository(session).get_parse_run(USER_ID, JOB_ID, PARSE_RUN_ID)
        analysis_run = await AnalysisRunRepository(session).get_analysis_run(
            USER_ID, JOB_ID, ANALYSIS_RUN_ID
        )
        action_items = await ActionItemRepository(session).list_action_items(
            USER_ID,
            ActionItemStatus.TODO,
            JOB_ID,
            None,
            10,
        )
    if len(experiences) != 1 or job is None or parse_run is None or analysis_run is None:
        raise DrillExecutionError("Repository readback did not return the restored graph.")
    if len(parse_run.requirements) != 2 or len(analysis_run.matches) != 2 or len(action_items) != 1:
        raise DrillExecutionError("Repository readback returned incomplete restored relationships.")


async def verify_api_readback(target_database_url: str) -> None:
    previous_environment = capture_environment(
        (
            "CAREEROPS_DATABASE_URL",
            "CAREEROPS_LLM_PROVIDER",
            "CAREEROPS_EMBEDDING_PROVIDER",
            "CAREEROPS_EVIDENCE_MATCHER_PROVIDER",
            "CAREEROPS_RUN_LLM_INTEGRATION",
            "CAREEROPS_RUN_EMBEDDING_INTEGRATION",
            "CAREEROPS_RUN_REAL_MATCHER_WORKER",
        )
    )
    os.environ.update(safe_process_environment(target_database_url))
    get_settings.cache_clear()
    try:
        from careerops.main import create_app

        app = create_app()
        token = TokenIssuer(
            secret=get_settings().jwt_secret,
            expires_after=timedelta(minutes=5),
        ).issue_access_token(USER_ID)
        headers = {"Authorization": f"Bearer {token.value}"}
        paths = (
            "/api/v1/auth/me",
            "/api/v1/experiences",
            "/api/v1/jobs",
            f"/api/v1/jobs/{JOB_ID}",
            f"/api/v1/jobs/{JOB_ID}/parse-runs/{PARSE_RUN_ID}",
            f"/api/v1/jobs/{JOB_ID}/analysis-runs/{ANALYSIS_RUN_ID}",
            "/api/v1/action-items",
        )
        async with app.router.lifespan_context(app):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                for path in paths:
                    response = await client.get(path, headers=headers)
                    if response.status_code != 200:
                        raise DrillExecutionError(
                            f"Read-only API recovery check failed for {path}."
                        )
    finally:
        restore_environment(previous_environment)
        get_settings.cache_clear()


async def verify_schema_objects(session_factory: async_sessionmaker[AsyncSession]) -> None:
    expected_constraints = {
        "ck_analysis_runs_lifecycle",
        "ck_evidence_matches_grounded_verdict",
        "fk_action_items_job_id_jobs",
    }
    expected_indexes = {
        "uq_evidence_matches_run_requirement",
        "uq_experience_embedding_runs_target",
    }
    async with session_factory() as session:
        constraints = set(
            (
                await session.scalars(
                    text(
                        "SELECT conname FROM pg_constraint "
                        "WHERE connamespace = 'public'::regnamespace"
                    )
                )
            ).all()
        )
        indexes = set(
            (
                await session.scalars(
                    text("SELECT indexname FROM pg_indexes WHERE schemaname = 'public'")
                )
            ).all()
        )
    if not expected_constraints.issubset(constraints) or not expected_indexes.issubset(indexes):
        raise DrillExecutionError(
            "Required constraints or unique indexes are missing after restore."
        )


async def verify_constraint_rejections(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    statements = (
        text("UPDATE analysis_runs SET finished_at = NULL WHERE id = :id"),
        text(
            "UPDATE evidence_matches SET verdict = 'matched' "
            "WHERE id = :id"
        ),
        text(
            "INSERT INTO evidence_matches "
            "(id, analysis_run_id, requirement_id, verdict, quote_valid) "
            "VALUES (:new_id, :analysis_id, :requirement_id, 'missing', false)"
        ),
        text(
            "INSERT INTO action_items "
            "(id, user_id, job_id, title, status, version, idempotency_key, request_fingerprint) "
            "VALUES (:new_id, :user_id, :job_id, 'Invalid FK', 'todo', 1, 'invalid-fk', :hash)"
        ),
    )
    parameters: tuple[Mapping[str, object], ...] = (
        {"id": ANALYSIS_RUN_ID},
        {"id": GAP_MATCH_ID},
        {
            "new_id": UUID("81000000-0000-4000-8000-00000000000c"),
            "analysis_id": ANALYSIS_RUN_ID,
            "requirement_id": POSITIVE_REQUIREMENT_ID,
        },
        {
            "new_id": UUID("81000000-0000-4000-8000-00000000000d"),
            "user_id": USER_ID,
            "job_id": UUID("81000000-0000-4000-8000-0000000000ff"),
            "hash": "d" * 64,
        },
    )
    for statement, values in zip(statements, parameters, strict=True):
        async with session_factory() as session:
            try:
                await session.execute(statement, values)
                await session.commit()
            except IntegrityError:
                await session.rollback()
            else:
                raise DrillExecutionError(
                    "A restored database invariant accepted an invalid write."
                )


def create_custom_dump(resources: DrillResources) -> None:
    command = docker_postgres_command(
        "pg_dump",
        "-U",
        POSTGRES_USER,
        "--format=custom",
        "--no-owner",
        "--no-privileges",
        "--dbname",
        resources.source_database,
    )
    run_binary_output(command, resources.dump_path)
    if resources.dump_path.stat().st_size <= 0:
        raise DrillExecutionError("pg_dump produced an empty archive.")


def restore_custom_dump(resources: DrillResources) -> None:
    command = docker_postgres_command(
        "pg_restore",
        "-U",
        POSTGRES_USER,
        "--exit-on-error",
        "--single-transaction",
        "--no-owner",
        "--no-privileges",
        "--dbname",
        resources.restore_database,
    )
    run_binary_input(command, resources.dump_path)


def cleanup_successful_drill(resources: DrillResources) -> None:
    comments = read_database_comments(resources)
    if comments.restore != resources.restore_comment or comments.source != resources.source_comment:
        raise DrillSafetyError("Database sentinels changed immediately before cleanup.")
    drop_temporary_database(resources.restore_database)
    drop_temporary_database(resources.source_database)
    resources.dump_path.unlink()
    resources.manifest_path.unlink()
    resources.artifact_directory.rmdir()
    if database_exists(resources.source_database) or database_exists(resources.restore_database):
        raise DrillExecutionError("Temporary database cleanup could not be verified.")
    if resources.artifact_directory.exists():
        raise DrillExecutionError("Temporary artifact cleanup could not be verified.")


def cleanup_failed_drill(run_id: str, *, confirmation_run_id: str) -> None:
    require_execution_gate()
    resources = build_resources(run_id)
    expected_manifest = DrillManifest.from_resources(resources)
    loaded_manifest = load_manifest(resources.manifest_path, expected_manifest)
    observed_comments = read_database_comments(resources)
    verify_failed_cleanup_contract(
        resources,
        loaded_manifest,
        observed_comments,
        confirmation_run_id=confirmation_run_id,
    )

    if observed_comments.restore is not None:
        drop_temporary_database(resources.restore_database)
    if observed_comments.source is not None:
        drop_temporary_database(resources.source_database)
    if resources.dump_path.exists():
        resources.dump_path.unlink()
    failure_path = resources.artifact_directory / "failure.txt"
    if failure_path.exists():
        failure_path.unlink()
    resources.manifest_path.unlink()
    resources.artifact_directory.rmdir()

    if database_exists(resources.source_database) or database_exists(resources.restore_database):
        raise DrillExecutionError("Failed-run database cleanup could not be verified.")
    if resources.artifact_directory.exists():
        raise DrillExecutionError("Failed-run artifact cleanup could not be verified.")


def drop_temporary_database(database_name: str) -> None:
    validate_database_identifier(database_name)
    psql("postgres", f"DROP DATABASE {quote_identifier(database_name)} WITH (FORCE);")


def read_database_comments(resources: DrillResources) -> ObservedDatabaseComments:
    return ObservedDatabaseComments(
        source=database_comment_from_server(resources.source_database),
        restore=database_comment_from_server(resources.restore_database),
    )


def database_comment_from_server(database_name: str) -> str | None:
    validate_database_identifier(database_name)
    value = psql(
        "postgres",
        "SELECT COALESCE(shobj_description(oid, 'pg_database'), '') "
        f"FROM pg_database WHERE datname = '{database_name}';",
    )
    return value or None


def database_exists(database_name: str) -> bool:
    validate_database_identifier(database_name)
    return psql(
        "postgres",
        f"SELECT EXISTS (SELECT 1 FROM pg_database WHERE datname = '{database_name}');",
    ) == "t"


def quote_identifier(database_name: str) -> str:
    validate_database_identifier(database_name)
    return f'"{database_name}"'


def database_url(database_name: str) -> str:
    validate_database_identifier(database_name)
    return f"{DATABASE_URL_PREFIX}{database_name}"


def psql(database_name: str, sql: str) -> str:
    if database_name != "postgres":
        validate_database_identifier(database_name)
    return run_text(
        docker_postgres_command(
            "psql",
            "-U",
            POSTGRES_USER,
            "-d",
            database_name,
            "-X",
            "-v",
            "ON_ERROR_STOP=1",
            "-Atc",
            sql,
        )
    )


def docker_postgres_command(*arguments: str) -> tuple[str, ...]:
    return ("docker", "compose", "exec", "-T", "postgres", *arguments)


def run_text(command: Sequence[str], *, environment: Mapping[str, str] | None = None) -> str:
    completed = subprocess.run(
        command,
        cwd=REPOSITORY_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if completed.returncode != 0:
        raise DrillExecutionError(safe_command_failure(command, completed.stderr))
    return completed.stdout.strip()


def run_binary_output(command: Sequence[str], output_path: Path) -> None:
    with output_path.open("xb") as output_file:
        completed = subprocess.run(
            command,
            cwd=REPOSITORY_ROOT,
            stdout=output_file,
            stderr=subprocess.PIPE,
            check=False,
        )
    if completed.returncode != 0:
        raise DrillExecutionError(safe_command_failure(command, completed.stderr.decode()))


def run_binary_input(command: Sequence[str], input_path: Path) -> None:
    with input_path.open("rb") as input_file:
        completed = subprocess.run(
            command,
            cwd=REPOSITORY_ROOT,
            stdin=input_file,
            capture_output=True,
            check=False,
        )
    if completed.returncode != 0:
        raise DrillExecutionError(safe_command_failure(command, completed.stderr.decode()))


def safe_command_failure(command: Sequence[str], stderr: str) -> str:
    executable = " ".join(command[:6])
    sanitized = stderr.replace("careerops:careerops@", "careerops:***@")[-1_000:]
    return f"Command failed ({executable}): {sanitized.strip()}"


def safe_process_environment(target_database_url: str) -> dict[str, str]:
    environment = dict(os.environ)
    environment.update(
        {
            "CAREEROPS_DATABASE_URL": target_database_url,
            "CAREEROPS_LLM_PROVIDER": "fake",
            "CAREEROPS_EMBEDDING_PROVIDER": "fake",
            "CAREEROPS_EVIDENCE_MATCHER_PROVIDER": "fake",
            "CAREEROPS_RUN_LLM_INTEGRATION": "0",
            "CAREEROPS_RUN_EMBEDDING_INTEGRATION": "0",
            "CAREEROPS_RUN_REAL_MATCHER_WORKER": "0",
        }
    )
    return environment


def write_manifest(path: Path, manifest: DrillManifest) -> None:
    temporary_path = path.with_suffix(".json.tmp")
    temporary_path.write_text(
        json.dumps(asdict(manifest), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    os.replace(temporary_path, path)


def load_manifest(path: Path, expected: DrillManifest) -> DrillManifest:
    payload: object = json.loads(path.read_text(encoding="utf-8"))
    if payload != asdict(expected):
        raise DrillSafetyError("Saved manifest does not match the expected resource identity.")
    return expected


def preserve_failure_diagnostic(resources: DrillResources, exc: Exception) -> None:
    if not resources.artifact_directory.exists():
        return
    diagnostic_path = resources.artifact_directory / "failure.txt"
    if diagnostic_path.exists():
        return
    message = str(exc).replace("careerops:careerops@", "careerops:***@")
    diagnostic_path.write_text(
        f"failed_at={datetime.now(UTC).isoformat()}\nerror={type(exc).__name__}: {message}\n",
        encoding="utf-8",
    )


def capture_environment(names: Sequence[str]) -> dict[str, str | None]:
    return {name: os.environ.get(name) for name in names}


def restore_environment(values: Mapping[str, str | None]) -> None:
    for name, value in values.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def elapsed_ms(started: float) -> int:
    return round((time.perf_counter() - started) * 1_000)


def render_result(result: DrillResult) -> str:
    return json.dumps(asdict(result), indent=2, sort_keys=True)
