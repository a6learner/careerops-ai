"""Freeze the parsed requirements of each pair (input to blind matcher labeling).

Usage:
    python -m scripts.large_eval.build_requirements --results <results.json> \
        --dataset evals/large_scale_v1 --out <pair_requirements.json>
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.large_eval.score import succeeded_parse


def build(results: dict[str, Any], pairs: list[dict[str, str]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for pair in pairs:
        job = results["jobs"].get(f"job:{pair['pair_id']}")
        parse = succeeded_parse(job) if job else None
        if parse is None:
            continue
        out.append(
            {
                "pair_id": pair["pair_id"],
                "resume_id": pair["resume_id"],
                "jd_id": pair["jd_id"],
                "parse_run_id": parse["id"],
                "requirements": [
                    {
                        "requirement_id": req["id"],
                        "category": req["category"],
                        "text": req["text"],
                        "skill_normalized": req["skill_normalized"],
                    }
                    for req in parse["requirements"]
                ],
            }
        )
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    results = json.loads(args.results.read_text(encoding="utf-8"))
    pairs = json.loads((args.dataset / "pairs.json").read_text(encoding="utf-8"))["pairs"]
    frozen = build(results, pairs)
    args.out.write_text(json.dumps(frozen, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    total = sum(len(item["requirements"]) for item in frozen)
    print(f"froze {len(frozen)} pairs, {total} requirements")


if __name__ == "__main__":
    main()
