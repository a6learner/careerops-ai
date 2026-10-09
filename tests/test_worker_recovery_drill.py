import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest

from careerops.operations.worker_recovery_drill import (
    WorkerRecoveryDrillError,
    build_resources,
    fake_environment,
    render_plan,
    stop_worker,
    validate_database_name,
    verify_database_cleanup_identity,
    verify_redis_cleanup_identity,
)

RUN_ID = "20261006t160000z_1a2b3c4d"


def test_resources_stay_in_fixed_namespaces(tmp_path: Path) -> None:
    resources = build_resources(RUN_ID, temp_root=tmp_path)

    assert resources.database_name == f"careerops_p18b_{RUN_ID}"
    assert resources.database_comment == f"careerops-p1-8b:{RUN_ID}"
    assert resources.redis_container_name == "careerops-p18b-20261006t160000z-1a2b3c4d"
    assert resources.artifact_directory.is_relative_to(tmp_path / "careerops-ai" / "p1-8b")


@pytest.mark.parametrize(
    "database_name",
    ("careerops", "careerops_p18a_src_20261006t160000z_1a2b3c4d", "postgres"),
)
def test_database_validation_rejects_non_p18b_targets(database_name: str) -> None:
    with pytest.raises(WorkerRecoveryDrillError):
        validate_database_name(database_name)


def test_plan_is_non_mutating_and_provider_free(tmp_path: Path) -> None:
    plan = render_plan(build_resources(RUN_ID, temp_root=tmp_path))

    assert '"mutates_state": false' in plan
    assert '"provider_calls": false' in plan


def test_cleanup_identity_rejects_mismatched_sentinels(tmp_path: Path) -> None:
    resources = build_resources(RUN_ID, temp_root=tmp_path)

    with pytest.raises(WorkerRecoveryDrillError):
        verify_database_cleanup_identity(resources, "careerops-p1-8b:different")
    with pytest.raises(WorkerRecoveryDrillError):
        verify_redis_cleanup_identity(resources, "different")


def test_fake_environment_overrides_ambient_real_provider_settings(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("CAREEROPS_LLM_PROVIDER", "groq")
    monkeypatch.setenv("CAREEROPS_EMBEDDING_PROVIDER", "gemini")
    monkeypatch.setenv("CAREEROPS_EVIDENCE_MATCHER_PROVIDER", "groq")
    resources = build_resources(RUN_ID, temp_root=tmp_path)

    environment = fake_environment(resources, "redis://127.0.0.1:6380/0")

    assert environment["CAREEROPS_LLM_PROVIDER"] == "fake"
    assert environment["CAREEROPS_EMBEDDING_PROVIDER"] == "fake"
    assert environment["CAREEROPS_EVIDENCE_MATCHER_PROVIDER"] == "fake"
    assert environment["CAREEROPS_RUN_REAL_MATCHER_WORKER"] == "0"
    assert resources.database_name in environment["CAREEROPS_DATABASE_URL"]


def test_windows_worker_shutdown_targets_the_owned_process_tree(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    worker = Mock(spec=subprocess.Popen)
    worker.pid = 1234
    worker.poll.return_value = None
    completed = subprocess.CompletedProcess(args=(), returncode=0)
    run = Mock(return_value=completed)
    monkeypatch.setattr("careerops.operations.worker_recovery_drill.os.name", "nt")
    monkeypatch.setattr("careerops.operations.worker_recovery_drill.subprocess.run", run)

    stop_worker(worker)

    run.assert_called_once_with(
        ("taskkill", "/PID", "1234", "/T", "/F"),
        capture_output=True,
        text=True,
        check=False,
    )
    worker.wait.assert_called_once_with(timeout=10)
