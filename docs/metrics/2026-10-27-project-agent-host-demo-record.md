# Codex Host Demonstration

Local date: 2026-10-27. Baseline HEAD `381ef0e`; changes remain uncommitted.
The author explicitly approved the previously proposed two model-session demo.

## Observed Outcome

Two independent real Codex model sessions completed successfully against the
local MCP server and PostgreSQL-backed API. Between them, the executing assistant
used the real web UI to confirm the synthetic draft with an explicit synthetic
contribution disclaimer. This is a demonstrated local host flow, not the author's
product acceptance, personal resume evidence or a production-quality evaluation.

| Stage | Direct observation |
|---|---|
| Environment | Current working tree rebuilt; isolated Compose project `careerops-agent-demo-20261027` |
| Readiness | API reports database/Redis ready; frontend reports API ready |
| Isolation | PostgreSQL 15421, Redis 16321, API 18021, frontend 13021; all published only on 127.0.0.1 |
| Backend models | Parser, embedding and matcher forced to fake; no provider keys supplied |
| Host | `codex-cli 0.164.0-alpha.11.1`; existing ChatGPT login, configured `gpt-5.6-sol` with medium reasoning |
| Record session | `list_projects`, `register_project`, `save_checkpoint`; accepted draft v1 |
| Browser review | Sources expanded; synthetic contribution disclaimer entered; record becomes confirmed v2 |
| Fresh recall session | `search_project_evidence`, `get_project_context`, `get_evidence`; Chinese review, English candidate bullet and STAR draft returned |
| Output limits | Synthetic-only context, unverified authorship, no executed fixture test, no measured metrics and no JD tailoring are explicitly retained |

The recall prompt contains the Skill and project ID, not the checkpoint source
text or first session output. Its tool allowlist contains only reads. Distinct
session IDs and completed tool inputs/results are retained in
[the machine-readable artifact](2026-10-27-project-agent-host-demo.json).

Project ID: `b942251c-c118-4732-aea8-627c16b49da4`.
Checkpoint ID: `24b391b8-56af-4d8a-b516-8a488059beb9`.
Packet ID: `5fd90bbc-b55a-5026-bd8a-eb3732d075e4`.

## Artifacts

- [Record-session original output](2026-10-27-project-agent-host-record-output.md).
- [Fresh-session original output](2026-10-27-project-agent-host-recall-output.md).
- [Draft and source screenshot](2026-10-27-project-agent-demo-draft.png).
- [Confirmed record screenshot](2026-10-27-project-agent-demo-confirmed.png).
- [Learning and repeatable demonstration guide](../learning/0050-project-agent-demo.md).

The JSON artifact retains only synthetic tool data and run summaries, excluding
credentials and unrelated host events. Complete local process logs remain under
the ignored `.pytest_cache/project-agent-host-demo` directory. Protected session
and packets stay there encrypted; they are not copied into metrics.

## Startup Failure And Execution Bound

The initial host process failed configuration validation before any thread or
model session started: this Codex build rejects `model_providers.openai.*`
overrides because `openai` is a reserved built-in provider ID. The attempted
request/stream retry overrides were removed; no alternate provider was created.
That failed process and a later prepare-only invocation remain in the artifact.
The prepare-only invocation starts no Codex process.

There were two actual model sessions, both successful. Each runner invocation
has a timeout and no automatic rerun. Codex's own network retry behavior was not
overridden. A PowerShell shell-snapshot warning occurred but did not prevent the
MCP flow; shell tools were disabled. No third model session was started.

## Verification And Remaining Work

The runner passed Ruff and compilation; the Compose script passed PowerShell
parsing, resolved configuration validation, loopback/provider checks and actual
startup. The new record, UI state and read-only recall have direct artifacts.
The earlier SDK/client 50-test result remains in its original report and was not
relabeled as this host acceptance. Frozen matcher/embedding holdouts were not run.

This demo did not test actual code-change extraction, automatic trigger timing,
long-running usage, withdrawal inside a further model session, adversarial
career-output quality, a real JD, Claude Code, other OSes or production service.
No author database was migrated; only the independent demo database was migrated.
No global Codex configuration or installed Skill was modified. No commit/push.

The environment is intentionally retained for inspection at
`http://127.0.0.1:13021/projects`. Use
`scripts/local_project_agent_demo.ps1 -Action Stop` to stop only this project;
its database volume is retained. This is not a claim that the environment stays
available after Docker shutdown or reboot.

Configuration references: [Codex non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode),
[MCP configuration](https://learn.chatgpt.com/docs/extend/mcp), and
[configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference).
