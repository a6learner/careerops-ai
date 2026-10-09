# ADR-035: Bounded Worker Recovery Cycle

## Status

Accepted

## Context

Parse, analysis, and embedding work already have independent PostgreSQL recovery
commands. Operators must currently remember and observe three commands, and an
exception in a hand-written command sequence can prevent later recovery types from
being checked.

The project needs one scheduler-friendly invocation, but it does not yet need a
persistent scheduler, another service, or a new retry state machine. A recovery
invocation can enqueue work that an existing worker consumes, so offline operation
also requires an explicit provider safety boundary.

## Decision

Add one thin recovery-cycle command that invokes the existing parse, analysis, and
embedding recovery functions exactly once and in that order. Each existing
function retains its own transaction, stale threshold, batch limit, dispatch
behavior, and attempt-fencing semantics.

Before running any step, the command requires the parser, embedding, and evidence
matcher provider settings in its own process to all be `fake`. It does not claim to
configure another process: an already-running worker must be checked separately.

Each step is isolated at the orchestration boundary. An unexpected exception is
reported by type without raw exception text, and the remaining recovery types are
still attempted. Any exception or reported dispatch failure produces a nonzero
process exit. The command emits one machine-readable JSON summary.

## Alternatives Considered

- Add a persistent scheduler or Compose service: deferred because one externally
  scheduled command is enough to prove the operational boundary without new
  infrastructure.
- Merge the three recovery services: rejected because their domain state machines,
  transactions, and result shapes are intentionally independent.
- Stop after the first exception: rejected because one unhealthy queue should not
  hide the recovery status of the other durable queues.
- Permit real-provider configuration: rejected for this offline operational slice;
  real provider execution still requires its separate authorization gates.

## Consequences

There is one bounded command suitable for a cron-like caller, while the individual
commands remain useful for diagnosis. Partial failure is visible and does not block
the remaining checks. The command can produce duplicate Redis deliveries, but the
existing conditional claims make those deliveries safe.

This is not automatic scheduling, a retry policy, or proof that another worker
process is fake-configured. It also does not change database, API, or authorization
semantics.

## Verification Or Evidence

Focused tests prove that unsafe provider settings prevent every step from running,
an exception in one step does not suppress later steps, partial failure is
preserved, and the CLI returns machine-readable output with a nonzero status.

Existing lifecycle tests continue to own the parse, analysis, and embedding
requeue, dispatch, duplicate-delivery, and attempt-fencing behavior; the new
orchestrator does not duplicate those state machines.

The isolated synthetic drill `20261006t173000z_6c8dae2f` recovered one stale Parse
Run, one stale Analysis Run, and one missing Embedding Run through a dedicated
fake-only worker. Exact sentinel and label checks removed its temporary PostgreSQL
database and Redis container. The saved local evidence is in
`docs/metrics/2026-10-06-worker-recovery-cycle-drill.md`.

## Revisit If

- Production deployment needs periodic scheduling, leader election, or overlap
  prevention.
- Recovery volume exceeds the existing per-type batch limits.
- Real-provider operations need a separately authorized recovery entry point.
