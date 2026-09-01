# 0003 Local Environment Isolation

## What Changed

This step created a project-local Python virtual environment:

```powershell
python -m venv .venv
```

Then project dependencies were installed into that environment:

```powershell
.\.venv\Scripts\python -m pip install -e ".[dev,worker]"
```

The README now uses explicit `.venv` command paths for tests, type checks, linting, Alembic, and Uvicorn.

## Why It Exists

Before this step, commands used the global Anaconda Python:

```text
D:\software\basic\anaconda\python.exe
```

That polluted the shared Anaconda environment with project dependencies. It also created a real warning: another package in that environment, `streamlit`, had dependency conflicts after project packages were installed.

A virtual environment isolates dependencies inside the project directory:

```text
D:\pdd\project\careerops-ai\.venv\Scripts\python.exe
```

The `.venv/` directory is ignored by Git, so it stays local and is not committed.

## Failure Modes It Prevents

- Installing project packages into Anaconda and breaking unrelated tools.
- Running tests with one dependency version locally and another version in CI without noticing.
- Having `pytest`, `mypy`, `ruff`, or `alembic` resolve to a global command instead of the project command.
- Making onboarding harder because a new machine cannot reproduce the setup cleanly.

## How To Verify It

Confirm the active interpreter:

```powershell
.\.venv\Scripts\python -c "import sys; print(sys.executable); print(sys.prefix); print(sys.base_prefix)"
```

Expected shape:

```text
D:\pdd\project\careerops-ai\.venv\Scripts\python.exe
D:\pdd\project\careerops-ai\.venv
D:\software\basic\anaconda
```

Run project checks through `.venv`:

```powershell
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\python -m mypy
.\.venv\Scripts\ruff check .
.\.venv\Scripts\lint-imports
.\.venv\Scripts\alembic history
```

## What You Must Understand

Level 1 concept:

- Reproducible environments are part of backend reliability. A project that only works because one machine has accidental global packages is not production-like.

Level 2 concepts:

- `.venv` is a local dependency sandbox.
- `python -m pip install ...` installs packages into whichever Python interpreter is used.
- Calling `.\.venv\Scripts\python` is safer than calling plain `python` after multiple Python installations exist.

## Current Risk Scan

These are the issues noticed during environment setup:

1. The global Anaconda environment was already touched earlier.
   - Status: known issue.
   - Impact: could affect unrelated local Python tools.
   - Action: do not keep installing this project into Anaconda. Do not uninstall packages from Anaconda without a separate review.

2. Local `.venv` is Python 3.12, while the project still supports Python 3.11+.
   - Status: reduced.
   - Impact: a Python 3.12-only feature could pass locally but fail in CI.
   - Action: CI now runs both Python 3.11 and 3.12. Keep `ruff` target and `mypy` Python version at 3.11.

3. Dependencies currently use lower bounds, not a lock file.
   - Status: acceptable for early development.
   - Impact: future installs may receive newer packages and expose warnings or behavior changes.
   - Action: add a lock or constraints file before deployment or before sharing setup instructions widely.

4. `pytest` showed a warning from the FastAPI/Starlette test client stack.
   - Status: reduced.
   - Impact: a future dependency update could turn this into a stronger compatibility issue.
   - Action: health endpoint tests now use `httpx.AsyncClient` with `ASGITransport` instead of FastAPI's deprecated `TestClient` path.

5. Docker Desktop was not running earlier.
   - Status: resolved for this run.
   - Impact: real PostgreSQL migrations could not be applied until Docker Desktop started.
   - Action: Docker Desktop is now running, PostgreSQL started successfully, and the first migration was applied.

6. Git reports a permission warning while reading the user's global ignore file.
   - Status: outside repository.
   - Impact: `git status` still works, but output is noisy.
   - Action: fix user-level Git config later if it becomes annoying; it does not block project code.

## Knowledge Check

1. Why does `.\.venv\Scripts\python -m pip install ...` install into `.venv`, while plain `python -m pip install ...` may install somewhere else?
2. Why is `.venv/` listed in `.gitignore`?
3. What risk comes from developing locally on Python 3.12 while CI runs Python 3.11?
4. Why should we avoid uninstalling packages from Anaconda immediately, even though it was polluted earlier?
5. Why is a warning from tests worth recording even when tests still pass?
