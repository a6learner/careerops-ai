# ADR-043: Temporary Private Cloud Deployment Lab

## Status

Authorized preparation on 2026-10-28. Local verification and cloud execution are
tracked separately in the metrics record. No paid resource is created by preparation.
The subsequent private cloud exercise passed its browser and recovery checks;
the author reported instance deletion. See `2026-10-28-cloud-lab-run.md` under
`docs/metrics/` for the teardown sequence and evidence limits.

## Context

The author wants to learn remote deployment for a few hours and remove the
resources afterward. Public users, a persistent service and real-model quality
are outside this exercise. P1-13 and the public P1-14 contract remain outstanding.

## Decision

Prepare a separate single-host Compose topology for an Ubuntu x86_64 Lightsail
candidate. The author creates the account, approves the displayed hourly price
and provisions the instance. Use new synthetic data and fixed fake providers.
PostgreSQL owns data; Redis is disposable. Keep API and worker process roles.
Use random per-lab credentials and deployment environment `production`.

Publish only frontend/API on the server loopback interface; publish neither
database nor Redis. Access the web UI through an SSH local forward to the same
browser loopback origin used by existing acceptance. Preserve Secure cookies,
same-origin checks, and backend authorization. Do not expose a public HTTP site.
SSH protects the transport; public HTTPS/DNS remains a separate exercise.

Keep the agent client's loopback-only restriction. Do not install server MCP,
enable live providers, or change schema/auth/API contracts. The chosen private
experiment is not an exemption that marks P1-13 or public deployment complete.

Build explicit release-tagged images before startup. One script runs the
migration and starts the application only on migration success. Failed releases
retain logs and database state; rollback never automatically downgrades schema.
Credentials and dumps are ignored and private on the VM. Archive restoration
uses a separate exclusively created scratch database, never the active database.
Cleanup has an exact project scope and a separate synthetic-data deletion gate.
Cloud deletion is a human operation after downloading evidence.

## Alternatives Considered

- Long-lived hosting: unnecessary for this learning objective.
- Managed database/queue and load balancer: extra cost and components for the first lab.
- Public IP HTTP with insecure cookies: would weaken the accepted session boundary.
- Public HTTPS/domain: valuable follow-up, not required to learn the first remote release.
- Remote MCP/auth redesign: separate user story, not needed for browser deployment.

## Consequences

Single-host failure can lose availability and data. Backup and restoration are
explicit exercises rather than high availability. Build capacity is unmeasured;
4 GB is a candidate starting size. No automatic budget cap or shutdown exists.
Lightsail stopped instances remain billable; users must delete and inspect
associated resources. Recovery is manual and bounded, not continuously scheduled.

## Verification Or Evidence

See `docs/metrics/2026-10-28-cloud-lab-preparation.md` for actual commands,
results, unresolved limits and the next user action. See the operations guide for
account provisioning, SSH, transfer, release, checks, backup and deletion.
