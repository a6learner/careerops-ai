# Evidence Matcher Rubric V2 Author Review Packet

The project author approved and froze the development labels, acceptance gates,
and prompt-v2 contract on 2026-10-04 America/Los_Angeles. The JSON source is
authoritative for candidate IDs, evidence references, quotes, and rationales.
The first prompt-v2 development run did not pass the gates. This packet remains
the historical development-label review; the later prompt-v4 policy exception
does not rewrite it. Review the migrated holdout separately in
`HOLDOUT_V2_REVIEW_PACKET.md`.

## Development Labels

| Case | Oracle | Candidate-conditioned | Gap reason / review focus |
|---|---|---|---|
| matcher-dev-001 | matched | matched | One Experience proves Python, FastAPI, PostgreSQL, and transactions |
| matcher-dev-002 | partial | partial | Retry deduplication is proven, regional availability is not |
| matcher-dev-003 | missing | missing | `required_technology_absent`: no Ruby or Rails mention |
| matcher-dev-004 | insufficient_evidence | insufficient_evidence | `future_plan_only`: Rust is an unimplemented rewrite idea |
| matcher-dev-005 | matched | matched | English evidence proves the complete Chinese requirement |
| matcher-dev-006 | partial | partial | Either streaming or warehouse evidence proves one separable half; both are acceptable |
| matcher-dev-007 | missing | missing | `required_technology_absent`: no PyTorch serving mention |
| matcher-dev-008 | insufficient_evidence | insufficient_evidence | `explicit_non_implementation`: discussed, not implemented |
| matcher-dev-009 | matched | partial | Full library proves all; Top-5 proves keyboard navigation only |
| matcher-dev-010 | partial | partial | Offline sync is proven, encrypted server storage is not |
| matcher-dev-011 | missing | missing | `required_technology_absent`: no Angular evidence |
| matcher-dev-012 | insufficient_evidence | insufficient_evidence | `metric_not_proven`: the atomic 20% causal result is unverified, so related work is not partial |

## Proposed Acceptance Gates

- schema pass `1.0`; provider failures `0`; output failures `0`;
- citation validity `1.0`; unsupported-positive rate `0.0`;
- matcher-only acceptable evidence accuracy `1.0`;
- matcher-only verdict accuracy at least `10/12`;
- matcher-only macro-F1 at least `0.75`;
- atomic verdict accuracy at least `7/9` and composite at least `2/3`;
- non-zero recall for every verdict class;
- end-to-end scores, canonical quote agreement, and confidence are diagnostics.

## Approval Boundary

Approval freezes the v2 development labels, hashes, rubric, active prompt-v2 contract,
and development acceptance gates. It does not authorize Groq calls, matcher
holdout access, retrieval changes, or production worker integration.
