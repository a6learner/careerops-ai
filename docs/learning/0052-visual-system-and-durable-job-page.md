# 0052 Visual System, Job Detail Page And Durable Run Lookup

## What Changed

- A Notion-inspired visual system (ADR-044):
  - tokens are defined once and registered with Tailwind v4 `@theme`;
  - Inter and JetBrains Mono are self-hosted by `next/font`;
  - shared UI primitives replace hand-styled controls.
- New page structure:
  - Jobs and Action Items are status boards;
  - Experiences is a gallery;
  - Projects is a page list with a document-style record view;
  - each job has its own page at `/jobs/[id]`.
- Three owner-scoped read endpoints (ADR-045):
  - `GET /jobs/{id}/parse-runs/latest`;
  - `GET /jobs/{id}/analysis-runs/latest?parse_run_id=…`;
  - `GET /dashboard/focus`.
- A UX feedback layer:
  - toasts after saves;
  - skeleton loading states;
  - route-level `loading`, `error` and `not-found` pages;
  - readable run failure messages that still show the raw code;
  - per-card pending state instead of one shared flag;
  - a confirmation step before withdrawing a project record.

## Why It Exists

The run data was always durable in PostgreSQL, but the browser only knew a run
by the ID it had just submitted. A reload lost the requirements and evidence, so
the user either re-ran parsing and analysis, which spends model calls in
real-provider mode, or lost the context. The job page now asks the API for the
latest run.

The board and gallery layouts move the crowded per-job panels onto a dedicated
page, so evidence quotes have room and every job has a URL.

## Failure Modes It Prevents

- **Lost results on reload.** A reload no longer drops parse or analysis results, and the user isn't pushed into re-submitting model work.
- **Mismatched evidence.** Evidence from an older parse is never shown next to newer requirements, because the analysis lookup is scoped by `parse_run_id`.
- **Treating a foreign job as empty.** The client treats only `PARSE_RUN_NOT_FOUND` / `ANALYSIS_RUN_NOT_FOUND` as "no run yet". A `JOB_NOT_FOUND` for another user's job is still shown as an error.
- **Stale cached counts.** The focus lists are uncached, so a deadline edit cannot leave a stale Redis entry behind.
- **One update blocking the board.** Each card owns its mutation, so one pending update no longer disables every row.
- **Accidental withdrawal.** Withdrawing a project record now needs a second click.
- **Ignored font sizes.** Base element styles sat outside a Tailwind layer, so every `text-sm` on buttons and inputs was ignored. Moving them into `@layer base` fixes that.

## How It Was Verified

See `../metrics/2026-10-29-ui-polish-test-record.md`. In short:

- backend unit tests;
- a PostgreSQL integration test covering ordering, both 404 codes, cross-user access, the required query parameter, and focus filtering;
- frontend component tests, including "restores the latest run after a reload without submitting";
- the isolated full-stack browser acceptance, which now reloads the job page and checks that requirements and evidence are still there.

## What You Must Understand

Level 1:

- **Why "latest" is scoped by `parse_run_id`.** An Analysis Run is bound to the requirements of one Parse Run. If the user re-parses, the old analysis does not describe the new requirements, so pairing them would show evidence for requirements that are not on screen.
- **Why the focus read is not cached.** `/summary` is cached in Redis and invalidated on job and action-item writes. Caching the focus lists would require invalidating on more write paths (deadline, title, company edits) for a few small indexed reads.
- **How ownership is enforced.** The service loads the job with `user_id` first, so another user's job is `404 JOB_NOT_FOUND`. The query itself also filters by `user_id`, which keeps a second, query-level guard.
- **What "today" means.** The focus endpoint uses the UTC date and returns it, so the browser counts days from the same date. User time zones are not stored.

Level 2:

- **TanStack Query `initialData`.** The polling query is seeded from the latest-run response, so there is no extra fetch when the run is already finished.
- **The `replacingLatest` flag.** It stops the old restored run from flashing back while a new run is being submitted.
- **Tailwind v4 tokens.** `@theme inline` turns CSS variables into utilities such as `bg-brand` and `text-muted`.
- **`@layer base`.** Unlayered CSS beats every Tailwind utility, regardless of specificity.

## Knowledge Check

1. Why does `/analysis-runs/latest` require `parse_run_id` instead of returning
   the newest analysis for the job?
2. The client calls `apiRequestOrNull(..., "PARSE_RUN_NOT_FOUND")`. What would
   go wrong if it turned every 404 into `null`?
3. Which writes would need to invalidate Redis if the focus lists were added to
   the cached `/dashboard/summary`?
4. Why does the job page not need a migration for the latest Parse Run lookup?
   Which index serves it?
5. A user in UTC-8 opens the dashboard at 17:00 local time on the day of a
   deadline. What does "days left" show, and why?
6. Why did `text-sm` on a `<button>` render at 16px before this change?
