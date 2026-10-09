import json
from dataclasses import replace
from pathlib import Path

import pytest

from careerops.operations.backup_restore_drill import (
    DrillManifest,
    DrillSafetyError,
    ObservedDatabaseComments,
    build_resources,
    render_dry_run,
    validate_database_identifier,
    verify_cleanup_contract,
    verify_failed_cleanup_contract,
)
from careerops.operations.backup_restore_execution import (
    EXECUTION_GATE,
    database_url,
    load_manifest,
    require_execution_gate,
    safe_process_environment,
    write_manifest,
)

RUN_ID = "20261006t120000z_1a2b3c4d"


def test_build_resources_derives_isolated_names_and_paths(tmp_path: Path) -> None:
    resources = build_resources(RUN_ID, temp_root=tmp_path)

    assert resources.source_database == f"careerops_p18a_src_{RUN_ID}"
    assert resources.restore_database == f"careerops_p18a_restore_{RUN_ID}"
    assert resources.artifact_directory == tmp_path / "careerops-ai" / "p1-8a" / RUN_ID
    assert resources.dump_path == resources.artifact_directory / f"careerops_p18a_{RUN_ID}.dump"
    assert resources.manifest_path == resources.artifact_directory / "manifest.json"
    assert resources.source_comment == f"careerops-p1-8a:{RUN_ID}:source"
    assert resources.restore_comment == f"careerops-p1-8a:{RUN_ID}:restore"


@pytest.mark.parametrize(
    "run_id",
    (
        "../careerops",
        "20261006T120000Z_1a2b3c4d",
        "20261006t120000z_1A2B3C4D",
        "20261006t120000z_1234",
    ),
)
def test_build_resources_rejects_unsafe_run_ids(tmp_path: Path, run_id: str) -> None:
    with pytest.raises(DrillSafetyError):
        build_resources(run_id, temp_root=tmp_path)


@pytest.mark.parametrize("database_name", ("careerops", "postgres", "template0", "template1"))
def test_protected_databases_are_never_valid_targets(database_name: str) -> None:
    with pytest.raises(DrillSafetyError):
        validate_database_identifier(database_name)


def test_database_name_must_use_temporary_namespace() -> None:
    with pytest.raises(DrillSafetyError):
        validate_database_identifier("unrelated_database")


def test_cleanup_contract_accepts_only_exact_resource_identity(tmp_path: Path) -> None:
    resources = build_resources(RUN_ID, temp_root=tmp_path)
    manifest = DrillManifest.from_resources(resources)
    comments = ObservedDatabaseComments(
        source=resources.source_comment,
        restore=resources.restore_comment,
    )

    verify_cleanup_contract(
        resources,
        manifest,
        comments,
        confirmation_run_id=RUN_ID,
        temp_root=tmp_path,
    )


@pytest.mark.parametrize("mismatch", ("confirmation", "manifest", "source", "restore"))
def test_cleanup_contract_rejects_any_identity_mismatch(tmp_path: Path, mismatch: str) -> None:
    resources = build_resources(RUN_ID, temp_root=tmp_path)
    manifest = DrillManifest.from_resources(resources)
    comments = ObservedDatabaseComments(
        source=resources.source_comment,
        restore=resources.restore_comment,
    )
    confirmation = RUN_ID
    if mismatch == "confirmation":
        confirmation = "20261006t120001z_1a2b3c4d"
    elif mismatch == "manifest":
        manifest = replace(manifest, source_database="careerops_p18a_src_wrong")
    elif mismatch == "source":
        comments = replace(comments, source="careerops-p1-8a:wrong:source")
    else:
        comments = replace(comments, restore="careerops-p1-8a:wrong:restore")

    with pytest.raises(DrillSafetyError):
        verify_cleanup_contract(
            resources,
            manifest,
            comments,
            confirmation_run_id=confirmation,
            temp_root=tmp_path,
        )


def test_cleanup_contract_rederives_resources_from_the_approved_root(tmp_path: Path) -> None:
    resources = build_resources(RUN_ID, temp_root=tmp_path)
    altered = replace(
        resources,
        artifact_directory=tmp_path / "careerops-ai" / "wrong" / RUN_ID,
    )

    with pytest.raises(DrillSafetyError):
        verify_cleanup_contract(
            altered,
            DrillManifest.from_resources(altered),
            ObservedDatabaseComments(
                source=altered.source_comment,
                restore=altered.restore_comment,
            ),
            confirmation_run_id=RUN_ID,
            temp_root=tmp_path,
        )


def test_failed_cleanup_allows_resources_that_were_never_created(tmp_path: Path) -> None:
    resources = build_resources(RUN_ID, temp_root=tmp_path)

    verify_failed_cleanup_contract(
        resources,
        DrillManifest.from_resources(resources),
        ObservedDatabaseComments(source=resources.source_comment, restore=None),
        confirmation_run_id=RUN_ID,
        temp_root=tmp_path,
    )


def test_failed_cleanup_rejects_wrong_existing_sentinel(tmp_path: Path) -> None:
    resources = build_resources(RUN_ID, temp_root=tmp_path)

    with pytest.raises(DrillSafetyError):
        verify_failed_cleanup_contract(
            resources,
            DrillManifest.from_resources(resources),
            ObservedDatabaseComments(source="wrong", restore=None),
            confirmation_run_id=RUN_ID,
            temp_root=tmp_path,
        )


def test_dry_run_is_explicitly_non_mutating_and_contains_no_credentials(tmp_path: Path) -> None:
    resources = build_resources(RUN_ID, temp_root=tmp_path)

    payload = json.loads(render_dry_run(resources))

    assert not resources.artifact_directory.exists()
    assert payload["mode"] == "dry_run"
    assert payload["mutates_state"] is False
    assert payload["provider_calls"] is False
    assert payload["resources"]["run_id"] == RUN_ID
    rendered = json.dumps(payload)
    assert "password" not in rendered.lower()
    assert "postgresql+asyncpg" not in rendered


def test_execution_requires_invocation_local_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(EXECUTION_GATE, raising=False)
    with pytest.raises(DrillSafetyError):
        require_execution_gate()

    monkeypatch.setenv(EXECUTION_GATE, "1")
    require_execution_gate()


def test_database_url_accepts_only_derived_temporary_names(tmp_path: Path) -> None:
    resources = build_resources(RUN_ID, temp_root=tmp_path)

    assert database_url(resources.source_database).endswith(resources.source_database)
    with pytest.raises(DrillSafetyError):
        database_url("careerops")


def test_manifest_round_trip_requires_exact_content(tmp_path: Path) -> None:
    resources = build_resources(RUN_ID, temp_root=tmp_path)
    resources.artifact_directory.mkdir(parents=True)
    manifest = DrillManifest.from_resources(resources)

    write_manifest(resources.manifest_path, manifest)

    assert load_manifest(resources.manifest_path, manifest) == manifest
    resources.manifest_path.write_text("{}", encoding="utf-8")
    with pytest.raises(DrillSafetyError):
        load_manifest(resources.manifest_path, manifest)


def test_execution_environment_forces_all_providers_fake() -> None:
    environment = safe_process_environment(
        "postgresql+asyncpg://careerops:careerops@127.0.0.1:5432/temporary"
    )

    assert environment["CAREEROPS_LLM_PROVIDER"] == "fake"
    assert environment["CAREEROPS_EMBEDDING_PROVIDER"] == "fake"
    assert environment["CAREEROPS_EVIDENCE_MATCHER_PROVIDER"] == "fake"
    assert environment["CAREEROPS_RUN_LLM_INTEGRATION"] == "0"
    assert environment["CAREEROPS_RUN_EMBEDDING_INTEGRATION"] == "0"
    assert environment["CAREEROPS_RUN_REAL_MATCHER_WORKER"] == "0"
