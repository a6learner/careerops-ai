# 0038 Bounded Worker Recovery Cycle

## What Changed

The three existing PostgreSQL recovery paths now have one operational entry point.
One invocation checks parse runs, analysis runs, and embedding runs once, prints a
JSON summary, and exits nonzero when any step fails.

The command refuses to start unless all three provider selections in its process
are explicitly `fake`. It preserves each recovery service rather than rebuilding
their state transitions in a fourth place.

## Why It Exists

PostgreSQL is authoritative, while a Redis delivery may be lost or a worker may
stop after claiming a run. A repeatable command must rebuild disposable queue
messages from durable state without making recovery logic harder to reason about.

## Failure Modes It Prevents

- Forgetting one of the three independent recovery commands.
- Letting one recovery exception hide the status of later durable queues.
- Returning success after a Redis dispatch failure.
- Accidentally using this offline operational route with a real provider selected
  in the command process.
- Copying domain recovery transitions into an orchestration layer that could drift.
- Leaking connection strings or provider error text in the summary.

## How It Was Verified

Focused unit tests use injected typed steps. They verify fail-before-dispatch
provider checks, continuation after an exception, preservation of partial failure,
machine-readable output, nonzero exit behavior, temporary namespaces, provider
overrides, cleanup sentinels, and Windows worker process-tree shutdown.

An isolated synthetic run used a temporary PostgreSQL database, a labeled temporary
Redis container, and a dedicated fake-only worker. It recovered one stale Parse Run
and one stale Analysis Run at attempt 2, reconciled one missing Embedding Run, and
then verified zero temporary-resource residue. The development database and its
Redis data were never selected.

## What You Must Understand

Level 1: PostgreSQL owns work state; Redis messages are rebuildable hints. Duplicate
delivery is expected, so workers use conditional claims and attempt fencing.

Level 1: an orchestration failure policy differs from a domain retry policy. The
cycle continues across independent queues, but it reports overall failure instead
of masking a broken step.

Level 2: the provider check protects the command process only. A separately running
worker has its own environment and must be verified before dispatched work is
consumed.

Level 2: the cycle is bounded by the existing per-type batch settings and performs
one pass. Scheduling and overlap control remain deployment concerns.

## Knowledge Check

1. Why can Redis delivery be rebuilt without making Redis a source of truth?
2. Why does the cycle continue after one recovery type raises an exception?
3. Why must the process still exit nonzero after the other steps succeed?
4. Why is checking the command's provider settings insufficient to prove the worker is fake-only?
5. What prevents two deliveries of the same run from executing the model twice concurrently?
