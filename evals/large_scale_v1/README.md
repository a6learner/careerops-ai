# large_scale_v1 (development set)

Built 2026-11-01 for the large-scale real-provider evaluation (see ADR-047 when written, and
`docs/metrics/` for results). **Development split only. Never use it as a holdout.** It was
built and scored at the same time, so any later tuning on it is development work. A future
holdout must be freshly collected.

## Contents

| File | What |
|---|---|
| `jds.json` | 302 real, public job descriptions. Each record has its `source_url`, `fetched_at`, collector and `sha256`. Emails and phone numbers are replaced with `[redacted]`. |
| `resumes.json` | 50 fully fictional resumes (214 experiences), stratified by `stratum`. Adversarial and sparse resumes list their deliberate non-evidence in `traps`. |
| `pairs.json` | 150 resume x JD pairs. Each resume has one designed high-, medium- and low-fit JD, and each JD is used once. 152 more JDs are parser-only. |
| `cv_files/` | Each resume rendered as `.md` (blank lines between entries) and `.docx` (one paragraph per line), for the CV-import test. |
| `manifest.json` | Counts, merge rejections, and SHA-256 of every file. |

## Provenance

- JDs:
  - about 112 from the author's Notion job list: the links were exported by Codex through its Notion connector, then the public posting text was fetched;
  - 90 from public Greenhouse board APIs;
  - 100 from public Lever/Ashby APIs and earlier study URLs.
- Merge rules: exact-URL dedupe, 5-word-shingle near-duplicate removal (Jaccard ≥ 0.85), and at most 4 JDs per company (`scripts/large_eval/build_dataset.py`).
- `role_family` and `seniority` were assigned by the collectors from title rules. They are approximate, and they are used only for pairing and reporting.
- Resumes were written by a Claude subagent (r01-r25) and Codex (r26-r50). A first Codex set was rejected for templated text. No real person's data is included.

## Labels

Parser and matcher labels are **model-labeled** (Codex and Antigravity labeled independently, then a
Claude adjudication pass). They are not author-labeled. Agreement statistics are reported with the results.
