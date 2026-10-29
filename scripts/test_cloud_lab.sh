#!/usr/bin/env bash
# Shell-level failure tests use fake Docker/curl; no daemon, credentials or network.
set -euo pipefail
source_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
scratch="$(mktemp -d)"
trap 'rm -rf -- "$scratch"' EXIT
mkdir -p "$scratch/scripts" "$scratch/bin"
cp "$source_root/scripts/cloud_lab.sh" "$scratch/scripts/"
touch "$scratch/docker-compose.cloud-lab.yml"
export LAB_TEST_CALLS="$scratch/calls"
export LAB_TEST_CONFIG="$scratch/config.json"
export PATH="$scratch/bin:$PATH"
cat > "$scratch/bin/docker" <<'SH'
#!/usr/bin/env bash
set -eu
printf '%s\n' "$*" >> "$LAB_TEST_CALLS"
case "$*" in
  *'config --format json') cat "$LAB_TEST_CONFIG" ;;
  *'run --rm --no-deps migrate') test "${LAB_TEST_FAIL_MIGRATE:-0}" = 0 ;;
  *'createdb -U careerops careerops_restore_check') test "${LAB_TEST_DB_EXISTS:-0}" = 0 ;;
  *'pg_restore '*) test "${LAB_TEST_FAIL_RESTORE:-0}" = 0 ;;
esac
SH
printf '#!/usr/bin/env bash\nexit 0\n' > "$scratch/bin/curl"
chmod +x "$scratch/bin/docker" "$scratch/bin/curl"
python3 - "$LAB_TEST_CONFIG" <<'PY'
import json
import sys
env = {
    "CAREEROPS_ENV": "production",
    "CAREEROPS_LLM_PROVIDER": "fake",
    "CAREEROPS_EMBEDDING_PROVIDER": "fake",
    "CAREEROPS_EVIDENCE_MATCHER_PROVIDER": "fake",
    "CAREEROPS_LLM_API_KEY": "",
    "CAREEROPS_GEMINI_API_KEY": "",
}
services = {name: {"environment": env} for name in ("api", "worker", "migrate")}
services["frontend"] = {"environment": {"CAREEROPS_FRONTEND_ORIGIN": "http://127.0.0.1:13010"}, "ports": [{"host_ip": "127.0.0.1"}]}
with open(sys.argv[1], "w") as output:
    json.dump({"name": "careerops-cloud-lab", "services": services}, output)
PY
lab=(bash "$scratch/scripts/cloud_lab.sh")
"${lab[@]}" init
python3 - "$scratch/.cloud-lab/environment" <<'PY'
from pathlib import Path
import stat
import sys
p = Path(sys.argv[1])
assert stat.S_IMODE(p.stat().st_mode) == 0o600
assert len(p.read_text().splitlines()) == 3
PY
before="$(sha256sum "$scratch/.cloud-lab/environment")"
if "${lab[@]}" init; then echo 'FAIL: init overwrote state'; exit 1; fi
test "$before" = "$(sha256sum "$scratch/.cloud-lab/environment")"
"${lab[@]}" check
cp "$LAB_TEST_CONFIG" "$scratch/valid.json"
python3 - "$LAB_TEST_CONFIG" <<'PY'
import json
import sys
from pathlib import Path
p = Path(sys.argv[1])
c = json.loads(p.read_text())
c["services"]["frontend"]["ports"][0]["host_ip"] = "0.0.0.0"
p.write_text(json.dumps(c))
PY
if "${lab[@]}" check; then echo 'FAIL: public binding accepted'; exit 1; fi
cp "$scratch/valid.json" "$LAB_TEST_CONFIG"
: > "$LAB_TEST_CALLS"
if LAB_TEST_FAIL_MIGRATE=1 "${lab[@]}" up; then echo 'FAIL: failed migration accepted'; exit 1; fi
if grep -q 'up -d --no-deps' "$LAB_TEST_CALLS"; then echo 'FAIL: app started after migration failure'; exit 1; fi
: > "$LAB_TEST_CALLS"
"${lab[@]}" up
python3 - "$LAB_TEST_CALLS" <<'PY'
from pathlib import Path
import sys
calls = Path(sys.argv[1]).read_text()
assert calls.index("run --rm --no-deps migrate") < calls.index("up -d --no-deps --wait --wait-timeout 180 api")
assert calls.index("180 api") < calls.index("180 worker frontend")
PY
: > "$LAB_TEST_CALLS"
if "${lab[@]}" destroy; then echo 'FAIL: unconfirmed deletion accepted'; exit 1; fi
if grep -q ' down' "$LAB_TEST_CALLS"; then echo 'FAIL: deletion ran without guard'; exit 1; fi
touch "$scratch/backup.dump"
: > "$LAB_TEST_CALLS"
if LAB_TEST_DB_EXISTS=1 "${lab[@]}" restore-check "$scratch/backup.dump"; then echo 'FAIL: existing scratch DB accepted'; exit 1; fi
if grep -q dropdb "$LAB_TEST_CALLS"; then echo 'FAIL: existing DB deleted'; exit 1; fi
: > "$LAB_TEST_CALLS"
if LAB_TEST_FAIL_RESTORE=1 "${lab[@]}" restore-check "$scratch/backup.dump"; then echo 'FAIL: failed restore accepted'; exit 1; fi
grep -q 'dropdb -U careerops careerops_restore_check' "$LAB_TEST_CALLS"
echo 'PASS: credential preservation, private-port rejection, release ordering, migration failure, guarded deletion and scratch restore cleanup.'
