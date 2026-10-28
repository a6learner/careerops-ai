# MCP Tool Boundary

## What Changed And Why

The optional `agent` extra installs the approved official Python MCP SDK. The
stdio adapter exposes the existing local project gateway to coding assistants.
The coding host supplies the model; CareerOps supplies evidence storage and
retrieval. API and worker images do not install this extra.

The adapter is a transport boundary, not a new agent planner. It does not make
model calls, run shell commands, scan a repository, or confirm career claims.
The repository Skill tells the host when and how to select useful checkpoints.

## Failure Modes

- A discovered tool is not proof that the user is signed in. Credentials remain
  in protected local storage and can be renewed from the human terminal.
- An interrupted request may already have committed. Save/replay retains the
  existing gateway's original UUID and encrypted packet instead of inventing a
  new operation.
- A successful save creates a draft, not verified personal experience. Only the
  existing user review flow can confirm it; evidence reads must use current state.
- Stdout is protocol data. Diagnostics or login prompts there would corrupt the
  connection. Startup and tool errors must also avoid leaking secret details.
- Tool annotations are host hints. Runtime validation, API ownership checks and
  database constraints still enforce the actual contract.

## Verification

Protocol results and their limits are recorded in
`../metrics/2026-10-27-project-agent-mcp-test-record.md`. Tests with the official
SDK client can prove discovery, schemas and calls. They do not prove that a real
coding host chose the right time to record, or that generated resume prose is good.
Host model use and user acceptance remain separate checks. The subsequent real
Codex synthetic demonstration is documented in [0050](0050-project-agent-demo.md).

## What The Author Must Understand

Level 1: the host runs the model; the MCP server offers bounded tools; the API
owns authentication, authorization and durable transactions. A caller-provided
upload declaration is not an independent human approval mechanism.

Level 2: start the module with the project Python environment, configure only the
loopback API origin and local state directory, sign in separately, and interpret
pending/rejected receipts before retrying.

## Knowledge Check

1. Which component decides to call `save_checkpoint`, and which stores the result?
2. Why are login and confirmation absent from the tool list?
3. What must remain unchanged when a save response is lost?
4. Why can an SDK stdio test pass while host acceptance is still pending?
5. Why do read-only tool annotations not replace authorization tests?
