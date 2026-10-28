# Optional MCP Adapter Verification

Date: 2026-10-27. Baseline HEAD `381ef0e`; extension work remains uncommitted.

## Scope And Authorization

Automatic approval initially rejected installation of the proposed major
dependency pending author confirmation. The author then explicitly approved
`mcp==2.3.0`. Installation into the project virtual environment succeeded;
`pip check` reported no broken requirements. Selected installed versions are in
[the dependency snapshot](2026-10-27-project-agent-mcp-dependencies.json), which
is not a complete lockfile. The optional `agent` extra is installed in backend
CI for type checks and tests; API/worker deployment dependency sets are unchanged.

The stdio adapter uses the official SDK v2 and the existing `ProjectAgent`
gateway. It exposes project registration/list/context, checkpoint save/replay,
confirmed evidence search/current-state retrieval and pending summaries. It has
no login, credential-reading, review, withdrawal, file execution or model tools.
Terminal login and the web review flow retain their existing contracts.

## Verification

The raw protocol/client report is
[JUnit](2026-10-27-project-agent-mcp-tests.xml). It combines new MCP tests with
previous client tests; totals overlap earlier reports and must not be added as
unique coverage.

Final focused run: **50 passed**, no failures, skips or warnings. This comprises
14 MCP cases and the existing 36 client cases.

```powershell
.\.venv\Scripts\python -m pytest tests/test_project_agent_mcp.py tests/test_project_agent.py --basetemp=.pytest_cache/project-agent-mcp-final-20261027 --junitxml=docs/metrics/2026-10-27-project-agent-mcp-tests.xml --tb=short
```

The protocol tests use the official SDK client, including a real stdio child
process. They verify discovery and schemas, safe unauthenticated/invalid-input
errors and a usable session after tool failure. SDK in-memory sessions exercise
the gateway with a deterministic HTTP transport: packet persistence before POST,
same-key replay after a lost response, conflict rejection, confirmed-only reads,
pagination parameters and current withdrawn state. Synthetic private markers in
invalid arguments, raw API diagnostics and unexpected exceptions are checked for
absence from returned errors; the stdio test also checks captured stderr.

An independent reviewer found that pending/rejected save receipts initially had
the SDK success flag. The adapter now flags them as tool errors while retaining
their structured packet/state/recovery information. Final tests directly cover
save and replay for rejected, login-required and upstream-unavailable receipts,
as well as the lost-response recovery case. No gateway business semantics changed.

Strict native and Linux-target mypy, Ruff, import-boundary checks, dependency
consistency and diff whitespace checks form the static gates. Configuration
examples were parsed as TOML/JSON and checked against official host documentation
and locally installed CLI help. The repository Skill validator passed.

Final static results: native and Linux-target strict mypy passed for 145 source
files; Ruff passed; both import-boundary contracts were kept; `pip check` and
`git diff --check` passed. No frontend changes were made in this SDK slice, so its
earlier browser/build evidence was not rerun or relabeled as new protocol evidence.

## Limits And Next Acceptance

This is SDK/protocol and deterministic client evidence. There was no actual
Codex/Claude model run, no global host installation, no new migration applied to
the author's database, no backend provider call, and no commit/push. Earlier
PostgreSQL/CLI and browser results are saved in their own stage reports; they are
not a claim that this new stdio process completed a PostgreSQL-backed host flow.

The chosen coding host must still record a selected project slice, let the user
review it, and recall it in a fresh session with traceable career drafts. That
acceptance uses the host's existing model/account and needs an explicit bounded
execution scope. Automatic capture, completeness, career-output quality,
performance and production reliability are not measured here.

Subsequent stage: after the author explicitly authorized model use, the two-session
Codex synthetic path was exercised and recorded separately in
[the host demo report](2026-10-27-project-agent-host-demo-record.md). This does not
change which checks the SDK-only stage itself performed.
