# ADR-042: Protected Local Agent Client And MCP Boundary

## Status

Local HTTP client, encrypted state and repository-packaged Skill implemented
under the author's continuation instruction, pending author review.
Automatic approval initially rejected SDK installation on 2026-10-27 pending
concrete package authorization. The author subsequently explicitly approved
`mcp==2.3.0`; it is installed in the project environment and declared in the
optional `agent` extra. The eight-tool stdio adapter and SDK protocol tests are
implemented and passed locally. Subsequent explicitly authorized Codex synthetic
record/review/recall sessions also passed; author acceptance and broader host
quality remain pending.

## Context

The author wants coding assistants to record project evidence using the user's
existing model. The API must remain the authorization and persistence boundary.
An expired session, a lost HTTP response or a different logged-in account must
not create duplicate records or silently change ownership.

## Decision

- Add `careerops.agent` as a local client using the existing httpx dependency.
  No database access or server model call is added.
- Restrict this first version to explicit loopback HTTP origins. Disable
  environment proxy discovery and HTTP redirects on all credential-bearing
  requests. Remote deployment/authentication is a separate stage.
- Human terminal login uses the existing `/auth/login` and `/auth/me` contracts.
  Password input requires an interactive terminal; the client prints no token.
  No model key or browser cookie is requested. Existing session expiry stays
  unchanged: on 401, re-login and replay the original packet.
- Store credentials, selected pending packets and receipts with Windows
  current-user DPAPI, using stdlib ctypes rather than a new encryption package.
  There is no production plaintext fallback. The default directory is
  `%LOCALAPPDATA%/CareerOps/agent`, configurable by the operator. Tests use
  isolated workspace directories. Mac/Linux protected storage is not implemented.
- DPAPI protects data at rest; it does not isolate an agent capable of executing
  arbitrary code as the same Windows user. The host remains a trusted execution
  environment. Credential secrecy here means no credential tool argument/output
  and no plaintext on disk, not protection against a hostile same-user process.
- A selected upload creates a complete encrypted local packet before contacting
  the API. Its deterministic packet UUID binds user/key; its content hash,
  project, owner and origin are immutable. File publication is atomic and does
  not overwrite a same-key packet. Local pending data is not accepted evidence.
- Each explicit submit/replay makes one write attempt. Auth identity is checked
  before writes. Retry uses the exact original key and payload; no background
  loop or automatic new key. Read current server state for career use.
- Validate returned project and content digest before accepting a receipt.
  Network/unknown-receipt failure and 401 retain pending data; a concrete API
  rejection is reported separately. Failure to save a local receipt reports
  pending even if the server may have committed. Raw response bodies and
  transport exception strings are not forwarded as user-facing errors.
- The local CLI remains available as a Skill fallback alongside MCP.
  It reads only explicitly selected checkpoint JSON, not arbitrary repository
  trees or transcripts. Default evidence search is `confirmed` only.
- `approved_for_upload=true` is a caller's scope declaration, not proof of human
  approval. Actual scope still comes from the user, host permissions and Skill.

## Approved MCP Contract

Use optional `mcp==2.3.0`, the official Python SDK version checked in this stage,
in a client-only extra. Keep it out of API/worker deployment dependencies.
Installation added mcp-types, httpx2/httpcore2, JSON Schema, cryptography and SDK
support packages; Windows also receives pywin32. Existing FastAPI/httpx/Pydantic
versions were retained and `pip check` passed. This record is not a lockfile.

Use SDK-provided stdio transport/schema discovery; do not hand-write the protocol
to bypass the dependency gate. The server exposes these eight operations,
with the already typed `ProjectAgent` gateway as implementation boundary:

| Operation | Contract |
|---|---|
| list_projects | bounded query/cursor -> project page |
| register_project | ProjectInput + stable UUID key -> project |
| get_project_context | project UUID -> project + confirmed page |
| save_checkpoint | project UUID + CheckpointInput + stable UUID key + upload declaration -> receipt |
| search_project_evidence | project UUID + bounded query/cursor -> confirmed page |
| get_evidence | project/checkpoint UUID -> current record/state/sources |
| list_pending_checkpoints | local bounded limit -> account-filtered pending/rejected summaries |
| replay_checkpoint | local packet UUID -> one same-payload attempt and receipt |

No login, credential-reading, arbitrary file-read, execution, confirmation or
withdrawal tool is exposed. Credentials are opened internally; the operator
configures only API origin/state directory. Stdout is reserved for MCP framing;
diagnostics go to stderr and must remain redacted. No host config is edited by
this stage. Subsequent ephemeral Codex synthetic connection tests passed; Claude
Code and general real-project extraction remain unverified.

## Alternatives Considered

- Plaintext bearer tokens or tokens in Skill/MCP config: rejected.
- Storing the user's provider keys: unnecessary; the existing coding host runs the model.
- DPAPI via pywin32/keyring: not necessary for the Windows-only first client.
- Refresh-token/OAuth redesign: deferred; reuse the accepted existing auth contract.
- Retrying every failed save with a new key: rejected because a lost response may
  mean the first transaction committed.
- Installing another SDK or hand-writing MCP after rejection: rejected; explicit
  approval is required for the proposed SDK before protocol implementation.

## Consequences

The local client works with the current API and does not fund model usage.
Protected state is currently Windows-only, requires a filesystem supporting
atomic hard-link publication, and may require a host sandbox permission grant.
Saved packets/receipts remain until locally removed by the operator; no automatic
retention scheduler or account-erasure guarantee is added. Public remote MCP,
package publishing and global Skill installation are separate work.

## Verification Or Evidence

See `docs/metrics/2026-10-27-project-agent-client-test-record.md` and learning
note 0048. Independent agents reviewed the previous API and the new client,
authored client tests and tried the Skill on a synthetic case.
SDK stdio discovery/calls and deterministic tool/recovery results are in
`docs/metrics/2026-10-27-project-agent-mcp-test-record.md`. The later approved
two-session live Codex demonstration is recorded separately in
`docs/metrics/2026-10-27-project-agent-host-demo-record.md`. No global host
installation or author acceptance is claimed.

## Revisit If

- A supported host requires a protocol or SDK version change.
- Remote use or Mac/Linux support becomes necessary.
- Real use shows that protected packets need retention controls or richer search.
