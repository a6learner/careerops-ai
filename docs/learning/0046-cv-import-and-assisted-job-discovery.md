# 0046 CV Import And Assisted Job Discovery

## What Changed

CareerOps can now upload seven common CV formats, extract text in the worker,
create source-grounded Experience drafts, and turn an explicitly confirmed draft
into an Experience. It can also run a deterministic job search through a worker
adapter, preserve source and freshness metadata, create an editable Job draft,
and create a formal Job only after confirmation.

## Why It Exists

The feature reduces manual setup without weakening the project's central rule:
untrusted automation may propose data, but the user controls what becomes an
authoritative resource. Durable run and draft records make failures reviewable
and confirmations replay-safe.

## Failure Modes It Prevents

- trusting an extension or browser-provided media type;
- decompressing a suspicious office archive without limits;
- blocking an API request on LibreOffice, PDF parsing, or search;
- treating a worker failure as a successful empty import;
- creating formal data before user review;
- creating duplicates when confirmation is retried or concurrent;
- exposing one user's imports, drafts, or search runs to another user;
- inventing a complete job description from a provider summary;
- losing the source URL or time at which a listing was observed;
- calling a real provider during ordinary tests or local acceptance.

## How To Verify It

Run the focused backend and frontend tests while developing. For final
verification, run the complete backend and frontend quality gates, migrate a
fresh PostgreSQL database, and run the isolated Compose browser acceptance. The
acceptance must keep parser, embedding, matcher, and job search behavior
deterministic and must clean up its exact Compose project.

## What You Must Understand

Level 1: Explain why drafts are separate from authoritative resources, how row
locking makes confirmation replay-safe, why source references must survive the
import, why PostgreSQL owns lifecycle state, and why a missing job description
cannot be filled from a summary.

Level 2: Be able to follow multipart upload through the same-origin BFF, API,
PostgreSQL work item, worker extractor or search adapter, draft endpoints, and
the final confirmation transaction. Know which formats use direct parsing and
which use LibreOffice.

## Knowledge Check

1. Why is checking a filename extension insufficient for an uploaded CV?
2. What database and transaction behavior prevents two confirmation requests
   from creating two Experiences?
3. Why does Experience confirmation create the embedding run in the same
   transaction but execute it later in a worker?
4. Why is `observed_at` different from a job's provider-supplied publication
   date?
5. Why is a search summary insufficient input for a formal Job description?
6. What new security and lifecycle decisions would direct Google Docs import
   require?
