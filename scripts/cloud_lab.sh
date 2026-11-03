#!/usr/bin/env bash
set -euo pipefail
umask 077
cd "$(dirname "${BASH_SOURCE[0]}")/.."
root="$PWD"
state="$root/.cloud-lab"
action="${1:-help}"
compose=(docker compose --project-name careerops-cloud-lab --env-file "$state/environment" -f "$root/docker-compose.cloud-lab.yml")
export COMPOSE_PARALLEL_LIMIT=1

case "$action" in
  init)
    test ! -e "$state/environment" || { echo 'Already initialized; keep the existing credentials.' >&2; exit 1; }
    docker info >/dev/null
    test -z "$(docker container ls -aq --filter label=com.docker.compose.project=careerops-cloud-lab)" || {
      echo 'Existing lab containers found; do not replace their credentials.' >&2; exit 1;
    }
    for kind in network volume; do
      test -z "$(docker "$kind" ls -q --filter label=com.docker.compose.project=careerops-cloud-lab)" || {
        echo 'Existing lab resources found; do not replace their credentials.' >&2; exit 1;
      }
    done
    mkdir -p "$state"
    python3 - "$state/environment" <<'PY'
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path

release = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
with Path(sys.argv[1]).open("x", encoding="utf-8") as output:
    output.write(f"LAB_RELEASE={release}\n")
    output.write(f"LAB_DATABASE_PASSWORD={secrets.token_hex(24)}\n")
    output.write(f"LAB_JWT_SECRET={secrets.token_hex(32)}\n")
PY
    echo 'Initialized private lab credentials. Do not upload or print .cloud-lab/environment.'
    exit 0
    ;;
  help)
    echo 'Usage: sudo bash scripts/cloud_lab.sh init|check|build|up|status|logs|recover|backup|restore-check|down|destroy'
    exit 0
    ;;
esac

test -f "$state/environment" || { echo 'Run init first.' >&2; exit 1; }
"${compose[@]}" config --quiet

case "$action" in
  check)
    "${compose[@]}" config --format json | python3 -c '
import json, sys
def require(condition, message):
    if not condition:
        raise SystemExit(message)
c = json.load(sys.stdin)
s = c["services"]
require(c["name"] == "careerops-cloud-lab", "Unexpected Compose project.")
for name in ("api", "worker", "migrate"):
    e = s[name]["environment"]
    require(e["CAREEROPS_ENV"] == "production", "Expected production settings.")
    for key in ("CAREEROPS_LLM_PROVIDER", "CAREEROPS_EMBEDDING_PROVIDER", "CAREEROPS_EVIDENCE_MATCHER_PROVIDER"):
        require(e[key] == "fake", "Lab providers must be fake.")
    require(not e["CAREEROPS_LLM_API_KEY"] and not e["CAREEROPS_GEMINI_API_KEY"], "Remove model keys from lab settings.")
for name, service in s.items():
    for port in service.get("ports", []):
        require(name in ("api", "frontend") and port["host_ip"] == "127.0.0.1", "Refusing public or database port bindings.")
require(s["frontend"]["environment"]["CAREEROPS_FRONTEND_ORIGIN"] == "http://127.0.0.1:13010", "Unexpected browser origin.")
print("PASS: private ports, production configuration, fake providers, no model keys.")
'
    ;;
  build)
    for service in api worker frontend; do
      "${compose[@]}" build "$service"
    done
    ;;
  up)
    bash "$root/scripts/cloud_lab.sh" check
    "${compose[@]}" up -d --wait --wait-timeout 180 postgres redis
    "${compose[@]}" run --rm --no-deps migrate
    "${compose[@]}" up -d --no-deps --wait --wait-timeout 180 api
    "${compose[@]}" up -d --no-deps --wait --wait-timeout 180 worker frontend
    "${compose[@]}" exec -T api alembic current
    "${compose[@]}" images --format json > "$state/images.json"
    bash "$root/scripts/cloud_lab.sh" status
    ;;
  status)
    "${compose[@]}" ps -a
    curl --fail --silent --show-error http://127.0.0.1:18010/readyz
    printf '\n'
    curl --fail --silent --show-error http://127.0.0.1:13010/readyz
    printf '\n'
    ;;
  logs)
    "${compose[@]}" logs --no-color --tail 200 api worker frontend
    ;;
  recover)
    "${compose[@]}" exec -T worker python -m careerops.workers.recovery_cycle
    ;;
  backup)
    backup="$state/backup-$(date -u +%Y%m%dT%H%M%SZ).dump"
    test ! -e "$backup" && test ! -e "$backup.partial"
    "${compose[@]}" exec -T postgres pg_dump -U careerops -d careerops -Fc > "$backup.partial"
    test -s "$backup.partial"
    mv "$backup.partial" "$backup"
    echo "Saved $backup; copy it off the VM before deletion."
    ;;
  restore-check)
    backup="${2:?Supply the exact dump path from backup}"
    test -f "$backup"
    # A fixed scratch database is created exclusively; never overwrite an existing database.
    "${compose[@]}" exec -T postgres createdb -U careerops careerops_restore_check
    trap '"${compose[@]}" exec -T postgres dropdb -U careerops careerops_restore_check' EXIT
    "${compose[@]}" exec -T postgres pg_restore -U careerops -d careerops_restore_check --exit-on-error < "$backup"
    "${compose[@]}" exec -T postgres psql -U careerops -d careerops_restore_check -v ON_ERROR_STOP=1 -c 'SELECT version_num FROM alembic_version;'
    echo 'Archive restored to a separate scratch database; compare selected synthetic records before calling data recovery complete.'
    ;;
  down)
    "${compose[@]}" down
    echo 'Containers removed; the lab database volume and cloud billing remain.'
    ;;
  destroy)
    test "${2:-}" = 'DELETE-SYNTHETIC-LAB-DATA' || {
      echo 'To delete only this lab volume: destroy DELETE-SYNTHETIC-LAB-DATA' >&2; exit 1;
    }
    "${compose[@]}" down --volumes
    echo 'Lab containers and volume removed. Delete the cloud instance separately; check residual billable resources.'
    ;;
  *) echo "Unknown action: $action" >&2; exit 1 ;;
esac
