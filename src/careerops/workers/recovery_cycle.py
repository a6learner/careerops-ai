import asyncio
import json
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import asdict, dataclass
from typing import Literal

from careerops.core.config import Settings, get_settings
from careerops.services.analysis_run_recovery import AnalysisRunRecoveryResult
from careerops.services.embedding_recovery import EmbeddingRecoveryResult
from careerops.services.parse_run_recovery import ParseRunRecoveryResult
from careerops.workers.analysis_recovery import recover_analysis_runs
from careerops.workers.embedding_recovery import recover_embedding_runs
from careerops.workers.recovery import recover_parse_runs

RecoveryStepName = Literal["parse", "analysis", "embedding"]


@dataclass(frozen=True)
class RecoveryStepResult:
    name: RecoveryStepName
    reconciled: int = 0
    requeued: int = 0
    dispatched: int = 0
    dispatch_failed: int = 0
    error_type: str | None = None

    @property
    def failed(self) -> bool:
        return self.dispatch_failed > 0 or self.error_type is not None


@dataclass(frozen=True)
class RecoveryCycleResult:
    steps: tuple[RecoveryStepResult, ...]

    @property
    def failed(self) -> bool:
        return any(step.failed for step in self.steps)


RecoveryStepRunner = Callable[[], Awaitable[RecoveryStepResult]]


@dataclass(frozen=True)
class RecoveryStep:
    name: RecoveryStepName
    runner: RecoveryStepRunner


class UnsafeRecoveryProviderConfigurationError(RuntimeError):
    pass


def ensure_fake_provider_configuration(settings: Settings) -> None:
    unsafe_fields = [
        name
        for name, value in (
            ("llm_provider", settings.llm_provider),
            ("embedding_provider", settings.embedding_provider),
            ("evidence_matcher_provider", settings.evidence_matcher_provider),
        )
        if value != "fake"
    ]
    if unsafe_fields:
        joined_fields = ", ".join(unsafe_fields)
        raise UnsafeRecoveryProviderConfigurationError(
            f"recovery cycle requires fake providers; unsafe settings: {joined_fields}"
        )


async def _recover_parse_step() -> RecoveryStepResult:
    result: ParseRunRecoveryResult = await recover_parse_runs()
    return RecoveryStepResult(
        name="parse",
        requeued=result.requeued,
        dispatched=result.dispatched,
        dispatch_failed=result.dispatch_failed,
    )


async def _recover_analysis_step() -> RecoveryStepResult:
    result: AnalysisRunRecoveryResult = await recover_analysis_runs()
    return RecoveryStepResult(
        name="analysis",
        requeued=result.requeued,
        dispatched=result.dispatched,
        dispatch_failed=result.dispatch_failed,
    )


async def _recover_embedding_step() -> RecoveryStepResult:
    result: EmbeddingRecoveryResult = await recover_embedding_runs()
    return RecoveryStepResult(
        name="embedding",
        reconciled=result.reconciled,
        requeued=result.requeued,
        dispatched=result.dispatched,
        dispatch_failed=result.dispatch_failed,
    )


def default_recovery_steps() -> tuple[RecoveryStep, ...]:
    return (
        RecoveryStep(name="parse", runner=_recover_parse_step),
        RecoveryStep(name="analysis", runner=_recover_analysis_step),
        RecoveryStep(name="embedding", runner=_recover_embedding_step),
    )


async def run_recovery_cycle(
    steps: Sequence[RecoveryStep] | None = None,
    settings: Settings | None = None,
) -> RecoveryCycleResult:
    ensure_fake_provider_configuration(settings or get_settings())
    selected_steps = default_recovery_steps() if steps is None else steps
    results: list[RecoveryStepResult] = []
    for step in selected_steps:
        try:
            results.append(await step.runner())
        except Exception as exc:
            # One broken recovery path must not prevent the other durable queues
            # from being inspected. The nonzero exit still exposes the failure.
            results.append(
                RecoveryStepResult(
                    name=step.name,
                    error_type=type(exc).__name__,
                )
            )
    return RecoveryCycleResult(steps=tuple(results))


def main() -> None:
    try:
        result = asyncio.run(run_recovery_cycle())
    except UnsafeRecoveryProviderConfigurationError as exc:
        print(json.dumps({"error": str(exc)}, sort_keys=True))
        raise SystemExit(1) from exc
    print(json.dumps(asdict(result), sort_keys=True))
    if result.failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
