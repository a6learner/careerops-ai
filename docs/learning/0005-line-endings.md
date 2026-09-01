# 0005 Line Endings

## What Changed

This step added `.gitattributes` to normalize line endings:

```gitattributes
* text=auto eol=lf
*.bat text eol=crlf
*.cmd text eol=crlf
*.ps1 text eol=crlf
```

Most project files will use LF. Windows command scripts keep CRLF because that is the safer convention for those file types.

## Why It Exists

Git on Windows can warn that LF will be replaced by CRLF. The warning is not a code bug, but it creates noise when reviewing changes.

For a portfolio project, noisy diffs are a real problem: reviewers should see meaningful code and docs changes, not accidental line-ending churn.

## Failure Modes It Prevents

- Large diffs where many lines appear changed only because line endings changed.
- Different contributors committing different line endings from different operating systems.
- CI behaving differently from local checks because scripts or config files were normalized inconsistently.

## How To Verify It

Run:

```powershell
git status --short
git diff --check
```

`git diff --check` should report no whitespace errors.

## What You Must Understand

Level 2 concepts:

- Git tracks file content, and line endings are part of that content.
- `.gitattributes` lets a repository define its own line-ending policy.
- This is project hygiene, not business logic.

## Knowledge Check

1. Why can line-ending churn make a pull request harder to review?
2. Why do we keep `.ps1`, `.bat`, and `.cmd` as CRLF while most files use LF?
3. Why is `.gitattributes` better than relying on every developer's global Git setting?
