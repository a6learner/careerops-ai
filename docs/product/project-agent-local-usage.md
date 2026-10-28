# Local Project Agent Client (Windows)

Status: local CLI and repository Skill implemented; the author approved the
official optional `mcp==2.3.0` SDK, now installed. SDK stdio and deterministic tool
tests passed. Two later real Codex sessions completed a synthetic local demo;
broader coding-host/real-project acceptance remains separate. Existing project features remain
available. No model API key is required by this client.

## Prerequisites

Use the normal CareerOps API with migrations through `202610270001`. For this
uncommitted initial release, a fresh isolated environment receives the amended
withdrawal trigger. If a database already applied the earlier uncommitted version
of that migration, do not downgrade it to update a function; arrange a separate
forward-only migration before using it. No development DB has been migrated by
the implementation sessions.

Use Python from the CareerOps development environment, e.g.
`.\.venv\Scripts\python` from this repository. Protected storage requires Windows;
there is no production plaintext fallback or support claim for other OSes.

## Sign In Yourself

In your own interactive PowerShell terminal:

```powershell
$env:CAREEROPS_AGENT_API_URL='http://127.0.0.1:8000'
.\.venv\Scripts\python -m careerops.agent login
```

Enter the existing CareerOps email/password at the prompts. Password input is
hidden; no access token is printed. Piped/non-interactive login is refused.
The short-lived session is DPAPI-protected in `%LOCALAPPDATA%/CareerOps/agent`.
Do not paste a password/token in chat, packet files, Skill or MCP config.

For an operator-chosen private state directory, set `CAREEROPS_AGENT_STATE_DIR`.
It must be outside version-controlled/uploaded material. The tool never reads
the backend `.env`, browser cookie store or provider credentials. The API origin
must be explicit loopback HTTP; public URLs, proxies and redirects are unsupported.

## Record And Recall

```powershell
.\.venv\Scripts\python -m careerops.agent projects
.\.venv\Scripts\python -m careerops.agent register --name 'My project' --goal 'Explain my backend work' --key <stable-uuid>
.\.venv\Scripts\python -m careerops.agent submit --project <project-uuid> --key <stable-save-uuid> --packet <selected-checkpoint.json>
.\.venv\Scripts\python -m careerops.agent pending
.\.venv\Scripts\python -m careerops.agent replay <packet-uuid>
.\.venv\Scripts\python -m careerops.agent search --project <project-uuid> --query 'retry'
.\.venv\Scripts\python -m careerops.agent get --project <project-uuid> --record <checkpoint-uuid>
```

Angle-bracket values are placeholders: replace them before running. Generate one
UUID per logical operation, e.g. `[guid]::NewGuid()`, and keep it for retries.
The selected file must contain only the bounded JSON packet described by the
Skill's `references/packet.md`. No repository is automatically read/uploaded.

`projects` and `search` accept `--limit` (1–100) and `--cursor` using the returned
`next_cursor`. `search` without `--query` traverses all confirmed records in that
project. Context returns the first confirmed page and does not imply full history.

CLI commands emit structured results; exit 0 is accepted, exit 2 needs attention.
`pending` does not mean the server failed: the response or local receipt may be
missing. Replay that packet after checking the API or signing in again. Do not
change its data or create a replacement key as recovery. Rejected requests need
correction/review rather than an unbounded retry loop.

Open Projects in the existing web UI to review personal contribution and confirm
the record. The client does not auto-confirm. Search/context default to confirmed
records; `get` reports current state, including withdrawal. Local receipt files
are not a source of current positive career claims.

DPAPI does not isolate a malicious process running as you. Packet publication
requires the configured local filesystem's atomic hard-link support. If a coding
host sandbox blocks local state writes, grant only the scoped client operation
through that host's normal permission workflow; do not fall back to plaintext or
skip packet persistence. Saved packets/receipts currently have no automatic purge.

## Skill And MCP Connection

The portable artifact is `integrations/skills/careerops-project-journal/SKILL.md`.
It may be explicitly supplied to a skills-compatible coding host, or installed
in that host's supported skill location after reviewing its instructions.
No global skill directory or host configuration is modified by this work.

The CLI works from the host's authorized shell tools. For MCP, install the
optional client extra in this same project environment:

```powershell
.\.venv\Scripts\python -m pip install -e '.[agent]'
```

The stdio entry point is `<absolute-project-python> -m
careerops.agent.mcp_server`. It is launched by the coding host, so it does not
open a browser or display a login prompt. Sign in first from your terminal using
the same API origin and state directory. Keep the API running separately.

Review the placeholder examples in `integrations/mcp/codex.example.toml` and
`integrations/mcp/claude-code.example.json`. Replace the Python/state paths and
add the entry through the host's supported configuration flow. These files are
examples; the implementation session does not install them globally. State
directory changes require a separate login there. Model/provider configuration
stays with the coding host.

After connection, discover the eight operations listed in ADR-042. A safe first
call is `list_projects` with empty arguments. If there is no local session, sign in
from your terminal, then retry; never send credentials through a tool call.
Supply the repository Skill explicitly if it has not been installed in the host.

## Human Acceptance In The Chosen Host

Use a synthetic project or selected non-sensitive project excerpts:

1. Discover tools and list the signed-in user's projects.
2. Register one intended project with a stable UUID key, or select its existing ID.
3. Ask the host to record one completed slice with exact source quotes and the
   authorized upload declaration. Confirm the returned draft in the web UI after
   checking personal contribution.
4. In a fresh host session, ask it to recall the project using confirmed records
   and current record state. Check the cited sources and contribution boundaries.
5. Ask for a resume/STAR draft. Verify each positive statement against those
   records; leave unsupported metrics and uncertain ownership out.

SDK protocol tests do not replace these host/model and human acceptance checks.
The executed synthetic Codex path and its startup failure are recorded in
`../metrics/2026-10-27-project-agent-host-demo-record.md`; the Chinese walkthrough
is `../learning/0050-project-agent-demo.md`. It used ephemeral per-run configuration,
not a global installation.
Automatic hooks, background capture and guaranteed completeness are not
implemented. Ordinary skill invocation or a host's own supported workflow must
trigger recording; a missed trigger can leave a missing checkpoint.
