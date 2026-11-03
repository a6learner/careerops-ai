"""Paired, per-requirement comparison of two matcher runs against the same labels.

For the pairs both runs completed, it counts requirements where only one run over-claims (or only
one run gets the coverage class exactly right) and gives an exact two-sided McNemar p-value. It also
scores the pairs only the second run completed ("rescued").

Usage:
    python -m scripts.large_eval.paired_matcher_check --dataset evals/large_scale_v1 \
        --matcher-labels <dir> --requirements <pair_requirements_all.json> \
        --compare name=<results_a>,<state_a>|<results_b>,<state_b> [--compare ...] \
        --out <report.json>
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

from scripts.large_eval.compare_matcher_runs import load_pairs
from scripts.large_eval.labels import load_matcher_labels, load_resumes
from scripts.large_eval.score import COVERAGE, OVERCLAIM, latest_success, wilson


def mcnemar_exact_p(only_first: int, only_second: int) -> float:
    total = only_first + only_second
    if total == 0:
        return 1.0
    tail = sum(math.comb(total, i) for i in range(min(only_first, only_second) + 1))
    return min(1.0, 2 * tail / 2**total)


def verdicts(run: dict[str, Any]) -> dict[str, str]:
    return {match["requirement_id"]: match["verdict"] for match in run["matches"]}


LONG_OUTPUT_PER_BATCH = 800


def compare(
    labels: dict[str, Any],
    first: dict[str, Any],
    second: dict[str, Any],
    batch_size: int,
) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    by_length: dict[str, Counter[str]] = {"short": Counter(), "long": Counter()}
    rescued: Counter[str] = Counter()
    for key, job in second.items():
        run_b = latest_success(job)
        if run_b is None:
            continue
        run_a = latest_success(first[key]) if key in first else None
        got_b = verdicts(run_b)
        got_a = verdicts(run_a) if run_a is not None else {}
        per_batch = (run_b["output_tokens"] or 0) / math.ceil(len(got_b) / batch_size)
        length = by_length["long" if per_batch > LONG_OUTPUT_PER_BATCH else "short"]
        for entry in labels[key.removeprefix("job:")].labels:
            if entry.requirement_id not in got_b:
                continue
            expected = COVERAGE[entry.verdict]
            over_b = (expected, COVERAGE[got_b[entry.requirement_id]]) in OVERCLAIM
            if run_a is None:
                rescued["requirements"] += 1
                rescued["overclaim"] += over_b
                continue
            if entry.requirement_id not in got_a:
                continue
            over_a = (expected, COVERAGE[got_a[entry.requirement_id]]) in OVERCLAIM
            exact_a = expected == COVERAGE[got_a[entry.requirement_id]]
            exact_b = expected == COVERAGE[got_b[entry.requirement_id]]
            for tally in (counts, length):
                tally["requirements"] += 1
                tally["same_verdict"] += got_a[entry.requirement_id] == got_b[entry.requirement_id]
                tally["overclaim_only_first"] += over_a and not over_b
                tally["overclaim_only_second"] += over_b and not over_a
                tally["exact_only_first"] += exact_a and not exact_b
                tally["exact_only_second"] += exact_b and not exact_a
    return {
        "shared_pairs": {
            **dict(counts),
            "overclaim_mcnemar_exact_p": round(
                mcnemar_exact_p(counts["overclaim_only_first"], counts["overclaim_only_second"]), 3
            ),
            "exact_mcnemar_exact_p": round(
                mcnemar_exact_p(counts["exact_only_first"], counts["exact_only_second"]), 3
            ),
        },
        "shared_pairs_by_second_run_output": {
            "definition": (
                "second run's output tokens / ceil(requirements / batch_size); "
                f"long if above {LONG_OUTPUT_PER_BATCH}"
            ),
            **{name: dict(tally) for name, tally in by_length.items()},
        },
        "pairs_only_second_completed": {
            "requirements": rescued["requirements"],
            "overclaim_rate": wilson(rescued["overclaim"], rescued["requirements"]),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--matcher-labels", type=Path, required=True)
    parser.add_argument("--requirements", type=Path, required=True)
    parser.add_argument("--compare", action="append", required=True)
    parser.add_argument("--batch-size", type=int, default=6)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    pairs = {p["pair_id"]: p for p in json.loads(args.requirements.read_text(encoding="utf-8"))}
    labels = load_matcher_labels(args.matcher_labels, load_resumes(args.dataset), pairs)
    report: dict[str, Any] = {}
    for spec in args.compare:
        name, runs = spec.split("=", 1)
        first, second = (load_pairs(*map(Path, side.split(",", 1))) for side in runs.split("|"))
        report[name] = compare(labels, first, second, args.batch_size)
    args.out.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
