# Metrics And Evidence

This directory stores measured evidence for claims made in the README, demo, resume bullets, interview notes, or project summaries.

## Rule

If a number was not measured and saved, do not use it as a claim.

Say `not measured` instead of inventing latency improvements, accuracy, recall, throughput, cost savings, reliability, coverage, cache hit rate, or task success rate.

## Metrics To Collect

Useful metrics for this project include:

- main read endpoint P50 and P95 latency
- before/after query plans for indexed endpoints
- async task success, retry, timeout, and permanent failure rates
- cache hit rate
- duplicate analysis requests blocked by idempotency controls
- unsupported positive claims blocked by validation and database constraints
- endpoint coverage by tests
- average analysis latency and estimated token cost

## Evidence Format

Prefer small, durable files:

- benchmark command and environment
- raw output or summarized table
- date measured
- git commit or branch
- dataset or fixture used
- interpretation and limitations

Do not overwrite old results when comparing performance. Add a new dated artifact so the improvement can be traced.
