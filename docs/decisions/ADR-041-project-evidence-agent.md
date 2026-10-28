# ADR-041: Host-Driven Project Evidence Agent

## Status

Accepted for the initial project/checkpoint API and review UI slice, 2026-10-27,
under the author's instruction to begin design and incremental upgrades while
preserving existing features. Implementation is subject to author review.
The MCP dependency/auth handoff and host integration remain proposed.

## Context

Candidates forget project details when development records are missing. Reading
the repository months later may recover code behavior but not the original
trade-offs, failed attempts, verification conditions, or personal contribution.
The author wants reusable project records inside existing coding-agent workflows
and wants users to use their own model access instead of funding server inference.

## Decision (Proposed)

Add a host-driven extension to CareerOps: a recording Skill, a local stdio MCP
adapter, authenticated project/checkpoint/source APIs, and review/search UI.
The host model proposes structured records; CareerOps validates and stores them.
This new path makes no server model call and collects no provider key. Existing
worker-only model adapters and their opt-in policies are unchanged.

PostgreSQL owns accepted data and lifecycle state. The adapter calls the existing
API/service boundary rather than writing the database directly. Pending local
packets are unaccepted submissions, not an alternative authoritative database.

Records preserve selected source snapshots, hashes, verification provenance,
corrections, and review state. A client-submitted hash or test report does not
prove independent execution or personal authorship. Generated career claims
remain drafts and cite confirmed records; existing Experience/verdict semantics
do not change. First delivery exports material rather than auto-promoting it.

## Initial Slice Contract

- Add `projects` and `project_checkpoints`; all pre-existing resources retain
  their contracts. Snapshots are bounded JSONB in the checkpoint row rather than
  an independently mutable source table. This follows the existing draft-source
  storage pattern and makes one record/source write atomic.
- Each checkpoint has 1–8 supplied sources. A source contains kind, relative
  locator, bounded content and an exact quote. Pydantic checks the packet and
  path, the service hashes normalized content, and a PostgreSQL CHECK function
  rejects absent/empty sources and quotes missing from content.
- A composite FK `(project_id, user_id)` enforces project ownership in DDL.
  Per-user unique idempotency keys protect project/checkpoint creation.
  Same key/different normalized input is 409; retry returns the existing record
  including its current review/withdrawal state.
- States: draft -> confirmed -> withdrawn, or draft -> withdrawn. No resurrection.
  PostgreSQL triggers protect initial state, immutable snapshots, ownership,
  source digest, input identity and review version increments.
- Review requires `If-Match`, row locking and a personal contribution note on
  confirmation. Repeating the identical review is replay-safe; conflicting
  notes or stale competing transitions fail. Withdrawal retains the original
  contribution note as historical context, not current career evidence.
- Reads support bounded, literal substring search and created-at/UUID cursor
  pagination. Search does not infer matching quality; confirmation does not
  certify authorship or test execution.
- New routes are under `/api/v1/projects`: POST/GET collection, GET detail,
  POST/GET `/{id}/checkpoints`, GET checkpoint detail, and PATCH checkpoint
  `/review`. Creation requires `Idempotency-Key`; missing contracts return 428,
  invalid input 422, cross-user/missing IDs 404, conflicts 409.
- Existing bearer auth and same-origin HttpOnly BFF remain unchanged. No new
  credential storage or model key collection is implemented. The frontend gets
  an additional Projects navigation entry and keeps all existing entries.
- No DELETE endpoint yet: withdrawal is not erasure. Data remains until owning
  user/database deletion cascades; no user-facing erasure or automatic retention
  scheduler is claimed. This must be addressed before public remote MCP release.
- Correction initially means withdraw the old record and create a new draft.
  Explicit supersession links and gap linkage are not implemented in this slice.

The next local-client slice is tracked by ADR-042: protected terminal auth,
packet/receipt replay and a repository Skill are implemented and tested.
MCP SDK/protocol/host integration, automatic capture, retention management and
live resume/STAR quality evaluation remain separate incomplete gates.

## Alternatives Considered

- Skill and local Markdown only: useful for a prototype, but lacks account-scoped
  durable cross-project search, review state, and a controlled evidence interface.
- MCP alone: exposes operations but does not define when and how a host records
  useful engineering details; combine it with a Skill.
- Central autonomous agent with hosted inference or user-key storage: deferred
  because it adds cost and credential scope before proving record quality.
- Universal hooks and full transcript capture: deferred; host-specific behavior,
  noisy records, privacy, and incomplete coverage need separate validation.
- Learning planner and Notion sync first: deferred until usable project records
  and recovery are demonstrated. They remain possible later consumers.
- Multi-agent orchestration: unnecessary for the first recording/retrieval flow.

## Consequences

Users retain their host model account and its usage costs. CareerOps still has
storage/operation costs; background processing without a connected host is not
provided. Source snapshots require explicit limits and deletion semantics.
Explicit capture is portable but may miss activity; automatic capture needs
separate host adapters. Installing a protocol package is not evidence of a
working agent: real host execution, provenance and failure handling must pass.

During verification, the existing Next.js 16.4.0 dependency was confirmed by
`npm audit` and the upstream 2026-10-14 security advisory to be vulnerable. The
existing Next.js and matching ESLint configuration are patched to 16.4.3 with
the lockfile updated. This is a focused patch in the existing release line,
not a new UI framework. Production dependency audit then reports zero findings;
the full development dependency audit still reports four findings and is not
claimed clean. No automatic force-upgrade was performed.

## Verification Or Evidence

Baseline: `381ef0e`, existing local acceptance and ADR-040. Initial slice results
are recorded in `docs/metrics/2026-10-27-project-records-test-record.md`. Gates K1–K8 in
[the project plan](../product/project-evidence-agent-plan.md) specify contract,
authorization/concurrency, recovery, host integration, trace-grounded outputs,
independent evaluations and local browser/MCP acceptance.

## Revisit If

- Users require background execution without a coding host.
- Real usage demonstrates that explicit checkpoint capture misses essential work.
- Remote distribution requires production-grade credentials and public MCP.
- Search quality requires more than bounded keyword/metadata retrieval.
