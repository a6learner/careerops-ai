# Local Hybrid Retrieval Test Record

Date: 2026-10-03

Branch: `codex/p1-3b-embedding-holdout`

Starting commit: `6fcbf5559eaf90d226e1acd1cfcbbd5321c1f452`
Verified implementation commit: `d1cd1f0e16f3356a5485849505471792c5115061`

## Scope

This record verifies the local Analysis Run hybrid-retrieval integration. It does
not rerun retrieval evaluation, open the sealed holdout, or call a real provider.

## Results

- Default offline suite: 208 passed, 20 skipped.
- PostgreSQL/Redis integration coverage: 18 cases passed; 2 explicitly gated cases
  skipped. One stale test-call signature failed in the full run and passed after the
  fixture was corrected and rerun directly.
- Real Dramatiq worker E2E with forced fake providers: passed.
- `mypy --strict`: 104 source files passed.
- Ruff, import-boundary contracts, dependency check, Alembic drift check, and
  whitespace validation passed.

The two integration skips were the explicitly gated real Groq request and worker
end-to-end test requiring a separately running Dramatiq process. Targeted hybrid,
authorization, vector-provenance, and Analysis Run attempt-fencing tests passed.

## Limitations

This is engineering verification, not a new quality benchmark. It makes no new
recall, latency, cost, or production-scale claim. No Gemini request was made.

During the later worker-E2E review, the first invocation inherited a local `.env`
Groq setting and made one successful parse request before the worker was stopped.
The E2E now refuses non-fake LLM or embedding providers and was rerun offline.
