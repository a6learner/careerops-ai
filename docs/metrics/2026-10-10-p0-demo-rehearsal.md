# P0 Demo Rehearsal — 2026-10-10

## Scope

Timed browser rehearsal of the 3–5 minute script in
`docs/demo/p0-demo-script.md`. The run used an isolated Compose project and
deterministic fake providers. It is local functional and pacing evidence, not
presentation-quality, real-model, cloud, or production evidence.

## Successful Run

- Run ID: `20261010h`
- Compose project: `careerops-p110-20261010h`
- Browser origin: `http://127.0.0.1:13013`
- Browser phase: 210.3 seconds (3 minutes 30.3 seconds)
- Migration: passed
- Frontend identity: `uid=1000`
- Parser provider: `fake`
- Embedding provider: `fake`
- Evidence matcher provider: `fake`
- Browser core loop: passed
- Demo pacing gate (180–300 seconds): passed
- Exact project cleanup: passed

The Chromium path registered a synthetic user, created an Experience and Job,
parsed requirements, showed one validated positive quote and one explicit gap,
created and completed an Action Item, updated the Job to Applied, and verified
the Dashboard counts through the public frontend origin only.

## Preceding Port Conflict

Run `20261010g` stopped before migration because the default Redis host port was
already allocated by an unrelated Docker resource. No product workflow ran. The
harness removed every resource belonging to that failed project. The successful
run used explicit alternate ports and did not inspect, stop, or modify the
unrelated resource.

That failure led to a stronger preflight check that combines Windows TCP
listeners with Docker's published-port inventory. A focused follow-up on
2026-10-11 confirmed that all four occupied default ports are now rejected before
build or resource creation, pre-existing environment values are restored, and
the unrelated `careerops-p110-manual` stack remains running.

## Reproduction

```powershell
.\scripts\local_full_stack_acceptance.ps1 `
  -RunId <unique-run-id> `
  -PostgresPort <free-port> `
  -RedisPort <free-port> `
  -ApiPort <free-port> `
  -FrontendPort <free-port> `
  -DemoRehearsal
```

Without `-DemoRehearsal`, the acceptance remains fast and does not insert
narration pauses.

## Limitations

- The automation validates browser state and pacing; a human presenter still
  needs to deliver the narration naturally.
- All data is synthetic and all model providers are fake.
- The run does not measure production latency, availability, accessibility, or
  real-provider quality.
