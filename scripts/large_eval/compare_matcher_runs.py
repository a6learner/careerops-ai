"""Compare two matcher runs over the same replayed parse runs and the same labels.

The overall label metrics of a run are measured only on its successful analyses, so a run that
succeeds on more (larger) jobs is scored on a different subset. This script also scores both runs
on the pairs that succeeded in both, which is the like-for-like comparison.

Usage:
    python -m scripts.large_eval.compare_matcher_runs --dataset evals/large_scale_v1 \
        --baseline-results <results.json> --baseline-state <state.jsonl> \
        --candidate-results <results.json> --candidate-state <state.jsonl> \
        --matcher-labels <dir> --requirements <pair_requirements_all.json> --out <compare.json>
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from scripts.large_eval.score import (
    bucket,
    keep_state_analysis_runs,
    latest_success,
    matcher_against_labels,
    wilson,
)


def load_pairs(results: Path, state: Path) -> dict[str, Any]:
    payload = json.loads(results.read_text(encoding="utf-8"))
    keep_state_analysis_runs(payload, state)
    return {
        key: job
        for key, job in payload["jobs"].items()
        if not key.startswith(("job:parser_only", "job:repeat")) and job["analysis_runs"]
    }


def first_outcome(job: dict[str, Any]) -> tuple[str, int]:
    first = job["analysis_runs"][0]
    parse = next(run for run in job["parse_runs"] if run["id"] == first["parse_run_id"])
    return first["error_code"] or "SUCCEEDED", len(parse["requirements"])


def outcome_label(error_code: str) -> str:
    return "ok" if error_code == "SUCCEEDED" else "fail"


def transitions(baseline: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    moves: Counter[str] = Counter()
    by_bucket: dict[str, Counter[str]] = {}
    for key in sorted(set(baseline) & set(candidate)):
        before, size = first_outcome(baseline[key])
        after, _ = first_outcome(candidate[key])
        move = f"{outcome_label(before)}->{outcome_label(after)}"
        moves[move] += 1
        by_bucket.setdefault(bucket(size), Counter())[move] += 1
    return {
        "pairs": sum(moves.values()),
        "first_attempt_transitions": dict(sorted(moves.items())),
        "transitions_by_requirement_count": {
            name: dict(sorted(counter.items())) for name, counter in sorted(by_bucket.items())
        },
    }


def verdict_changes(
    baseline: dict[str, Any], candidate: dict[str, Any], keys: list[str]
) -> dict[str, Any]:
    changes: Counter[str] = Counter()
    for key in keys:
        before = latest_success(baseline[key])
        after = latest_success(candidate[key])
        assert before is not None and after is not None
        old = {match["requirement_id"]: match["verdict"] for match in before["matches"]}
        for match in after["matches"]:
            changes[f"{old.get(match['requirement_id'])}->{match['verdict']}"] += 1
    total = sum(changes.values())
    unchanged = sum(
        count for move, count in changes.items() if len(set(move.split("->"))) == 1
    )
    return {
        "requirements": total,
        "same_verdict": wilson(unchanged, total),
        "transitions": dict(sorted(changes.items())),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--baseline-results", type=Path, required=True)
    parser.add_argument("--baseline-state", type=Path, required=True)
    parser.add_argument("--candidate-results", type=Path, required=True)
    parser.add_argument("--candidate-state", type=Path, required=True)
    parser.add_argument("--matcher-labels", type=Path, required=True)
    parser.add_argument("--requirements", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    baseline = load_pairs(args.baseline_results, args.baseline_state)
    candidate = load_pairs(args.candidate_results, args.candidate_state)
    both = sorted(
        key
        for key in set(baseline) & set(candidate)
        if latest_success(baseline[key]) is not None and latest_success(candidate[key]) is not None
    )
    labels, requirements = args.matcher_labels, args.requirements
    report = {
        "outcomes": transitions(baseline, candidate),
        "pairs_succeeded_in_both": len(both),
        "labels_on_pairs_succeeded_in_both": {
            "baseline": matcher_against_labels(
                args.dataset, {k: baseline[k] for k in both}, labels, requirements
            ),
            "candidate": matcher_against_labels(
                args.dataset, {k: candidate[k] for k in both}, labels, requirements
            ),
        },
        "verdict_changes_on_pairs_succeeded_in_both": verdict_changes(baseline, candidate, both),
    }
    args.out.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(report["outcomes"], indent=1))


if __name__ == "__main__":
    main()
