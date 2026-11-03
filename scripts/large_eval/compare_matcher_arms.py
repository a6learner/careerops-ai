"""Score several matcher runs ("arms") on the pairs that succeeded in every arm.

Each arm is `name=<results.json>,<driver_state.jsonl>`. Pairs come from an order file (a JSON list
of `job:<pair_id>` keys). Over-claim breakdowns use the same pairs and the label gap reasons.

Usage:
    python -m scripts.large_eval.compare_matcher_arms --dataset evals/large_scale_v1 \
        --matcher-labels <dir> --requirements <pair_requirements_all.json> --order <order.json> \
        --arm batch6=<results.json>,<state.jsonl> --arm single=<...> --out <arms.json>
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from scripts.large_eval.compare_matcher_runs import load_pairs
from scripts.large_eval.labels import load_matcher_labels, load_resumes
from scripts.large_eval.score import COVERAGE, OVERCLAIM, latest_success, matcher_against_labels


def heading_like(text: str) -> bool:
    plain = re.sub(r"<[^>]+>", "", text).strip()
    return len(plain.split()) <= 4 or plain.endswith(":") or plain.isupper()


def overclaim_breakdown(
    dataset: Path,
    runs: dict[str, Any],
    keys: list[str],
    labels_dir: Path,
    requirements: Path,
) -> dict[str, Any]:
    pairs = {p["pair_id"]: p for p in json.loads(requirements.read_text(encoding="utf-8"))}
    resumes = load_resumes(dataset)
    labels = load_matcher_labels(labels_dir, resumes, pairs)
    texts = {r["requirement_id"]: r["text"] for p in pairs.values() for r in p["requirements"]}
    kinds: Counter[str] = Counter()
    strata: Counter[str] = Counter()
    for key in keys:
        run = latest_success(runs[key])
        assert run is not None
        pair_id = key.removeprefix("job:")
        predicted = {match["requirement_id"]: match for match in run["matches"]}
        for entry in labels[pair_id].labels:
            if entry.requirement_id not in predicted:
                continue
            got = COVERAGE[predicted[entry.requirement_id]["verdict"]]
            expected = COVERAGE[entry.verdict]
            if (expected, got) not in OVERCLAIM:
                continue
            suffix = " (heading-like text)" if heading_like(texts[entry.requirement_id]) else ""
            kinds[f"{expected}->{got}{suffix}"] += 1
            strata[resumes[pairs[pair_id]["resume_id"]].stratum] += 1
    return {
        "by_kind": dict(sorted(kinds.items())),
        "by_resume_stratum": dict(sorted(strata.items())),
    }


def restrict_to_shared_requirements(arms: dict[str, dict[str, Any]], keys: list[str]) -> None:
    for key in keys:
        runs = [latest_success(arm[key]) for arm in arms.values()]
        shared = set.intersection(
            *({match["requirement_id"] for match in run["matches"]} for run in runs if run)
        )
        for arm in arms.values():
            job = arm[key]
            for run in job["analysis_runs"]:
                run["matches"] = [m for m in run["matches"] if m["requirement_id"] in shared]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--matcher-labels", type=Path, required=True)
    parser.add_argument("--requirements", type=Path, required=True)
    parser.add_argument("--order", type=Path, required=True)
    parser.add_argument("--arm", action="append", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--shared-requirements-only",
        action="store_true",
        help="score only requirements that every arm analysed (e.g. after a parser filter)",
    )
    args = parser.parse_args()

    arms: dict[str, dict[str, Any]] = {}
    for spec in args.arm:
        name, paths = spec.split("=", 1)
        results, state = paths.split(",", 1)
        arms[name] = load_pairs(Path(results), Path(state))
    order: list[str] = json.loads(args.order.read_text(encoding="utf-8"))
    keys = [
        key
        for key in order
        if all(key in runs and latest_success(runs[key]) is not None for runs in arms.values())
    ]
    if args.shared_requirements_only:
        restrict_to_shared_requirements(arms, keys)
    report: dict[str, Any] = {
        "order": str(args.order),
        "pairs_succeeded_in_all_arms": len(keys),
        "shared_requirements_only": args.shared_requirements_only,
    }
    for name, runs in arms.items():
        succeeded = sum(key in runs and latest_success(runs[key]) is not None for key in order)
        subset = {key: runs[key] for key in keys}
        report[name] = {
            "pairs_in_order_succeeded": succeeded,
            "labels_on_common_pairs": matcher_against_labels(
                args.dataset, subset, args.matcher_labels, args.requirements
            ),
            "overclaims_on_common_pairs": overclaim_breakdown(
                args.dataset, runs, keys, args.matcher_labels, args.requirements
            ),
        }
    args.out.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    summary = {
        name: (value["pairs_in_order_succeeded"], value["labels_on_common_pairs"]["overclaim_rate"])
        for name, value in report.items()
        if isinstance(value, dict)
    }
    print(json.dumps({"pairs_succeeded_in_all_arms": len(keys), "arms": summary}, indent=1))


if __name__ == "__main__":
    main()
