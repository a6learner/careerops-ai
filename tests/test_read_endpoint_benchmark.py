import pytest

from careerops.operations.read_endpoint_benchmark import (
    BenchmarkError,
    nearest_rank,
    plan_execution_time_ms,
)


def test_nearest_rank_uses_documented_positions() -> None:
    values = [float(value) for value in range(1, 101)]

    assert nearest_rank(values, 0.50) == 50.0
    assert nearest_rank(values, 0.95) == 95.0


def test_nearest_rank_rejects_empty_samples() -> None:
    with pytest.raises(ValueError, match="At least one"):
        nearest_rank([], 0.95)


def test_plan_execution_time_reads_explain_json() -> None:
    assert plan_execution_time_ms([{"Execution Time": 1.25}]) == 1.25


def test_plan_execution_time_rejects_missing_shape() -> None:
    with pytest.raises(BenchmarkError, match="one JSON plan"):
        plan_execution_time_ms({})


@pytest.mark.parametrize("percentile", [0.0, -0.1, 1.1])
def test_nearest_rank_rejects_invalid_percentiles(percentile: float) -> None:
    with pytest.raises(ValueError, match="Percentile"):
        nearest_rank([1.0], percentile)
