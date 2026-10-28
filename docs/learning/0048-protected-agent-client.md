# 0048 Protected Agent Client And Recovery

## What Changed

A local CLI can log in, register/list projects, submit selected checkpoint JSON,
find pending packets, replay them and read confirmed evidence through the API.
The repository packages a recording/recall/career-brief Skill. This note describes
the client slice before SDK approval; subsequent MCP work is in learning note
0049. Real coding-host acceptance remains separate.

## Why It Exists

A coding host supplies reasoning/model access; CareerOps supplies reliable tools
and persistence. This avoids a second model bill while keeping evidence review
and ownership inside the existing backend.

## Failure Modes It Prevents

- Plaintext local credentials or tokens appearing as tool arguments.
- Following a redirect or environment proxy with credential-bearing requests.
- Losing a logical operation after a response timeout and creating duplicates.
- Sending an old packet under a different account or configured API.
- Treating a model draft or cached receipt as currently confirmed evidence.
- Reporting success when the packet or receipt was not safely saved locally.

## How It Was Verified

See `docs/metrics/2026-10-27-project-agent-client-test-record.md`.
Independent tests use a fake backend for deterministic fault injection and native
Windows DPAPI for a protected-state roundtrip. A new isolated database exercises
the API/client path with synthetic credentials. Skill forward-testing uses a
synthetic fixture and does not prove live host/MCP integration.

## What The Author Must Understand

Level 1: a failed response is not proof of a failed transaction; the packet/key
must survive uncertainty. A server row is authoritative; a local receipt is a
recovery aid. DPAPI protects stored bytes from other identities, not arbitrary
code running as the same Windows user. A Skill is guidance, an MCP server is
a tool protocol, and the host model decides how to use those tools.

Level 2: follow terminal login -> protected credential -> gateway -> httpx ->
existing API. Explain packet publication before POST, schema/digest checks,
single-attempt replay, sanitized errors, account binding and fresh credential
loading after re-login.

## Knowledge Check

1. Why can a timed-out POST be safely recovered only with the original key/payload?
2. What should happen when a server write succeeds but local receipt storage fails?
3. Why must an old pending packet not be replayed under a different account?
4. What does DPAPI not protect against when the host can execute arbitrary code?
5. Which parts work now, and which require an installed SDK and actual host test?
