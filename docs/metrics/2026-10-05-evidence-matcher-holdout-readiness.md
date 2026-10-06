# Evidence Matcher Holdout Readiness Record

## Scope

This record covers offline runner verification and the one-time rubric-v2 label
migration. It is not a matcher holdout result. No Groq request was made.

## Frozen Candidate

- prompt: `evidence-matcher-prompt-v4`, SHA-256
  `ef33e71c303438a876c53ef026c47c38fe9c9331ecb3cc5b00d3b3d680b24b5a`
- response schema: `evidence-matcher-schema-v1`, SHA-256
  `bf2c87f276da75998a6d2421f661316a50e9b608304642a4223e6824c4307902`
- provider/model: Groq / `openai/gpt-oss-20b`
- request policy: eight slots, one attempt per case, at least 11 seconds apart,
  800 maximum output tokens, low reasoning, temperature 0
- coverage evaluator: `evidence-matcher-coverage-v2`
- safety policy: `evidence-matcher-holdout-safety-v1`

## Label Migration

The legacy eight-case holdout was opened once for label review. It was migrated
without changing prompt, retrieval, schema, or evaluator behavior. The v2 labels
contain two cases per oracle verdict, one retrieval miss, one multilingual case,
and one prompt-injection case.

- migrated holdout SHA-256:
  `e0575f5cae44dd58a59b1fd21da0e8f357c79a7795a68392449725377514417a`
- run manifest: `evals/evidence_matcher_v1/holdout_v2_run_manifest.json`
- manifest status: `approved_frozen`
- reviewer: project author
- reviewed at: `2026-10-05T17:29:53.1449873-07:00`
- manifest SHA-256:
  `099dd7d4eb034284ab2938a83abf111529a5a4ecae65796bcf95b2fe2a5186da`

The pre-migration approved manifest and its old holdout hash remain unchanged as
historical evidence. They cannot authorize the migrated file.

## Verification

Toy fixtures verified complete execution, recovery without repeated completed
calls, ambiguous-attempt fencing, request budget, single attempts, provider and
output failure preservation, manifest/model fencing, separate invocation
authorization, explicit prompt v4, and immutable final output.

Verification on 2026-10-05:

- 88 focused matcher and Analysis Run tests passed;
- strict mypy passed for 118 source files;
- Ruff passed;
- both import-boundary contracts passed across 118 analyzed files and 349
  dependencies.

## Subsequent Result

After author approval, the independent runner completed the one-time holdout and
passed every pre-frozen safety gate. The result is recorded separately in
`2026-10-05-groq-evidence-matcher-holdout.md` and its immutable JSON report.
This readiness record remains evidence of the state before provider access; it
is not rewritten into a result report.
