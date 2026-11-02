"""Resumable driver that pushes the large_scale_v1 dataset through the real HTTP API.

Every provider-backed submission is paced, and every outcome is appended to a JSONL
checkpoint so an interrupted chunk never re-sends finished work.

Usage:
    python -m scripts.large_eval.drive_pipeline --dataset evals/large_scale_v1 \
        --state <scratch>/runs/state.jsonl --api http://127.0.0.1:8010 \
        --stage setup|parse|analysis|cv_import [--limit N] [--pace SECONDS]

Exit codes: 0 done or chunk limit reached, 3 provider quota suspected (rerun later).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from scripts.large_eval.models import JdRecord, ResumeRecord

PASSWORD = "large-eval-password-2026"
TOKEN_TTL_SECONDS = 20 * 60
POLL_SECONDS = 2.0
RUN_TIMEOUT_SECONDS = 600.0
# PARSER_FAILED hides the HTTP status (observed: Groq 429 tokens-per-minute, 413, 400), so it is
# retried after a cooldown; every attempt is still recorded.
RETRYABLE_CODES = {"MATCHER_PROVIDER_RATE_LIMITED", "ANALYSIS_RATE_LIMITED", "PARSER_FAILED"}
MAX_PROVIDER_RETRIES = 3
QUOTA_STREAK = 3
# A key that keeps failing after this many attempts is deterministic (e.g. HTTP 400/413), not quota.
MAX_TOTAL_ATTEMPTS = 20
TERMINAL = {"succeeded", "failed"}


@dataclass
class State:
    path: Path
    records: dict[str, dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> State:
        state = cls(path)
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    event = json.loads(line)
                    state.records[event["key"]] = event
        return state

    def get(self, key: str) -> dict[str, Any] | None:
        return self.records.get(key)

    def put(self, key: str, data: dict[str, Any]) -> None:
        event = {"key": key, "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), **data}
        self.records[key] = event
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event) + "\n")


@dataclass
class Session:
    api: str
    email: str
    token: str = ""
    issued: float = 0.0

    def headers(self, client: httpx.Client) -> dict[str, str]:
        if time.monotonic() - self.issued > TOKEN_TTL_SECONDS:
            response = client.post(
                f"{self.api}/api/v1/auth/login", json={"email": self.email, "password": PASSWORD}
            )
            response.raise_for_status()
            self.token = response.json()["access_token"]
            self.issued = time.monotonic()
        return {"Authorization": f"Bearer {self.token}"}


class Pacer:
    def __init__(self, seconds: float) -> None:
        self.seconds = seconds
        self.last = 0.0

    def wait(self) -> None:
        delay = self.last + self.seconds - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        self.last = time.monotonic()


def email_for(user_key: str, run_tag: str) -> str:
    return f"largeeval-{run_tag}-{user_key}@example.com"


def load_dataset(
    dataset: Path,
) -> tuple[dict[str, JdRecord], dict[str, ResumeRecord], dict[str, Any]]:
    jds = {
        record["jd_id"]: JdRecord.model_validate(record)
        for record in json.loads((dataset / "jds.json").read_text(encoding="utf-8"))
    }
    resumes = {
        record["resume_id"]: ResumeRecord.model_validate(record)
        for record in json.loads((dataset / "resumes.json").read_text(encoding="utf-8"))
    }
    pairs = json.loads((dataset / "pairs.json").read_text(encoding="utf-8"))
    return jds, resumes, pairs


def user_keys(pairs: dict[str, Any]) -> list[str]:
    keys = sorted({pair["resume_id"] for pair in pairs["pairs"]})
    return [*keys, "parser_only"]


def ensure_user(client: httpx.Client, state: State, api: str, user_key: str, tag: str) -> Session:
    email = email_for(user_key, tag)
    if state.get(f"user:{user_key}") is None:
        response = client.post(
            f"{api}/api/v1/auth/register", json={"email": email, "password": PASSWORD}
        )
        if response.status_code not in {201, 409}:
            response.raise_for_status()
        state.put(f"user:{user_key}", {"email": email})
    return Session(api=api, email=email)


def stage_setup(
    client: httpx.Client,
    state: State,
    api: str,
    tag: str,
    jds: dict[str, JdRecord],
    resumes: dict[str, ResumeRecord],
    pairs: dict[str, Any],
) -> None:
    sessions = {key: ensure_user(client, state, api, key, tag) for key in user_keys(pairs)}
    for resume in resumes.values():
        session = sessions[resume.resume_id]
        for exp in resume.experiences:
            key = f"experience:{exp.exp_key}"
            if state.get(key):
                continue
            response = client.post(
                f"{api}/api/v1/experiences",
                headers=session.headers(client),
                json={
                    "title": exp.title,
                    "kind": exp.kind,
                    "description": exp.description,
                    "skills": list(exp.skills),
                    "outcome": exp.outcome,
                },
            )
            response.raise_for_status()
            body = response.json()
            state.put(key, {"experience_id": body["id"], "version": body["version"]})
    jobs: list[tuple[str, str, str]] = [
        (f"job:{pair['pair_id']}", pair["resume_id"], pair["jd_id"]) for pair in pairs["pairs"]
    ]
    jobs += [
        (f"job:parser_only:{jd_id}", "parser_only", jd_id) for jd_id in pairs["parser_only_jd_ids"]
    ]
    for key, user_key, jd_id in jobs:
        if state.get(key):
            continue
        jd = jds[jd_id]
        response = client.post(
            f"{api}/api/v1/jobs",
            headers=sessions[user_key].headers(client),
            json={
                "company": jd.company,
                "title": jd.title,
                "raw_description": jd.raw_description,
                "source_url": jd.source_url,
                "location": (jd.location or "").strip() or None,
            },
        )
        response.raise_for_status()
        state.put(key, {"job_id": response.json()["id"], "user_key": user_key, "jd_id": jd_id})


async def embedding_status(database_url: str) -> dict[str, int]:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            rows = await connection.execute(
                text(
                    "SELECT (embedding IS NOT NULL) AS done, count(*) AS n FROM experiences "
                    "WHERE deleted_at IS NULL GROUP BY 1"
                )
            )
            return {("embedded" if row.done else "pending"): int(row.n) for row in rows}
    finally:
        await engine.dispose()


def stage_cv_import(client: httpx.Client, state: State, api: str, tag: str, dataset: Path) -> None:
    """Upload every rendered CV (no model involved) and record the drafts produced."""
    session = ensure_user(client, state, api, "cv_import", tag)
    for path in sorted((dataset / "cv_files").iterdir()):
        key = f"cv_import:{path.name}"
        if state.get(key):
            continue
        media = (
            "text/markdown"
            if path.suffix == ".md"
            else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        response = client.post(
            f"{api}/api/v1/cv-imports",
            headers={
                **session.headers(client),
                "Idempotency-Key": f"large-eval-cv-{uuid.uuid4()}",
            },
            files={"file": (path.name, path.read_bytes(), media)},
        )
        response.raise_for_status()
        body = poll_run(client, session, f"{api}/api/v1/cv-imports/{response.json()['id']}")
        drafts = body.get("drafts", [])
        state.put(
            key,
            {
                "status": body["status"],
                "error_code": body.get("error_code"),
                "document_type": body.get("document_type"),
                "draft_count": len(drafts),
                "draft_titles": [draft["title"] for draft in drafts],
                "draft_skill_counts": [len(draft["skills"]) for draft in drafts],
            },
        )
        print(f"{key}: {body['status']} drafts={len(drafts)}", flush=True)


def poll_run(client: httpx.Client, session: Session, path: str) -> dict[str, Any]:
    deadline = time.monotonic() + RUN_TIMEOUT_SECONDS
    while True:
        response = client.get(path, headers=session.headers(client))
        response.raise_for_status()
        body: dict[str, Any] = response.json()
        if body["status"] in TERMINAL or time.monotonic() > deadline:
            return body
        time.sleep(POLL_SECONDS)


def summarize_run(body: dict[str, Any]) -> dict[str, Any]:
    keep = (
        "id",
        "status",
        "error_code",
        "latency_ms",
        "input_tokens",
        "output_tokens",
        "model_name",
        "prompt_version",
        "validation_failure_count",
    )
    summary = {name: body.get(name) for name in keep}
    if "requirements" in body:
        summary["requirement_count"] = len(body["requirements"])
    if "matches" in body:
        summary["match_count"] = len(body["matches"])
    return summary


def is_rate_limited(body: dict[str, Any]) -> bool:
    return (body.get("error_code") or "") in RETRYABLE_CODES


def run_provider_stage(
    client: httpx.Client,
    state: State,
    api: str,
    tag: str,
    kind: str,
    keys: list[str],
    limit: int | None,
    pace: Pacer,
    cooldown: float,
    retry_failed: bool = False,
) -> int:
    sessions: dict[str, Session] = {}
    done = 0
    rate_limit_streak = 0
    for job_key in keys:
        result_key = f"{kind}:{job_key.removeprefix('job:')}"
        previous = state.get(result_key)
        if previous is not None and not (
            retry_failed
            and previous["final"].get("error_code") in RETRYABLE_CODES
            and len(previous["attempts"]) < MAX_TOTAL_ATTEMPTS
        ):
            continue
        job = state.get(job_key)
        if job is None:
            continue
        user_key = job["user_key"]
        session = sessions.setdefault(user_key, Session(api=api, email=email_for(user_key, tag)))
        attempts: list[dict[str, Any]] = list(previous["attempts"]) if previous else []
        body: dict[str, Any] = {}
        for _ in range(MAX_PROVIDER_RETRIES):
            pace.wait()
            body = submit(client, session, api, kind, job_key, job, state)
            attempts.append(summarize_run(body))
            if not is_rate_limited(body):
                break
            print(f"{result_key}: rate limited, cooling down {cooldown:.0f}s", flush=True)
            time.sleep(cooldown)
        first_limited = is_rate_limited(body)
        rate_limit_streak = rate_limit_streak + 1 if first_limited else 0
        state.put(
            result_key,
            {
                "job_key": job_key,
                "final": attempts[-1],
                "attempts": attempts,
                "first_attempt_status": attempts[0]["status"],
                "first_attempt_error": attempts[0]["error_code"],
            },
        )
        print(f"{result_key}: {attempts[-1]['status']} {attempts[-1]['error_code']}", flush=True)
        if rate_limit_streak >= QUOTA_STREAK:
            print("provider quota suspected; stopping chunk", flush=True)
            return 3
        done += 1
        if limit is not None and done >= limit:
            break
    return 0


def submit(
    client: httpx.Client,
    session: Session,
    api: str,
    kind: str,
    job_key: str,
    job: dict[str, Any],
    state: State,
) -> dict[str, Any]:
    job_id = job["job_id"]
    headers = {**session.headers(client), "Idempotency-Key": f"large-eval-{uuid.uuid4()}"}
    if kind == "parse":
        response = client.post(f"{api}/api/v1/jobs/{job_id}/parse-runs", headers=headers)
        response.raise_for_status()
        run = response.json()
        return poll_run(client, session, f"{api}/api/v1/jobs/{job_id}/parse-runs/{run['id']}")
    parse = state.get(f"parse:{job_key.removeprefix('job:')}")
    if parse is None or parse["final"]["status"] != "succeeded":
        return {"status": "skipped", "error_code": "NO_SUCCEEDED_PARSE"}
    response = client.post(
        f"{api}/api/v1/jobs/{job_id}/analysis-runs",
        headers=headers,
        json={"parse_run_id": parse["final"]["id"]},
    )
    if response.status_code == 429:
        return {"status": "failed", "error_code": "ANALYSIS_RATE_LIMITED"}
    response.raise_for_status()
    run = response.json()
    return poll_run(client, session, f"{api}/api/v1/jobs/{job_id}/analysis-runs/{run['id']}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--api", default="http://127.0.0.1:8010")
    parser.add_argument("--tag", default="v1")
    parser.add_argument(
        "--stage", choices=["setup", "embeddings", "parse", "analysis", "cv_import"], required=True
    )
    parser.add_argument("--keys", choices=["pairs", "parser_only", "all"], default="all")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--pace", type=float, default=25.0)
    parser.add_argument("--cooldown", type=float, default=120.0)
    parser.add_argument("--retry-failed", action="store_true")
    parser.add_argument("--order", type=Path, help="optional JSON list of job keys to run in order")
    args = parser.parse_args()

    jds, resumes, pairs = load_dataset(args.dataset)
    state = State.load(args.state)
    with httpx.Client(timeout=30.0) as client:
        if args.stage == "setup":
            stage_setup(client, state, args.api, args.tag, jds, resumes, pairs)
            return 0
        if args.stage == "cv_import":
            stage_cv_import(client, state, args.api, args.tag, args.dataset)
            return 0
        if args.stage == "embeddings":
            print(json.dumps(asyncio.run(embedding_status(os.environ["CAREEROPS_DATABASE_URL"]))))
            return 0
        if args.order:
            keys = json.loads(args.order.read_text(encoding="utf-8"))
        else:
            keys = [key for key in state.records if key.startswith("job:")]
            if args.keys == "pairs":
                keys = [key for key in keys if not key.startswith("job:parser_only:")]
            elif args.keys == "parser_only":
                keys = [key for key in keys if key.startswith("job:parser_only:")]
        return run_provider_stage(
            client,
            state,
            args.api,
            args.tag,
            args.stage,
            keys,
            args.limit,
            Pacer(args.pace),
            args.cooldown,
            args.retry_failed,
        )


if __name__ == "__main__":
    sys.exit(main())
