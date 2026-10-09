import argparse
import json
import os
import re
import stat
import tempfile
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

RUN_ID_PATTERN = re.compile(r"^[0-9]{8}t[0-9]{6}z_[0-9a-f]{8}$")
DATABASE_IDENTIFIER_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,62}$")
PROTECTED_DATABASE_NAMES = frozenset({"careerops", "postgres", "template0", "template1"})
MANIFEST_SCHEMA_VERSION = 1


class DrillSafetyError(ValueError):
    """Raised when a proposed drill resource violates a safety invariant."""


@dataclass(frozen=True)
class DrillResources:
    run_id: str
    source_database: str
    restore_database: str
    artifact_directory: Path
    dump_path: Path
    manifest_path: Path
    source_comment: str
    restore_comment: str


@dataclass(frozen=True)
class DrillManifest:
    schema_version: int
    run_id: str
    source_database: str
    restore_database: str
    artifact_directory: str
    dump_path: str
    source_comment: str
    restore_comment: str

    @classmethod
    def from_resources(cls, resources: DrillResources) -> "DrillManifest":
        return cls(
            schema_version=MANIFEST_SCHEMA_VERSION,
            run_id=resources.run_id,
            source_database=resources.source_database,
            restore_database=resources.restore_database,
            artifact_directory=str(resources.artifact_directory),
            dump_path=str(resources.dump_path),
            source_comment=resources.source_comment,
            restore_comment=resources.restore_comment,
        )


@dataclass(frozen=True)
class ObservedDatabaseComments:
    source: str | None
    restore: str | None


@dataclass(frozen=True)
class DryRunPlan:
    mode: Literal["dry_run"]
    mutates_state: bool
    provider_calls: bool
    resources: DrillManifest
    planned_stages: tuple[str, ...]
    cleanup_requirements: tuple[str, ...]


def build_resources(run_id: str, *, temp_root: Path | None = None) -> DrillResources:
    validate_run_id(run_id)
    source_database = f"careerops_p18a_src_{run_id}"
    restore_database = f"careerops_p18a_restore_{run_id}"
    validate_database_identifier(source_database)
    validate_database_identifier(restore_database)

    resolved_temp_root = (temp_root or Path(tempfile.gettempdir())).resolve(strict=True)
    artifact_root = (resolved_temp_root / "careerops-ai" / "p1-8a").resolve(strict=False)
    artifact_directory = (artifact_root / run_id).resolve(strict=False)
    if not artifact_directory.is_relative_to(artifact_root):
        raise DrillSafetyError("Artifact directory escaped the fixed drill root.")
    ensure_no_linked_existing_components(artifact_directory, resolved_temp_root)

    dump_path = artifact_directory / f"careerops_p18a_{run_id}.dump"
    manifest_path = artifact_directory / "manifest.json"
    return DrillResources(
        run_id=run_id,
        source_database=source_database,
        restore_database=restore_database,
        artifact_directory=artifact_directory,
        dump_path=dump_path,
        manifest_path=manifest_path,
        source_comment=database_comment(run_id, "source"),
        restore_comment=database_comment(run_id, "restore"),
    )


def validate_run_id(run_id: str) -> None:
    if RUN_ID_PATTERN.fullmatch(run_id) is None:
        raise DrillSafetyError(
            "Run ID must match YYYYMMDDtHHMMSSz_ followed by eight lowercase hex characters."
        )


def validate_database_identifier(database_name: str) -> None:
    if database_name in PROTECTED_DATABASE_NAMES:
        raise DrillSafetyError(f"Protected database name is never a drill target: {database_name}")
    if DATABASE_IDENTIFIER_PATTERN.fullmatch(database_name) is None:
        raise DrillSafetyError("Database name is not a safe PostgreSQL identifier.")
    if not database_name.startswith(("careerops_p18a_src_", "careerops_p18a_restore_")):
        raise DrillSafetyError("Database name is outside the P1-8a temporary namespace.")


def database_comment(run_id: str, role: Literal["source", "restore"]) -> str:
    validate_run_id(run_id)
    return f"careerops-p1-8a:{run_id}:{role}"


def verify_cleanup_contract(
    resources: DrillResources,
    manifest: DrillManifest,
    observed_comments: ObservedDatabaseComments,
    *,
    confirmation_run_id: str,
    temp_root: Path | None = None,
) -> None:
    expected_resources = build_resources(resources.run_id, temp_root=temp_root)
    expected_manifest = DrillManifest.from_resources(expected_resources)
    if confirmation_run_id != resources.run_id:
        raise DrillSafetyError("Cleanup confirmation does not match the planned run ID.")
    if resources != expected_resources:
        raise DrillSafetyError("Resources do not exactly match the run ID and temporary root.")
    if manifest != expected_manifest:
        raise DrillSafetyError("Manifest does not exactly match the planned resources.")
    if observed_comments.source != resources.source_comment:
        raise DrillSafetyError("Source database comment sentinel does not match.")
    if observed_comments.restore != resources.restore_comment:
        raise DrillSafetyError("Restore database comment sentinel does not match.")
    validate_database_identifier(resources.source_database)
    validate_database_identifier(resources.restore_database)


def verify_failed_cleanup_contract(
    resources: DrillResources,
    manifest: DrillManifest,
    observed_comments: ObservedDatabaseComments,
    *,
    confirmation_run_id: str,
    temp_root: Path | None = None,
) -> None:
    expected_resources = build_resources(resources.run_id, temp_root=temp_root)
    expected_manifest = DrillManifest.from_resources(expected_resources)
    if confirmation_run_id != resources.run_id:
        raise DrillSafetyError("Failed-run cleanup confirmation does not match the run ID.")
    if resources != expected_resources or manifest != expected_manifest:
        raise DrillSafetyError("Failed-run resources do not match the derived resource identity.")
    if observed_comments.source not in {None, resources.source_comment}:
        raise DrillSafetyError("Existing source database has the wrong comment sentinel.")
    if observed_comments.restore not in {None, resources.restore_comment}:
        raise DrillSafetyError("Existing restore database has the wrong comment sentinel.")


def build_dry_run_plan(resources: DrillResources) -> DryRunPlan:
    return DryRunPlan(
        mode="dry_run",
        mutates_state=False,
        provider_calls=False,
        resources=DrillManifest.from_resources(resources),
        planned_stages=(
            "preflight",
            "create isolated source database",
            "upgrade source database from Alembic base to head",
            "seed deterministic synthetic data",
            "create PostgreSQL custom-format dump",
            "create empty restore database",
            "restore dump in one transaction",
            "verify revision, data, constraints, repositories, and read-only API paths",
            "clean up only after explicit authorization and exact identity revalidation",
        ),
        cleanup_requirements=(
            "confirmation run ID equals the planned run ID",
            "manifest equals the derived resource plan",
            "source and restore database comments equal their sentinels",
            "database names remain in the careerops_p18a temporary namespace",
            "artifact path remains under the fixed system temporary directory",
        ),
    )


def render_dry_run(resources: DrillResources) -> str:
    return json.dumps(asdict(build_dry_run_plan(resources)), indent=2, sort_keys=True)


def ensure_no_linked_existing_components(path: Path, boundary: Path) -> None:
    resolved_boundary = boundary.resolve(strict=True)
    candidate = path
    while True:
        if candidate.exists() and is_link_or_reparse_point(candidate):
            raise DrillSafetyError(f"Linked or reparse-point path is not allowed: {candidate}")
        if candidate == resolved_boundary:
            return
        if candidate.parent == candidate or not candidate.is_relative_to(resolved_boundary):
            raise DrillSafetyError("Artifact path is outside the approved temporary boundary.")
        candidate = candidate.parent


def is_link_or_reparse_point(path: Path) -> bool:
    path_stat = os.lstat(path)
    file_attributes = getattr(path_stat, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return path.is_symlink() or bool(file_attributes & reparse_flag)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Plan or run the isolated P1-8a PostgreSQL drill.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    plan_parser = subparsers.add_parser("plan", help="Print a non-mutating resource plan.")
    plan_parser.add_argument("--run-id", required=True)
    run_parser = subparsers.add_parser("run", help="Execute the explicitly authorized drill.")
    run_parser.add_argument("--run-id", required=True)
    run_parser.add_argument("--confirm-cleanup-run-id", required=True)
    cleanup_parser = subparsers.add_parser(
        "cleanup-failed",
        help="Clean only a failed run whose manifest and existing sentinels match.",
    )
    cleanup_parser.add_argument("--run-id", required=True)
    cleanup_parser.add_argument("--confirm-cleanup-run-id", required=True)
    args = parser.parse_args(argv)

    try:
        run_id = str(args.run_id)
        if args.command in {"run", "cleanup-failed"}:
            from .backup_restore_execution import (
                cleanup_failed_drill,
                execute_drill,
                render_result,
            )

            confirmation_run_id = str(args.confirm_cleanup_run_id)
            if args.command == "cleanup-failed":
                cleanup_failed_drill(
                    run_id,
                    confirmation_run_id=confirmation_run_id,
                )
                print(json.dumps({"cleaned_failed_run": run_id}, sort_keys=True))
                return 0
            result = execute_drill(run_id, confirmation_run_id=confirmation_run_id)
            print(render_result(result))
            return 0
        resources = build_resources(run_id)
    except DrillSafetyError as exc:
        parser.error(str(exc))
    print(render_dry_run(resources))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
