#!/usr/bin/env python3
"""Scale/reliability driver for a fake-provider CareerOps deployment.

This program intentionally uses only the Python standard library and httpx.
It performs network traffic only when explicitly executed.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import re
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

POLL_INTERVAL_SECONDS = 0.5
RUN_TIMEOUT_SECONDS = 300.0
TOKEN_REFRESH_SECONDS = 20.0 * 60.0
REQUEST_TIMEOUT_SECONDS = 30.0
TERMINAL_STATUSES = {"succeeded", "failed"}


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def nearest_rank(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(percentile * len(ordered)))
    return ordered[rank - 1]


def percentile_summary(
    values: list[float], include_max: bool = False
) -> dict[str, float | int | None]:
    result: dict[str, float | int | None] = {
        "count": len(values),
        "p50": nearest_rank(values, 0.50),
        "p95": nearest_rank(values, 0.95),
    }
    if include_max:
        result["max"] = max(values) if values else None
    return result


def response_json(response: httpx.Response | None) -> dict[str, Any]:
    if response is None:
        return {}
    try:
        value = response.json()
    except (json.JSONDecodeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def error_code_from(payload: dict[str, Any], fallback: str | None = None) -> str | None:
    for key in ("error_code", "code"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    detail = payload.get("detail")
    if isinstance(detail, dict):
        for key in ("error_code", "code"):
            value = detail.get(key)
            if isinstance(value, str) and value:
                return value
    return fallback


@dataclass
class UserState:
    index: int
    email: str
    password: str
    token: str | None = None
    login_monotonic: float = 0.0
    login_lock: asyncio.Lock = field(default_factory=asyncio.Lock)


@dataclass
class JobState:
    user: UserState
    job_index: int
    job_id: str
    parse_key: str
    parse_run_id: str | None = None
    parse_status: str | None = None
    alternate_parse_run_id: str | None = None
    analysis_key: str | None = None
    analysis_run_id: str | None = None


class Driver:
    def __init__(
        self,
        args: argparse.Namespace,
        resumes: list[dict[str, Any]],
        jds: list[dict[str, Any]],
    ) -> None:
        self.args = args
        self.resumes = resumes
        self.jds = jds
        self.semaphore = asyncio.Semaphore(args.concurrency)
        self.client = httpx.AsyncClient(
            base_url=args.api.rstrip("/"),
            timeout=httpx.Timeout(REQUEST_TIMEOUT_SECONDS),
            limits=httpx.Limits(
                max_connections=args.concurrency,
                max_keepalive_connections=args.concurrency,
            ),
            headers={"User-Agent": "careerops-fake-provider-scale-test/1.0"},
        )
        self.http_errors: Counter[str] = Counter()
        self.http_errors_by_stage: dict[str, Counter[str]] = {}
        self.network_errors: Counter[str] = Counter()
        self.internal_errors: Counter[str] = Counter()
        self.setup_counts: Counter[str] = Counter()
        self.parse_records: list[dict[str, Any]] = []
        self.analysis_records: list[dict[str, Any]] = []
        self.read_records: list[dict[str, Any]] = []
        self.idempotency_probe_runs: list[dict[str, Any]] = []
        self.idempotency: dict[str, Counter[str]] = {
            "parse_same_key_same_id": Counter(),
            "analysis_same_key_same_body_same_id": Counter(),
            "analysis_same_key_different_body_409": Counter(),
        }

    def count_http_error(self, stage: str, status_code: int) -> None:
        key = str(status_code)
        self.http_errors[key] += 1
        self.http_errors_by_stage.setdefault(stage, Counter())[key] += 1

    async def raw_request(
        self, method: str, path: str, stage: str, **kwargs: Any
    ) -> httpx.Response | None:
        try:
            async with self.semaphore:
                response = await self.client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            self.network_errors[type(exc).__name__] += 1
            self.network_errors[f"stage:{stage}"] += 1
            return None
        if response.status_code >= 400:
            self.count_http_error(stage, response.status_code)
        return response

    async def login(self, user: UserState, force: bool = False) -> bool:
        async with user.login_lock:
            if (
                not force
                and user.token
                and time.monotonic() - user.login_monotonic < TOKEN_REFRESH_SECONDS
            ):
                return True
            response = await self.raw_request(
                "POST",
                "/api/v1/auth/login",
                "auth_login",
                json={"email": user.email, "password": user.password},
            )
            payload = response_json(response)
            token = payload.get("access_token")
            if response is None or response.status_code != 200 or not isinstance(token, str):
                self.setup_counts["login_failed"] += 1
                user.token = None
                return False
            user.token = token
            user.login_monotonic = time.monotonic()
            self.setup_counts["login_succeeded"] += 1
            return True

    async def request(
        self, user: UserState, method: str, path: str, stage: str, **kwargs: Any
    ) -> httpx.Response | None:
        if not await self.login(user):
            return None
        headers = dict(kwargs.pop("headers", {}))
        headers["Authorization"] = f"Bearer {user.token}"
        response = await self.raw_request(method, path, stage, headers=headers, **kwargs)
        if (
            response is not None
            and response.status_code == 401
            and await self.login(user, force=True)
        ):
            headers["Authorization"] = f"Bearer {user.token}"
            response = await self.raw_request(method, path, stage, headers=headers, **kwargs)
        return response

    async def setup_user(self, user: UserState) -> list[JobState]:
        jobs: list[JobState] = []
        try:
            register = await self.raw_request(
                "POST",
                "/api/v1/auth/register",
                "auth_register",
                json={"email": user.email, "password": user.password},
            )
            if register is not None and register.status_code in (201, 409):
                self.setup_counts["register_ready"] += 1
            else:
                self.setup_counts["register_failed"] += 1
            if not await self.login(user, force=True):
                return jobs

            resume = self.resumes[user.index]
            experiences = resume.get("experiences", [])
            if not isinstance(experiences, list):
                experiences = []
            for experience in experiences:
                body = {
                    key: experience.get(key)
                    for key in ("title", "kind", "description", "skills", "outcome")
                }
                response = await self.request(
                    user, "POST", "/api/v1/experiences", "setup_experiences", json=body
                )
                if response is not None and response.status_code == 201:
                    self.setup_counts["experiences_created"] += 1
                else:
                    self.setup_counts["experiences_failed"] += 1

            for job_index in range(self.args.jobs_per_user):
                jd = self.jds[(job_index + user.index) % len(self.jds)]
                location = jd.get("location")
                body = {
                    "company": jd.get("company"),
                    "title": jd.get("title"),
                    "raw_description": jd.get("raw_description"),
                    "source_url": jd.get("source_url"),
                    "location": location if location else None,
                }
                response = await self.request(user, "POST", "/api/v1/jobs", "setup_jobs", json=body)
                payload = response_json(response)
                job_id = payload.get("id")
                if response is not None and response.status_code == 201 and isinstance(job_id, str):
                    self.setup_counts["jobs_created"] += 1
                    jobs.append(
                        JobState(
                            user=user,
                            job_index=job_index,
                            job_id=job_id,
                            parse_key=f"{self.args.safe_tag}-parse-u{user.index:03d}-j{job_index:04d}",
                        )
                    )
                else:
                    self.setup_counts["jobs_failed"] += 1
        except Exception as exc:  # isolate an unexpected per-user defect
            self.internal_errors[f"setup_user:{type(exc).__name__}"] += 1
        return jobs

    async def poll_run(
        self,
        job: JobState,
        kind: str,
        run_id: str,
        submitted_monotonic: float,
    ) -> tuple[str, str | None, str]:
        path = f"/api/v1/jobs/{job.job_id}/{kind}-runs/{run_id}"
        deadline = submitted_monotonic + RUN_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            response = await self.request(job.user, "GET", path, f"{kind}_poll")
            payload = response_json(response)
            if response is not None and response.status_code == 200:
                status = payload.get("status")
                if status in TERMINAL_STATUSES:
                    return str(status), error_code_from(payload), utc_now()
            remaining = deadline - time.monotonic()
            if remaining > 0:
                await asyncio.sleep(min(POLL_INTERVAL_SECONDS, remaining))
        return "timeout", "POLL_TIMEOUT", utc_now()

    async def run_parse(self, job: JobState) -> None:
        submit_ts = utc_now()
        submitted_monotonic = time.monotonic()
        response = await self.request(
            job.user,
            "POST",
            f"/api/v1/jobs/{job.job_id}/parse-runs",
            "parse_submit",
            headers={"Idempotency-Key": job.parse_key},
        )
        payload = response_json(response)
        run_id = payload.get("id")
        if response is None or response.status_code != 202 or not isinstance(run_id, str):
            status = "submit_failed"
            error_code = error_code_from(
                payload,
                "NETWORK_ERROR" if response is None else f"HTTP_{response.status_code}",
            )
            terminal_ts = utc_now()
        else:
            job.parse_run_id = run_id
            status, error_code, terminal_ts = await self.poll_run(
                job, "parse", run_id, submitted_monotonic
            )
        job.parse_status = status
        self.parse_records.append(
            {
                "user_index": job.user.index,
                "job_id": job.job_id,
                "run_id": run_id if isinstance(run_id, str) else None,
                "idempotency_key": job.parse_key,
                "submit_ts": submit_ts,
                "terminal_ts": terminal_ts,
                "status": status,
                "error_code": error_code,
                "latency_seconds": max(0.0, time.monotonic() - submitted_monotonic),
            }
        )

    async def create_alternate_parse(self, job: JobState) -> str | None:
        key = f"{job.parse_key}-alternate"
        submit_ts = utc_now()
        started = time.monotonic()
        response = await self.request(
            job.user,
            "POST",
            f"/api/v1/jobs/{job.job_id}/parse-runs",
            "idempotency_parse_alternate",
            headers={"Idempotency-Key": key},
        )
        payload = response_json(response)
        run_id = payload.get("id")
        if response is None or response.status_code != 202 or not isinstance(run_id, str):
            status = "submit_failed"
            error_code = error_code_from(
                payload, "NETWORK_ERROR" if response is None else f"HTTP_{response.status_code}"
            )
            terminal_ts = utc_now()
            self.idempotency_probe_runs.append(
                {
                    "probe": "alternate_parse_for_analysis_conflict",
                    "user_index": job.user.index,
                    "job_id": job.job_id,
                    "run_id": None,
                    "idempotency_key": key,
                    "submit_ts": submit_ts,
                    "terminal_ts": terminal_ts,
                    "status": status,
                    "error_code": error_code,
                    "latency_seconds": max(0.0, time.monotonic() - started),
                }
            )
            return None
        status, error_code, terminal_ts = await self.poll_run(job, "parse", run_id, started)
        self.idempotency_probe_runs.append(
            {
                "probe": "alternate_parse_for_analysis_conflict",
                "user_index": job.user.index,
                "job_id": job.job_id,
                "run_id": run_id,
                "idempotency_key": key,
                "submit_ts": submit_ts,
                "terminal_ts": terminal_ts,
                "status": status,
                "error_code": error_code,
                "latency_seconds": max(0.0, time.monotonic() - started),
            }
        )
        if status == "succeeded":
            job.alternate_parse_run_id = run_id
            return run_id
        return None

    async def check_parse_idempotency(self, job: JobState) -> None:
        check = self.idempotency["parse_same_key_same_id"]
        response = await self.request(
            job.user,
            "POST",
            f"/api/v1/jobs/{job.job_id}/parse-runs",
            "idempotency_parse_replay",
            headers={"Idempotency-Key": job.parse_key},
        )
        replay_id = response_json(response).get("id")
        if response is not None and response.status_code == 202 and replay_id == job.parse_run_id:
            check["pass"] += 1
        else:
            check["fail"] += 1
        await self.create_alternate_parse(job)

    async def submit_analysis(self, job: JobState) -> dict[str, Any]:
        submit_ts = utc_now()
        submitted_monotonic = time.monotonic()
        job.analysis_key = (
            f"{self.args.safe_tag}-analysis-u{job.user.index:03d}-j{job.job_index:04d}"
        )
        body = {"parse_run_id": job.parse_run_id}
        response = await self.request(
            job.user,
            "POST",
            f"/api/v1/jobs/{job.job_id}/analysis-runs",
            "analysis_submit",
            headers={"Idempotency-Key": job.analysis_key},
            json=body,
        )
        payload = response_json(response)
        run_id = payload.get("id")
        if response is None or response.status_code != 202 or not isinstance(run_id, str):
            status = "submit_failed"
            error_code = error_code_from(
                payload,
                "NETWORK_ERROR" if response is None else f"HTTP_{response.status_code}",
            )
            terminal_ts = utc_now()
        else:
            job.analysis_run_id = run_id
            status, error_code, terminal_ts = await self.poll_run(
                job, "analysis", run_id, submitted_monotonic
            )
        return {
            "user_index": job.user.index,
            "job_id": job.job_id,
            "parse_run_id": job.parse_run_id,
            "run_id": run_id if isinstance(run_id, str) else None,
            "idempotency_key": job.analysis_key,
            "submit_ts": submit_ts,
            "terminal_ts": terminal_ts,
            "status": status,
            "error_code": error_code,
            "latency_seconds": max(0.0, time.monotonic() - submitted_monotonic),
        }

    async def run_analysis_with_checks(self, job: JobState) -> None:
        record = await self.submit_analysis(job)
        self.analysis_records.append(record)
        if job.analysis_run_id is None or job.analysis_key is None:
            self.idempotency["analysis_same_key_same_body_same_id"]["fail"] += 1
            self.idempotency["analysis_same_key_different_body_409"]["fail"] += 1
            return

        path = f"/api/v1/jobs/{job.job_id}/analysis-runs"
        same = await self.request(
            job.user,
            "POST",
            path,
            "idempotency_analysis_replay",
            headers={"Idempotency-Key": job.analysis_key},
            json={"parse_run_id": job.parse_run_id},
        )
        same_payload = response_json(same)
        same_check = self.idempotency["analysis_same_key_same_body_same_id"]
        if (
            same is not None
            and same.status_code == 202
            and same_payload.get("id") == job.analysis_run_id
        ):
            same_check["pass"] += 1
        else:
            same_check["fail"] += 1

        conflict_check = self.idempotency["analysis_same_key_different_body_409"]
        if job.alternate_parse_run_id is None:
            conflict_check["fail"] += 1
            return
        conflict = await self.request(
            job.user,
            "POST",
            path,
            "idempotency_analysis_conflict",
            headers={"Idempotency-Key": job.analysis_key},
            json={"parse_run_id": job.alternate_parse_run_id},
        )
        if conflict is not None and conflict.status_code == 409:
            conflict_check["pass"] += 1
        else:
            conflict_check["fail"] += 1

    async def safe_call(self, label: str, coroutine: Any) -> None:
        try:
            await coroutine
        except Exception as exc:  # one bad lifecycle must not cancel the stage
            self.internal_errors[f"{label}:{type(exc).__name__}"] += 1

    async def timed_read(
        self,
        user: UserState,
        endpoint_name: str,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> httpx.Response | None:
        started = time.perf_counter()
        response = await self.request(user, "GET", path, f"read:{endpoint_name}", params=params)
        latency_ms = (time.perf_counter() - started) * 1000.0
        self.read_records.append(
            {
                "user_index": user.index,
                "endpoint": endpoint_name,
                "latency_ms": latency_ms,
                "status_code": response.status_code if response is not None else None,
                "success": response is not None and 200 <= response.status_code < 300,
            }
        )
        return response

    async def run_reads_for_user(self, user: UserState, user_jobs: list[JobState]) -> None:
        cursor: str | None = None
        for _ in range(20):
            params: dict[str, Any] = {"limit": 20}
            if cursor:
                params["cursor"] = cursor
            response = await self.timed_read(user, "jobs_list", "/api/v1/jobs", params)
            payload = response_json(response)
            next_cursor = payload.get("next_cursor")
            cursor = next_cursor if isinstance(next_cursor, str) and next_cursor else None

        selected = next((job for job in user_jobs if job.parse_run_id), None)
        endpoint_specs: list[tuple[str, str, dict[str, Any] | None]] = [
            ("experiences", "/api/v1/experiences", None),
            ("dashboard_summary", "/api/v1/dashboard/summary", None),
            ("dashboard_focus", "/api/v1/dashboard/focus", None),
        ]
        if selected is not None:
            endpoint_specs.insert(0, ("job_detail", f"/api/v1/jobs/{selected.job_id}", None))
            endpoint_specs.append(
                (
                    "latest_analysis",
                    f"/api/v1/jobs/{selected.job_id}/analysis-runs/latest",
                    {"parse_run_id": selected.parse_run_id},
                )
            )
        for endpoint_name, path, read_params in endpoint_specs:
            for _ in range(20):
                await self.timed_read(user, endpoint_name, path, read_params)

    def stage_metrics(
        self, records: list[dict[str, Any]], wall_seconds: float
    ) -> dict[str, Any]:
        statuses = Counter(str(record.get("status")) for record in records)
        error_codes = Counter(str(record.get("error_code") or "none") for record in records)
        terminal_records = [
            record for record in records if record.get("status") in TERMINAL_STATUSES
        ]
        latencies = [float(record["latency_seconds"]) for record in terminal_records]
        throughput = len(terminal_records) / (wall_seconds / 60.0) if wall_seconds > 0 else 0.0
        return {
            "counts_by_status": dict(sorted(statuses.items())),
            "counts_by_error_code": dict(sorted(error_codes.items())),
            "end_to_end_latency_seconds": percentile_summary(latencies, include_max=True),
            "terminal_runs": len(terminal_records),
            "wall_time_seconds": wall_seconds,
            "throughput_terminal_runs_per_minute": throughput,
        }

    def read_metrics(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        endpoint_names = sorted({str(record["endpoint"]) for record in self.read_records})
        for name in endpoint_names:
            records = [record for record in self.read_records if record["endpoint"] == name]
            successful = [float(record["latency_ms"]) for record in records if record["success"]]
            result[name] = {
                "attempted": len(records),
                "succeeded": len(successful),
                "latency_ms": percentile_summary(successful),
            }
        return result

    async def run(self) -> dict[str, Any]:
        digest = hashlib.sha256(self.args.run_tag.encode("utf-8")).hexdigest()[:16]
        password = f"ScaleTest!Aa1-{digest}"
        users = [
            UserState(
                index=index,
                email=f"scale-{self.args.safe_tag}-u{index:02d}@example.com",
                password=password,
            )
            for index in range(self.args.users)
        ]

        setup_started = time.monotonic()
        setup_results = await asyncio.gather(*(self.setup_user(user) for user in users))
        jobs = [job for group in setup_results for job in group]
        setup_wall = time.monotonic() - setup_started

        parse_started = time.monotonic()
        await asyncio.gather(
            *(self.safe_call("parse", self.run_parse(job)) for job in jobs)
        )
        parse_wall = time.monotonic() - parse_started

        succeeded = [job for job in jobs if job.parse_status == "succeeded" and job.parse_run_id]
        sample: list[JobState] = []
        for user in users:
            candidate = next((job for job in succeeded if job.user is user), None)
            if candidate is not None:
                sample.append(candidate)
            if len(sample) == 50:
                break
        if len(sample) < min(50, len(succeeded)):
            chosen_ids = {id(job) for job in sample}
            sample.extend(job for job in succeeded if id(job) not in chosen_ids)
            sample = sample[:50]

        await asyncio.gather(
            *(
                self.safe_call("parse_idempotency", self.check_parse_idempotency(job))
                for job in sample
            )
        )

        analysis_started = time.monotonic()
        sample_ids = {id(job) for job in sample}
        await asyncio.gather(
            *(
                self.safe_call("analysis_checks", self.run_analysis_with_checks(job))
                for job in sample
            )
        )
        remaining = [job for job in succeeded if id(job) not in sample_ids]

        async def ordinary_analysis(job: JobState) -> None:
            self.analysis_records.append(await self.submit_analysis(job))

        await asyncio.gather(
            *(self.safe_call("analysis", ordinary_analysis(job)) for job in remaining)
        )
        analysis_wall = time.monotonic() - analysis_started

        jobs_by_user = {user.index: [job for job in jobs if job.user is user] for user in users}
        reads_started = time.monotonic()
        await asyncio.gather(
            *(
                self.safe_call(
                    "reads", self.run_reads_for_user(user, jobs_by_user[user.index])
                )
                for user in users
            )
        )
        reads_wall = time.monotonic() - reads_started

        config = {
            "api": self.args.api.rstrip("/"),
            "users": self.args.users,
            "jobs_per_user": self.args.jobs_per_user,
            "concurrency": self.args.concurrency,
            "out": str(self.args.out),
            "run_tag": self.args.run_tag,
            "normalized_run_tag": self.args.safe_tag,
            "poll_interval_seconds": POLL_INTERVAL_SECONDS,
            "run_timeout_seconds": RUN_TIMEOUT_SECONDS,
            "token_refresh_seconds": TOKEN_REFRESH_SECONDS,
            "request_timeout_seconds": REQUEST_TIMEOUT_SECONDS,
            "resumes_file": str(self.args.resumes),
            "jds_file": str(self.args.jds),
        }
        return {
            "generated_at": utc_now(),
            "config": config,
            "setup": {
                "counts": dict(sorted(self.setup_counts.items())),
                "wall_time_seconds": setup_wall,
            },
            "parse": {
                **self.stage_metrics(self.parse_records, parse_wall),
                "runs": self.parse_records,
            },
            "analysis": {
                **self.stage_metrics(self.analysis_records, analysis_wall),
                "runs": self.analysis_records,
            },
            "idempotency_checks": {
                name: {"pass": counts["pass"], "fail": counts["fail"]}
                for name, counts in self.idempotency.items()
            },
            "idempotency_probe_runs": self.idempotency_probe_runs,
            "reads": {
                "wall_time_seconds": reads_wall,
                "metrics_by_endpoint": self.read_metrics(),
                "calls": self.read_records,
            },
            "http_errors_by_status_code": dict(sorted(self.http_errors.items())),
            "http_errors_by_stage_and_status_code": {
                stage: dict(sorted(counts.items()))
                for stage, counts in sorted(self.http_errors_by_stage.items())
            },
            "network_errors": dict(sorted(self.network_errors.items())),
            "internal_errors": dict(sorted(self.internal_errors.items())),
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", required=True, help="CareerOps API base URL")
    parser.add_argument("--users", type=int, default=50)
    parser.add_argument("--jobs-per-user", type=int, default=150)
    parser.add_argument("--concurrency", type=int, default=16)
    parser.add_argument("--out", type=Path, default=Path("results.json"))
    parser.add_argument(
        "--run-tag", required=True, help="Unique label used in test account emails and keys"
    )
    parser.add_argument(
        "--resumes",
        type=Path,
        default=Path(__file__).with_name("resumes.json"),
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--jds", type=Path, default=Path(__file__).with_name("jds.json"), help=argparse.SUPPRESS
    )
    args = parser.parse_args()
    if args.users <= 0:
        parser.error("--users must be positive")
    if args.jobs_per_user <= 0:
        parser.error("--jobs-per-user must be positive")
    if args.concurrency <= 0:
        parser.error("--concurrency must be positive")
    safe_tag = re.sub(r"[^a-z0-9-]+", "-", args.run_tag.lower()).strip("-")
    if not safe_tag:
        parser.error("--run-tag must contain at least one ASCII letter or digit")
    args.safe_tag = safe_tag[:40]
    return args


def load_json_list(path: Path, label: str) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(item, dict) for item in value)
    ):
        raise ValueError(f"{label} must be a non-empty JSON array of objects: {path}")
    return value


async def async_main(args: argparse.Namespace) -> dict[str, Any]:
    resumes = load_json_list(args.resumes, "resumes")
    jds = load_json_list(args.jds, "jds")
    if args.users > len(resumes):
        raise ValueError(f"--users ({args.users}) exceeds available resumes ({len(resumes)})")
    driver = Driver(args, resumes, jds)
    try:
        return await driver.run()
    finally:
        await driver.client.aclose()


def main() -> int:
    args = parse_args()
    try:
        results = asyncio.run(async_main(args))
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"fatal configuration/input error: {exc}")
        return 2

    parse = results["parse"]
    analysis = results["analysis"]
    checks = results["idempotency_checks"]
    passed = sum(item["pass"] for item in checks.values())
    failed = sum(item["fail"] for item in checks.values())
    print(
        f"wrote {args.out}: parse={parse['counts_by_status']}, "
        f"analysis={analysis['counts_by_status']}, idempotency={passed} pass/{failed} fail, "
        f"http_errors={results['http_errors_by_status_code']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
