"""Replay the exact large_scale_v1 parse results into a fresh evaluation database.

Re-parsing would mix matcher changes with parser nondeterminism (8/19 identical repeat parses
in large_scale_v1). This script copies, for each labeled pair, the parse run the original
analysis used, keeping its parse-run ID and requirement IDs so the committed matcher labels
apply unchanged. The rows are written as succeeded parse runs for the jobs that the driver's
`setup` stage created, and a `parse:<pair>` record is added to the driver state so
`--stage analysis` can submit them.

Usage (after `drive_pipeline --stage setup` and embeddings have completed):
    python -m scripts.large_eval.replay_parses --dataset evals/large_scale_v1 \
        --state <state.jsonl> --results <large_scale_v1 results_real_run.json> \
        --requirements-out <pair_requirements_all.json>
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from careerops.adapters.groq_requirement_parser import is_section_heading
from scripts.large_eval.drive_pipeline import State

LABEL_ROUNDS = ("m1", "m2", "m3", "m4")


def load_pair_requirements(dataset: Path) -> list[dict[str, Any]]:
    pairs: list[dict[str, Any]] = []
    for round_name in LABEL_ROUNDS:
        path = dataset / "labels" / "matcher" / round_name / "pair_requirements.json"
        pairs.extend(json.loads(path.read_text(encoding="utf-8")))
    if len({pair["pair_id"] for pair in pairs}) != len(pairs):
        raise ValueError("a pair appears in more than one label round")
    return pairs


def original_parse_runs(results: Path) -> dict[str, dict[str, Any]]:
    jobs = json.loads(results.read_text(encoding="utf-8"))["jobs"]
    return {run["id"]: run for job in jobs.values() for run in job["parse_runs"]}


async def replay(
    database_url: str,
    state: State,
    pairs: list[dict[str, Any]],
    parse_runs: dict[str, dict[str, Any]],
    drop_headings: bool,
) -> int:
    engine = create_async_engine(database_url)
    inserted = 0
    try:
        async with engine.begin() as connection:
            for pair in pairs:
                result_key = f"parse:{pair['pair_id']}"
                if state.get(result_key):
                    continue
                job = state.get(f"job:{pair['pair_id']}")
                if job is None:
                    raise ValueError(f"{pair['pair_id']}: job missing; run the setup stage first")
                original = parse_runs[pair["parse_run_id"]]
                expected_ids = {req["requirement_id"] for req in pair["requirements"]}
                if {req["id"] for req in original["requirements"]} != expected_ids:
                    raise ValueError(f"{pair['pair_id']}: parse run differs from labeled set")
                kept = [
                    requirement
                    for requirement in original["requirements"]
                    if not (drop_headings and is_section_heading(requirement["text"]))
                ]
                if not kept:
                    state.put(
                        result_key,
                        {
                            "job_key": f"job:{pair['pair_id']}",
                            "final": {"status": "skipped", "error_code": "REPLAY_ONLY_HEADINGS"},
                            "attempts": [],
                            "replayed_from": original["id"],
                            "headings_dropped": len(original["requirements"]),
                        },
                    )
                    continue
                row = (
                    await connection.execute(
                        text(
                            "SELECT user_id, version, description_hash, raw_description "
                            "FROM jobs WHERE id = :job"
                        ),
                        {"job": job["job_id"]},
                    )
                ).one()
                fingerprint = hashlib.sha256(
                    f"{job['job_id']}:{row.version}:{row.description_hash}:"
                    f"{original['prompt_version']}".encode()
                ).hexdigest()
                await connection.execute(
                    text(
                        "INSERT INTO parse_runs (id, user_id, job_id, status, idempotency_key, "
                        "input_fingerprint, input_text, model_name, prompt_version, attempt, "
                        "latency_ms, input_tokens, output_tokens, started_at, finished_at) "
                        "VALUES (:id, :user_id, :job_id, 'succeeded', :key, :fingerprint, "
                        ":input_text, :model, :prompt, 1, :latency, :input_tokens, "
                        ":output_tokens, now(), now())"
                    ),
                    {
                        "id": original["id"],
                        "user_id": row.user_id,
                        "job_id": job["job_id"],
                        "key": f"replay-{original['id']}",
                        "fingerprint": fingerprint,
                        "input_text": row.raw_description,
                        "model": original["model_name"],
                        "prompt": original["prompt_version"],
                        "latency": original["latency_ms"],
                        "input_tokens": original["input_tokens"],
                        "output_tokens": original["output_tokens"],
                    },
                )
                for requirement in kept:
                    await connection.execute(
                        text(
                            "INSERT INTO job_requirements (id, job_id, parse_run_id, category, "
                            "text, skill_normalized, source_span_start, source_span_end) VALUES "
                            "(:id, :job_id, :parse_run_id, :category, :text, :skill, :start, :end)"
                        ),
                        {
                            "id": requirement["id"],
                            "job_id": job["job_id"],
                            "parse_run_id": original["id"],
                            "category": requirement["category"],
                            "text": requirement["text"],
                            "skill": requirement["skill_normalized"],
                            "start": requirement["source_span_start"],
                            "end": requirement["source_span_end"],
                        },
                    )
                state.put(
                    result_key,
                    {
                        "job_key": f"job:{pair['pair_id']}",
                        "final": {"id": original["id"], "status": "succeeded", "error_code": None},
                        "attempts": [],
                        "replayed_from": original["id"],
                        "requirement_count": len(kept),
                        "headings_dropped": len(original["requirements"]) - len(kept),
                    },
                )
                inserted += 1
    finally:
        await engine.dispose()
    return inserted


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--requirements-out", type=Path, required=True)
    parser.add_argument(
        "--drop-headings",
        action="store_true",
        help="leave out requirements that parse-v4 would never offer (is_section_heading)",
    )
    args = parser.parse_args()
    pairs = load_pair_requirements(args.dataset)
    args.requirements_out.write_text(json.dumps(pairs, indent=1) + "\n", encoding="utf-8")
    state = State.load(args.state)
    parse_runs = original_parse_runs(args.results)
    inserted = asyncio.run(
        replay(
            os.environ["CAREEROPS_DATABASE_URL"], state, pairs, parse_runs, args.drop_headings
        )
    )
    print(json.dumps({"pairs": len(pairs), "parse_runs_inserted": inserted}))


if __name__ == "__main__":
    main()
