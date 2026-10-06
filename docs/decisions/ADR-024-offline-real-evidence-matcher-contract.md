# ADR-024: Offline Real Evidence Matcher Contract

## Status

Accepted

## Context

Analysis Runs already retrieve at most five provenance-valid candidates per
requirement, but the worker still uses a deterministic fake matcher. A later real
matcher must receive only the evidence needed for its decision, reject malformed
output, and remain unable to bypass the existing ownership, candidate, version, and
quote checks.

This stage must not call a real provider, change frozen retrieval, add persistence,
or change the public API.

## Decision

Introduce a provider-neutral typed matcher input with versioned requirements,
deduplicated candidate Experiences, exact source fields, and per-requirement ranked
candidate IDs. Do not include user IDs, embeddings, retrieval scores, content
hashes, or non-candidate Experiences.

Define a strict JSON response schema with `extra="forbid"`. Positive verdicts are
`matched` or `partial` and must carry one candidate Experience ID and version, a
source reference, an exact verbatim quote, and confidence in `[0, 1]`. Gap verdicts
are `missing` or `insufficient_evidence` and cannot carry evidence. Confidence is
confidence in the verdict, not a match percentage, and does not bypass validation.

The model does not supply character offsets. The service derives a span by finding
the exact quote inside the referenced source field. This avoids trusting model
character counting and preserves the current database and API, which store the
quote but not the derived span.

Invalid JSON, invalid schema, and invalid requirement coverage are distinct output
failure categories. A response must contain every supplied requirement exactly
once and no other requirement. These producer failures fail the whole Analysis
Run. A structurally valid positive claim that cites another user, a non-candidate,
a stale version, an unknown source, or an unsupported quote is instead downgraded
to `insufficient_evidence` before persistence.

Provider failures have stable categories for disabled, misconfigured, timeout,
rate-limited, unavailable, and other request failures. Analysis execution maps
these and the output categories to existing `analysis_runs.error_code` values. No
new database state is required.

The fake matcher now consumes the same typed input and remains the default offline
implementation. No real adapter, provider factory, live configuration, HTTP
transport, evaluation dataset, or worker provider selection is added in this
stage.

## Alternatives Considered

- Send complete Experience records: rejected because ownership and persistence
  metadata are unnecessary provider exposure.
- Let the model return offsets: rejected because token models count Unicode and
  whitespace unreliably; the server can derive offsets from an exact quote.
- Repair malformed JSON or fill omitted requirements with gaps: rejected because
  this would turn producer failure into a business conclusion.
- Fall back to the fake matcher after provider failure: rejected because it would
  store a different algorithm under the real pipeline identity and hide an outage.
- Persist source references and spans now: deferred because it requires a migration
  and public contract decision not needed for safe matching.

## Consequences

The real matcher boundary can be tested offline before provider selection. Prompt
injection-like source text remains data, response shape is deterministic, and
unsupported positive claims still cannot pass the existing validation service.
Exact quoting is stricter than the earlier whitespace-normalized check, so a model
must copy a substring from one named source field.

The current database still enforces positive-row shape and one verdict per
requirement. Ownership, candidate membership, version, source, and quote truth are
application validations performed before the atomic result transaction. Stronger
database-only ownership enforcement would require a separate schema decision.

## Verification Or Evidence

Focused offline tests cover typed minimal input, candidate deduplication, strict
positive/gap schemas, invalid JSON, extra and inconsistent fields, omitted,
duplicate, and foreign requirements, exact source quotes, cross-user and stale
claims, and durable error-code mapping. No provider request or retrieval evaluation
is part of this evidence.

## Revisit If

- P1-5b evaluation shows Experience kind or retrieval rank is insufficient context.
- Product requirements need persisted source fields or spans.
- A provider cannot support the strict structured-output schema.
