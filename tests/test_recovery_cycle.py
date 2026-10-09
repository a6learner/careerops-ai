import json

import pytest

from careerops.core.config import Settings
from careerops.workers import recovery_cycle
from careerops.workers.recovery_cycle import RecoveryStep, RecoveryStepResult


def fake_settings() -> Settings:
    return Settings(
        llm_provider="fake",
        embedding_provider="fake",
        evidence_matcher_provider="fake",
    )


def make_step(
    name: recovery_cycle.RecoveryStepName,
    *,
    result: RecoveryStepResult | None = None,
    error: Exception | None = None,
) -> RecoveryStep:
    async def runner() -> RecoveryStepResult:
        if error is not None:
            raise error
        assert result is not None
        return result

    return RecoveryStep(name=name, runner=runner)


@pytest.mark.asyncio
async def test_cycle_requires_every_provider_to_be_fake_before_running_steps() -> None:
    called = False

    async def runner() -> RecoveryStepResult:
        nonlocal called
        called = True
        return RecoveryStepResult(name="parse")

    with pytest.raises(recovery_cycle.UnsafeRecoveryProviderConfigurationError):
        await recovery_cycle.run_recovery_cycle(
            steps=(RecoveryStep(name="parse", runner=runner),),
            settings=Settings(
                llm_provider="fake",
                embedding_provider="fake",
                evidence_matcher_provider="groq",
            ),
        )

    assert not called


@pytest.mark.asyncio
async def test_cycle_runs_every_step_and_preserves_partial_failure() -> None:
    parse = make_step(
        "parse",
        result=RecoveryStepResult(name="parse", requeued=1, dispatched=1),
    )
    analysis = make_step("analysis", error=RuntimeError("database unavailable"))
    embedding = make_step(
        "embedding",
        result=RecoveryStepResult(name="embedding", reconciled=2, dispatched=2),
    )

    result = await recovery_cycle.run_recovery_cycle(
        steps=(parse, analysis, embedding),
        settings=fake_settings(),
    )

    assert result.failed
    assert result.steps == (
        RecoveryStepResult(name="parse", requeued=1, dispatched=1),
        RecoveryStepResult(name="analysis", error_type="RuntimeError"),
        RecoveryStepResult(name="embedding", reconciled=2, dispatched=2),
    )


def test_command_prints_machine_readable_summary_and_exits_on_failure(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def failed_cycle() -> recovery_cycle.RecoveryCycleResult:
        return recovery_cycle.RecoveryCycleResult(
            steps=(RecoveryStepResult(name="analysis", dispatch_failed=1),)
        )

    monkeypatch.setattr(recovery_cycle, "run_recovery_cycle", failed_cycle)

    with pytest.raises(SystemExit) as raised:
        recovery_cycle.main()

    assert raised.value.code == 1
    assert json.loads(capsys.readouterr().out) == {
        "steps": [
            {
                "dispatch_failed": 1,
                "dispatched": 0,
                "error_type": None,
                "name": "analysis",
                "reconciled": 0,
                "requeued": 0,
            }
        ]
    }
