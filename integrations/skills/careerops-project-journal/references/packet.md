# Checkpoint packet v1

Use the existing project UUID. New project registration requires a separate
stable UUID key and the user's intended name/goal. UUIDs identify saved resources,
not local filesystem paths. The packet is an explicit upload of its contents.

Required fields: `title` (1–200 characters), `objective` (1–2000), `changes`
(1–4000), `host` (1–100) and `sources` (1–8 items).

Optional fields: `schema_version` is `"1"`; `base_revision` is a commit/ref label
up to 100 characters or null; `decisions`, `failures`, `verification` allow up to
4000 characters each; `remaining` and `contribution` up to 2000 each.
The whole UTF-8 JSON file must fit 128 KiB. Omit unavailable facts rather than
fabricating them. Unknown fields are rejected.

Each source includes:

- `kind`: `repository_excerpt`, `test_output`, or `user_note`. These describe
  client-supplied provenance, not server execution certification.
- `locator`: a relative source label up to 300 characters, no absolute path,
  URL, parent traversal, credential directory or `.env` source.
- `content`: selected excerpt, 1–8000 characters.
- `quote`: exact substring of that excerpt, 1–2000 characters.

Synthetic shape example (replace it with actual selected evidence):

```json
{
  "schema_version": "1",
  "title": "Make record retries safe",
  "objective": "Avoid duplicate records after a lost response",
  "changes": "Persist one idempotency key for the save operation",
  "decisions": "Keep the same payload on retry",
  "failures": "",
  "verification": "Not yet verified; this is an illustrative draft",
  "remaining": "Exercise a lost-response retry",
  "contribution": "Await user confirmation of personal responsibility",
  "host": "coding-assistant",
  "base_revision": null,
  "sources": [
    {
      "kind": "user_note",
      "locator": "notes/retry-design.md",
      "content": "Retry the same packet using the same idempotency key.",
      "quote": "same idempotency key"
    }
  ]
}
```

A new save returns a draft and content digest. Replaying an existing save returns
that record's current review state, which may already be confirmed or withdrawn.
Confirmation lives in the CareerOps Projects page and requires an explicit
personal contribution. Local packet IDs and receipts support recovery; they do
not replace server state.
