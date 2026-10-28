# Local Project Agent Client And Independent Verification

Date: 2026-10-27. Baseline HEAD `381ef0e`; all extension work remains uncommitted.
This records the next slice after the existing project/checkpoint API and UI.

## Implemented And Not Implemented

Implemented: typed local HTTP client/gateway, human terminal login, Windows
DPAPI-protected credentials/packets/receipts, atomic packet publication before
POST, same-key explicit replay, account/origin binding, default confirmed-only
evidence reads, CLI commands and repository-packaged Skill.

Not implemented: stdio MCP server, SDK protocol discovery/calls, global Skill
installation, real Codex/Claude Code host connection, automatic capture or
background model execution. The SDK installation was rejected by automatic
approval and was not retried through an alternate mechanism. `mcp==2.3.0` is a
specific proposed optional dependency awaiting author approval; pyproject and
API/worker dependency sets are unchanged in this slice.

## Verification

| Check | Observed result |
|---|---|
| Ruff across source/tests/migrations | passed |
| Strict mypy | passed for 144 source files |
| Import boundaries | 2 contracts kept |
| Packaged Skill quick validator | passed with PYTHONUTF8=1 |
| Independent client unit tests | 36 passed, including native Windows DPAPI |
| Combined focused API/client/precondition/record tests | 67 passed in 4.33 seconds |
| Independent real CLI/socket test | 1 passed in 15.43 seconds |
| Final native-platform/client + CLI revalidation | 37 passed in 21.73 seconds |
| Final CLI pagination extension | 1 passed in 25.10 seconds |
| Fresh migration and drift check | passed through 202610270001; no upgrade drift |

The unit tests are included in the combined 67 and final 37; these counts must
not be added as if they were distinct coverage. CLI/socket is a separate additional test.
Raw combined report: [JUnit](2026-10-27-project-agent-client-tests.xml).
The final native-platform check also has a
[client/CLI JUnit report](2026-10-27-project-agent-cli-tests.xml).
After adding explicit CLI cursor/limit options, the independent socket test
also verifies two-page traversal across two projects (no duplicates), and
confirmed search without a query; its
[pagination JUnit](2026-10-27-project-agent-cli-pagination.xml) records the final run.
The CLI run result was reported by the independently delegated test agent; its
reproducible source is `tests/integration/test_project_agent_cli_postgres.py`.
Times are local test execution observations, not user time-saving measurements.

Both native Windows and `mypy --platform linux` strict checks pass. This verifies
the Windows-only import boundary does not break Linux type checking; it is not
a claim of implemented protected storage on Linux.

The main combined invocation used a new labeled standalone pgvector container
on 127.0.0.1:25430, explicit fake parser/embedding/matcher settings, and:

```powershell
.\.venv\Scripts\python -m pytest `
  tests/test_project_agent.py tests/test_project_records.py `
  tests/test_api_preconditions.py `
  tests/integration/test_project_records_postgres.py `
  tests/integration/test_project_agent_postgres.py `
  --basetemp=.pytest_cache/agent-k3-20261027-final `
  --junitxml=docs/metrics/2026-10-27-project-agent-client-tests.xml --tb=short
```

This is a historical command; use new output/temp paths rather than overwriting
the saved report. All accounts and source inputs were synthetic. No real user
credential or model key was used; no provider call or frozen holdout was run.

## What Was Actually Exercised

Fault-injection tests independently authored in `tests/test_project_agent.py`
verify packet persistence before POST, a committed write with a lost response,
cross-instance same-key replay, no duplicate server record, changed input under
the same key, expired-session recovery after protected credential replacement,
account/origin mismatch, disabled redirects/proxies, default confirmed search,
sanitized HTTP errors and invalid receipts, and encrypted local state.

Regression tests trigger real `mkdir`/`mkstemp` permission failures during receipt
storage: the server still receives exactly one POST, the packet remains, and the
result is `pending/RECEIPT_NOT_SAVED`. Wrong packet filename/derived UUID or receipt
identity is rejected before any extra write request. These tests lock down an
issue found during independent client review, rather than merely mocking an
already-safe error type.

The real API integration uses PostgreSQL, ASGI transport, synthetic login and
native DPAPI. A fresh client opens protected state, submits a draft, confirms
through the normal review API and retrieves confirmed source evidence. A replay
returns the original record and its newer confirmed state.

The independent CLI/socket test starts its own uvicorn process on a free local
port and uses separate `python -m careerops.agent` processes. It checks register
replay, project listing, selected JSON submit, draft exclusion from search,
normal API confirmation, search/get exact quotes, same-ID replay, pending list,
JSON/exit codes and absence of synthetic password/token in stdout or stderr.
It terminates only its owned API process and deletes the synthetic user.

## Independent Review And Fixes

The author authorized parallel verification agents while keeping this chat as
the progress coordinator. Shared-workspace file scopes were separated.

- API reviewer found that direct SQL withdrawal could also change the historical
  contribution note. The still-uncommitted migration trigger now preserves that
  value; direct SQL and HTTP regression tests pass against a fresh database.
- The same review reproduced unhandled `int()` failure for an excessively long
  If-Match header. The shared parser now maps that failure to the existing
  precondition error; valid input behavior remains unchanged. HTTP returns 428.
- Client reviewer found state-directory/temp-file errors outside error conversion.
  Those errors now map to safe pending handling; independent tests reproduce the
  original failure mechanism. Packet/receipt association checks were also added.

No existing broad tests or frozen evaluations were repeated unnecessarily.
The previous full backend and frontend/browser evidence remains in
`2026-10-27-project-records-test-record.md`; this slice adds focused evidence.

## Skill Forward Test

An independent agent used the actual Skill with
`tests/fixtures/project_agent_forward_case.json`, without live tools/credentials.
Its [unmodified output](2026-10-27-project-agent-skill-forward-output.md) preserves
the synthetic-data warning, personal contribution boundaries, citations and
missing-evidence statements. It excludes draft metrics and withdrawn architecture
from current positive claims, and flags duplicate bullets when only one distinct
achievement is supported. The Skill was clarified for missing-JD and offline-state
limitations after this observation.

This is one synthetic behavioral exercise, not a statistical quality evaluation
or a live Skill-to-MCP integration test. No success-rate or coverage claim follows.

## Environment Failures And Remaining Gate

- pip dry-run metadata access initially failed on sandbox Temp permissions;
  an approved read-only dry-run succeeded.
- Actual SDK installation was rejected by automatic approval because explicit
  author confirmation of the new major dependency was missing. No dependency
  install, alternate SDK or hand-written MCP workaround was performed.
- Sandboxed Windows hard-link publication was denied; approved unsandboxed
  client tests passed without weakening atomic publication or plaintext policy.
- Skill validation initially used Windows GBK; invocation-local PYTHONUTF8=1
  resolved decoding without changing the Skill's content semantics.

The remaining gate is explicit approval to install the optional official
`mcp==2.3.0`, then protocol implementation and real host verification. DPAPI is
Windows-only and does not defend against arbitrary same-user code execution.
Current packets/receipts have no automatic purge, no production retention claim
or performance/model-cost measurement is made, and no developer database was
migrated. Temporary database cleanup passed after checking the exact
`careerops.run=agent-20261027` label and removing only that container and its
temporary anonymous volume. No matching container remained. Synthetic test data
was discarded; code and reports remain.
