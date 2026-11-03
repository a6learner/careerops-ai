# Temporary Cloud Lab Execution — 2026-10-28

## Scope

Private, short-lived learning deployment using synthetic data and fake providers.
Preparation and local verification are recorded separately in
`2026-10-28-cloud-lab-preparation.md`. No personal data or credentials belong here.

## Observed Progress

The author supplied Lightsail console screenshots showing:

- Access to the Lightsail console after account registration.
- Selection of an Oregon dual-stack 4 GB / 2 vCPU / 80 GB plan, displayed at $24/month.
- Creation of instance `careerops-cloud-lab` in Oregon Zone A with an Ubuntu blueprint.
- The instance detail page reports `Starting`; browser SSH is not yet available.

These are screenshot observations, not live API or SSH verification. Ubuntu
version, CPU architecture, running status, firewall rules, Docker availability,
remote deployment and billing have not been verified. No cloud shell command has
been executed by the assistant.

## Next Step

Wait for Running, use the Lightsail browser SSH client, and inspect OS version,
architecture, memory, disk and the public SSH host-key fingerprint. Download the
regional default private key locally for later Windows SSH/scp and tunneling;
never paste or commit its contents. Verify these facts before installing Docker.
Then follow `../operations/cloud-lab.md` for the remaining release and teardown.

## Browser SSH Preflight

The author subsequently reported Running and supplied a browser-terminal
screenshot. The login banner shows Ubuntu 24.04.4 LTS; `uname -m` reports
`x86_64`. `free -h` shows approximately 3.7 GiB RAM, 3.3 GiB available and no
swap. `df -h /` shows approximately 77 GB total and 75 GB available.
These observations establish successful browser SSH access and resource
visibility, not application capacity or deployment success.

The OS-release command failed after a visible bracketed-paste escape prefix;
the host-key command targeted a `.pub~` filename with an extra trailing tilde.
Retry these two commands by typing them manually. Do not infer that `cat` or
the actual host public key is missing from these malformed commands.
Docker installation, firewall review, local SSH fingerprint matching and code
upload remain pending. No private key or credential has been recorded here.

The next terminal screenshot shows successful `/etc/os-release` output:
Ubuntu 24.04.4 LTS, codename `noble`, and a successful ED25519 SHA-256 host-key
fingerprint command. The earlier paste errors were corrected. The fingerprint
is available in the author's trusted browser SSH session for comparison with
the subsequent Windows SSH connection; local host identity matching has not
yet occurred. Next: locate the downloaded regional key without exposing its
contents, establish Windows SSH, then install Docker on the new lab VM.

## Authorized Assistant SSH Execution

The author subsequently confirmed successful local SSH and explicitly authorized
the assistant to operate this project directory and the new remote lab server.
The author requires using the designated private-key file through SSH without
reading its contents, and notification before accessing other sensitive files.
No private-key contents were read, copied, uploaded or logged. SSH uses batch
authentication and `StrictHostKeyChecking=yes`; account credentials and unrelated
local folders are outside the operational scope.

Direct remote preflight confirmed Ubuntu 24.04.4/noble, x86_64, approximately
3.3 GiB available RAM and 75 GB available disk. No Docker executable or lab
directory existed. Python 3 and curl were present.

Docker was installed using the official Ubuntu apt repository. Verified daemon:
29.9.2; Compose plugin: v5.6.1. No docker-group membership change or new AWS
resource was made. `scripts/cloud_lab_bootstrap.sh` preserves the install steps.
The first PowerShell text-pipe invocation completed installation but appended a
carriage return interpreted as an extra command (exit 1); a fresh SSH call
verified both versions and the transferred script passed `bash -n`. Use file
transfer/execution rather than a PowerShell text pipe for subsequent scripts.

Project-only release archive SHA-256:
`7b2081f81fe83f95d2e2783d866ac434b2ea62cbc3814eab5dde5f77c1fa7252`
(312 entries, including the new bootstrap script). Member checks excluded local
env files, private keys, databases, Git history, local dependencies and unsafe
archive paths. Remote checksum matched before extraction into a new private
`~/careerops-cloud-lab` directory. This supersedes the earlier local package hash
for this cloud execution; it does not rewrite the historical preparation record.

Remote init generated fresh database/JWT credentials without printing their
values. The lab config check passed: production settings, fake providers, no
model keys, loopback-only application ports. A pre-deployment listener check
showed SSH on port 22 and local system DNS only. AWS firewall rules have not
been inspected through the control plane.

Serial API/worker/frontend image build was started via SSH. Build output is saved
in the remote project directory as `cloud-lab-build.log`. Application startup,
cloud browser verification and remote recovery remain pending this build.

## Verified Cloud Release And Recovery

The serial build completed and the cloud release script exited successfully.
Release tag: `20261029015411` (UTC). The new database upgraded from empty to
Alembic head `202610270001`; `alembic check` reported no new operations.
API readiness reports database/Redis ready; frontend readiness reports API ready.
Host listener inspection confirms API `127.0.0.1:18010` and frontend
`127.0.0.1:13010`; PostgreSQL and Redis have no host-published ports.
Only SSH listens on a public interface. This is host observation, not an AWS
firewall audit or public HTTPS acceptance.

An assistant-owned Windows SSH local forward binds only `127.0.0.1:13010` and
connects to the remote frontend. The existing Playwright tests ran through this
tunnel against the cloud VM: **2 passed**, covering the CV-import/job-discovery
core loop and project source review/confirmation/withdrawal. All inputs were
synthetic; backend providers remain fake. Raw browser output is retained in
ignored `.cloud-lab/cloud-browser-tests.log`.

Cloud fault exercise, after browser completion:

- Verified exact Compose project labels before selecting resources.
- Stopped only the lab worker and submitted one synthetic Parse Run: queued.
- API readiness stayed ready while the worker was stopped.
- Cleared only the dedicated lab Redis DB, then restarted the worker.
- Bounded recovery dispatched the missing queued work from PostgreSQL once.
- The run succeeded at attempt 1 and produced 2 requirements.
- An extra one-time verification helper was transferred separately under the
  remote project scripts; application images and source were not changed.

Cloud backup exercise:

- Custom-format pg_dump was restored into an exclusively created scratch DB.
- Counts and ordered full-row JSON fingerprints matched across all 17 public
  tables while the source was idle. Scratch DB was removed afterward.
- The synthetic dump was exported with mode 0600, downloaded into the local
  ignored project lab directory, and its SHA-256 matched before any VM deletion.
- No private key, application credential file or real user dataset was downloaded.

The locked production frontend dependency audit (`--omit=dev --package-lock-only`)
ran inside a temporary container with read-only lockfiles and reported zero
vulnerabilities. No dependency was modified; dev-dependency warnings during
build were not resolved by a forced update. This audit is not a complete security
assessment of the application or OS.

Image identities, aggregate fault/backup evidence and limits are preserved in
`2026-10-28-cloud-lab-run.json`. The VM and application are intentionally retained
for the author's inspection. No additional AWS resource was created and no model
provider was enabled. No commit/push was performed.

## Initial Post-Release State (Superseded By Teardown Below)

The author can inspect the cloud app on this computer through the current SSH
forward at `http://127.0.0.1:13010`. It needs a synthetic account; the local
development database was not copied. The forward is a live local process, not a
permanent hosting URL. Reconnect using the documented SSH forwarding command if
it ends. The VM continues to incur its normal plan charges while retained.

After inspection, remove only this lab's containers/volume through the guarded
destroy action. The author must delete the named Lightsail instance and inspect
associated resources in the AWS console to end cloud billing. Cloud-resource
deletion, final billing and an incompatible-schema rollback exercise remain
unverified. Public HTTPS, live models, remote MCP and formal public P1-14
completion remain outside this private lab result.

## Interrupted Teardown And Revised Retention Request

After the author finished inspection and requested shutdown, the guarded
`destroy DELETE-SYNTHETIC-LAB-DATA` action was dispatched. The turn was interrupted
and the author clarified that containers/network/data should be retained while
the VM is stopped. An immediate follow-up attempted to terminate any remaining
matching teardown process. At `2026-10-29T03:26:11Z`, label-scoped checks found no
remaining lab containers, network or database volume: the earlier teardown had
already taken effect. These resources were not preserved in place. No further
resource deletion was performed after the revised instruction.

Targeted follow-up checks confirmed the remote project directory, all three
release images and the earlier synthetic verification dump still exist. The
local synthetic backup also exists and its original SHA-256 still matches.
It permits restoration to the verification-time state; changes made during the
author's later inspection are not established as backed up. No recovery has
been performed or claimed. The VM itself has not been stopped/deleted by the
assistant, and no snapshot was created.

The author asked whether stopping prevents billing. Official Lightsail billing
documentation was rechecked: normal Lightsail instance plans bill in both
running and stopped states until deletion. Retaining snapshots also incurs
storage fees. The author's revised retention preference must be resolved with
this cost information before any instance deletion. No cloud lifecycle change
is inferred from application teardown.

## Author-Reported Instance Deletion

The author subsequently stated that the Lightsail instance was deleted.
The assistant-owned SSH forward returned terminal exit code 1 with
`Connection ... closed by remote host`; it is no longer running. No further
SSH connection will be attempted to the former address, which may be reassigned.
Local project source, verification records and the checksum-verified synthetic
backup remain. There was no Git commit/push or private-key deletion.

Cloud instance deletion is recorded as author-reported, not independently
verified through the AWS API. Final charges and any remaining snapshots, static
IPs or extra disks are not verified. The practical learning exercise is closed;
checking those resource categories and the eventual bill is the remaining
account-side cost reconciliation step, not a claim of continuing VM operation.

## Publication Preparation

The author explicitly requested commit and push after the exercise. Refreshed
remote refs showed no existing unpushed commits. The trusted fetch/push URL
matched `git@github.com:a6learner/careerops-ai.git`. Publication targets the
existing `codex/p1-3b-embedding-holdout` development branch.

Before committing, all three shell scripts passed Bash syntax checks; the
daemon-free failure-path tests and Ruff passed. The staged lab configuration,
scripts and documentation were scanned for private keys, provider tokens,
bearer JWTs, account identifiers, personal paths and the former server address;
no unresolved finding was found. JSON artifacts parsed, staged shell files had
LF line endings, and `git diff --check` passed. Local credentials, raw backups,
transfer packages and temporary verification helpers remain ignored.
Git history and the remote ref identify the resulting publication commit.
