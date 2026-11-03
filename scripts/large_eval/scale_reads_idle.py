"""Sequential read-latency re-measure on the idle scale stack (no concurrent writes).

Nearest-rank p50/p95.
"""

import json
import math
import sys
import time
from typing import Any

import httpx

API = "http://127.0.0.1:8020"
METHOD = "sequential, 10 users x 20 calls per endpoint, idle stack, 7500 jobs + 7500 analyses in DB"


def pct(values: list[float], q: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, math.ceil(q * len(ordered)) - 1))]


def main() -> None:
    with open(sys.argv[1], encoding="utf-8") as handle:
        res: dict[str, Any] = json.load(handle)
    cfg: dict[str, Any] = res["config"]
    runs: list[dict[str, Any]] = res["analysis"]["runs"]
    client = httpx.Client(timeout=30)
    lat: dict[str, list[float]] = {}
    users: list[int] = sorted({r["user_index"] for r in runs})[:10]
    by_user: dict[int, dict[str, Any]] = {}
    for r in runs:
        by_user.setdefault(r["user_index"], r)
    for u in users:
        email = f"scale-{cfg['normalized_run_tag']}-u{u:02d}@example.com"
        login = client.post(
            f"{API}/api/v1/auth/login", json={"email": email, "password": sys.argv[2]}
        )
        tok: str = login.json()["access_token"]
        h = {"Authorization": f"Bearer {tok}"}
        run = by_user[u]
        job = run["job_id"]
        parse_id = run.get("parse_run_id")
        eps = {
            "jobs_list": "/api/v1/jobs?limit=20",
            "job_detail": f"/api/v1/jobs/{job}",
            "experiences": "/api/v1/experiences",
            "dashboard_summary": "/api/v1/dashboard/summary",
            "dashboard_focus": "/api/v1/dashboard/focus",
        }
        if parse_id:
            eps["latest_analysis"] = (
                f"/api/v1/jobs/{job}/analysis-runs/latest?parse_run_id={parse_id}"
            )
        for name, path in eps.items():
            for _ in range(20):
                t = time.perf_counter()
                response = client.get(API + path, headers=h)
                dt = (time.perf_counter() - t) * 1000
                if response.status_code == 200:
                    lat.setdefault(name, []).append(dt)
    out = {
        k: {"n": len(v), "p50_ms": round(pct(v, 0.5), 1), "p95_ms": round(pct(v, 0.95), 1)}
        for k, v in lat.items()
    }
    with open(sys.argv[3], "w") as handle:
        json.dump({"method": METHOD, "endpoints": out}, handle, indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
