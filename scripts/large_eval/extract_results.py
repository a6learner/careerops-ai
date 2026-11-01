"""Export persisted parse/analysis results for every job in a driver state file.

Usage:
    python -m scripts.large_eval.extract_results --state <state.jsonl> --out <results.json>
Reads CAREEROPS_DATABASE_URL. Read-only.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from scripts.large_eval.drive_pipeline import State

RUN_COLUMNS = (
    "id, status, error_code, latency_ms, input_tokens, output_tokens, model_name, "
    "prompt_version, attempt, created_at, finished_at"
)


def jsonable(row: Any) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in row._mapping.items():
        out[key] = value if isinstance(value, int | float | str | bool | type(None)) else str(value)
    return out


async def export(database_url: str, state: State) -> dict[str, Any]:
    engine = create_async_engine(database_url)
    experiences = {
        record["experience_id"]: key.removeprefix("experience:")
        for key, record in state.records.items()
        if key.startswith("experience:")
    }
    jobs: dict[str, Any] = {}
    try:
        async with engine.connect() as connection:
            for key, record in state.records.items():
                if not key.startswith("job:"):
                    continue
                job_id = record["job_id"]
                parse_runs = [
                    jsonable(row)
                    for row in await connection.execute(
                        text(
                            f"SELECT {RUN_COLUMNS} FROM parse_runs WHERE job_id = :job "
                            "ORDER BY created_at"
                        ),
                        {"job": job_id},
                    )
                ]
                for run in parse_runs:
                    run["requirements"] = [
                        jsonable(row)
                        for row in await connection.execute(
                            text(
                                "SELECT id, category, text, skill_normalized, source_span_start, "
                                "source_span_end FROM job_requirements WHERE parse_run_id = :run "
                                "ORDER BY source_span_start"
                            ),
                            {"run": run["id"]},
                        )
                    ]
                analysis_runs = [
                    jsonable(row)
                    for row in await connection.execute(
                        text(
                            f"SELECT {RUN_COLUMNS}, parse_run_id, validation_failure_count "
                            "FROM analysis_runs WHERE job_id = :job ORDER BY created_at"
                        ),
                        {"job": job_id},
                    )
                ]
                for run in analysis_runs:
                    matches = [
                        jsonable(row)
                        for row in await connection.execute(
                            text(
                                "SELECT requirement_id, experience_id, experience_version, "
                                "verdict, "
                                "quote, quote_valid, confidence FROM evidence_matches "
                                "WHERE analysis_run_id = :run"
                            ),
                            {"run": run["id"]},
                        )
                    ]
                    for match in matches:
                        match["exp_key"] = experiences.get(str(match["experience_id"]))
                    run["matches"] = matches
                jobs[key] = {
                    **record,
                    "parse_runs": parse_runs,
                    "analysis_runs": analysis_runs,
                }
    finally:
        await engine.dispose()
    return {"jobs": jobs, "experience_keys": experiences}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    state = State.load(args.state)
    payload = asyncio.run(export(os.environ["CAREEROPS_DATABASE_URL"], state))
    args.out.write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"exported {len(payload['jobs'])} jobs")


if __name__ == "__main__":
    main()
