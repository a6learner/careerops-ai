# 0047 Project Checkpoints And Reviewed Evidence

## What Changed

An additive Projects workspace stores user-owned project goals and development
checkpoints with supplied source excerpts. Records start as drafts and can be
confirmed with an explicit contribution note or withdrawn. Search and immutable
snapshots support later recall; MCP and model-generated career briefs are future
slices, not implemented behavior.

## Why It Exists

Code alone rarely preserves the reason for a trade-off or a failed approach.
Capturing those details during development helps reconstruct an interview story
without inventing achievements. It also keeps AI-proposed summaries distinct
from the author's contribution and understanding.

## Failure Modes It Prevents

- Retrying after a lost response creates duplicates: unique keys and request hashes
  converge to the same row, including its current withdrawal state.
- A client points at another user's project: a composite foreign key and API
  owner filters enforce ownership independently.
- An invented quote is persisted: schema validation and a DB CHECK require the
  quote to occur in the supplied source content.
- An old browser overwrites review state: If-Match, row locks and DB transition
  protection prevent competing reviews and resurrection.
- A summary changes after confirmation: immutable snapshot triggers reject it.
- A locally supplied test report becomes a claim of server-certified execution:
  the UI explicitly labels client provenance; no execution certification exists.

## How It Was Verified

See `docs/metrics/2026-10-27-project-records-test-record.md`. Tests exercise
concurrent creation/review, authorization, replay after withdrawal, literal search,
cursor traversal, invalid input and direct database bypass attempts. Browser
acceptance includes the original core loop plus the new manual record workflow.

## What The Author Must Understand

Level 1: distinguish an idempotency key from a content hash, source grounding
from truth, user confirmation from skill certification, and withdrawal from
deletion. Explain why payload/sources are atomic bounded JSONB, why the FK includes
the owner, and why repeated identical review can return the newer version safely.

Level 2: follow the BFF -> API -> service -> repository path, normalized Pydantic
input, PostgreSQL conflict handling, CHECK/trigger migration and review row lock.

## Knowledge Check

1. What happens if a save succeeded but its response was lost, and the user retries
   after that record has been withdrawn?
2. Why does a hash of a test-output excerpt not prove that the test ran?
3. What does the composite project/owner FK protect that a normal project FK does not?
4. Which requests may replay an old If-Match successfully, and why is that not a lost update?
5. How should you correct a confirmed record without rewriting its source history?
6. Which part runs the model in the proposed Skill/MCP architecture, and which part
   still needs implementation?
