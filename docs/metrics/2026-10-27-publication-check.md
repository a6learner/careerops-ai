# Publication Check

The author requested a concise GitHub README and authorized commit/push of the
current project. The README now describes the product, demonstrated workflows,
basic startup and current limits. Detailed development instructions were moved
to `docs/development.md`; the prior source/evaluation records remain available.

## Verification

- Offline backend regression: **443 passed, 26 integration cases deselected**.
  [JUnit](2026-10-27-publication-unit.xml).
- Strict mypy: passed for 145 source files.
- Ruff: passed across the repository.
- Import boundaries: both contracts kept.
- README relative links and screenshot target: verified locally.
- Quick-start Compose configuration: checked for fake providers and documented ports.
- Existing PostgreSQL/browser and real Codex demonstration evidence remains in
  its original stage records; no new provider or frozen holdout run was made.

The offline regression used fake providers and did not connect to the retained
demo database. It does not replace earlier database or browser acceptance.

## Public Artifact Review

JUnit hostnames and local workspace, Python environment and user-profile path
prefixes were replaced with neutral labels before publication. XML parsing and
test names/counts/outcomes/timings were checked before and after replacement.
Historical failed reports were retained; their failure outcomes were not changed.
Synthetic invalid-path inputs that are part of test names remain unchanged.

The pending text changes and previous commits between the remote default branch
and current work were scanned for provider keys, bearer JWTs, private keys and
private user-profile paths. No unresolved match was found. Demo screenshot/data
inspection found only the isolated synthetic project. Credentials, protected
packets, host process logs, caches and local `.env` files remain untracked/ignored.

## Publication Scope

The trusted remote was verified as `git@github.com:a6learner/careerops-ai.git`.
The remote `main` is an ancestor of the development history. Publication advances
the existing history without a force push so that the default-branch README and
code describe the same product. Git history records the final commit identities.
The main project plan remains the stage ledger; publication does not imply author
acceptance of all milestones or production readiness.

Implementation commit: `668669d` (`feat: add reviewed project journal and local
MCP integration`). The concise README, development guide and this publication
record form the subsequent documentation commit.
