# Container Deployment Rehearsal — 2026-10-06

## Scope

This is local synthetic evidence for the platform-neutral P1-8d deployment
contract. It is not evidence of cloud deployment, production availability,
security certification, throughput, or recovery time.

- Final Compose project: `careerops-p18d-final`
- API host port: `18080`
- PostgreSQL host port: `15432`
- Redis host port: `16379`
- Providers: parser, embedding, and evidence matcher forced to fake
- Provider credentials: explicitly empty in the rehearsal process
- Real provider calls: none
- Starting database: new isolated empty volume

## Verified Result

| Check | Result |
|---|---|
| Constrained Python 3.11 Linux image build | passed |
| One-shot migration before API/worker | passed |
| Alembic revision | `202610060001` |
| Repeated `alembic upgrade head` | passed |
| `GET /healthz` | HTTP 200, `ok` |
| `GET /readyz` | HTTP 200, PostgreSQL and Redis ready |
| API runtime identity | `uid=100(careerops) gid=101(careerops)` |
| Worker runtime identity | `uid=100(careerops) gid=101(careerops)` |
| Runtime dependency consistency | `pip check`: no broken requirements |
| Containers, network, and volume cleanup | passed; zero matching residue |

## Failure Found And Corrected

The first isolated startup attempt reused fixed host mappings `5432` and `6379`,
which collided with the existing development stack. Compose stopped before the
application started, and the `finally` path removed the temporary containers,
network, and volume.

PostgreSQL and Redis host mappings are now configurable while retaining their old
defaults. The successful rehearsal used `15432` and `16379`; service-to-service
URLs inside Compose remained unchanged.

## Reproducibility Boundary

`constraints/deployment-py311-linux.txt` records the runtime versions installed in
the verified Linux image. Docker still resolves the base-image tag and downloads
packages during a fresh build, so the saved constraints improve Python dependency
repeatability but are not a complete software-supply-chain attestation. Dependency
updates require review, CI, and another deployment rehearsal.

## Cleanup Evidence

After `docker compose --project-name careerops-p18d-final down --volumes
--remove-orphans`, follow-up Docker queries found no container, network, or volume
whose name matched the isolated project.
