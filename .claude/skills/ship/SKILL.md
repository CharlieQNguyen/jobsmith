---
name: ship
description: Check, review and land jobsmith changes through a squash-merged PR. Use when the user says ship, commit and push, or publish their jobsmith changes.
disable-model-invocation: true
---

# Ship jobsmith changes

jobsmith is **public**. Every push publishes.

## 1. Locate the repo

```bash
J="$(git rev-parse --show-toplevel)"          # run from inside jobsmith
```

Confirm `$J/pyproject.toml` has `name = "jobsmith"`.

## 2. Check

Run from `$J`; stop and fix (or report) on the first failure:

```bash
uv run ruff format .
uv run ruff check .
uv run pytest -q
```

`ruff format` may modify files. That's expected; include them in the commit.

## 3. Review what's going public

- `git -C "$J" status --short` and `git -C "$J" diff --stat`. If nothing changed, say so and stop.
- If the change reaches users (the CLI, the plugin, or what `jobsmith init` writes), bump the
  version in `pyproject.toml`, `src/jobsmith/__init__.py` and `.claude-plugin/plugin.json`
  together, then `uv lock`. A test fails when they differ. The plugin installs the CLI at its own
  version when they differ, and data repos record the version they were set up with, so a bump
  is what reaches users.
- Read the full diff. Look for anything personal: real names, emails, phone numbers,
  companies the user applied to, resume content, paths under `/Users/<name>`. The pre-commit hook
  catches only the obvious cases. **If you find anything, stop and show it to the user.**
- If on `main` with unrelated changes mixed together, offer to split them into separate commits.

## 4. Land jobsmith through a PR

- On a detached HEAD or on `main`, create a branch: `git switch -c <short-kebab-name>`.
- Stage explicitly (`git add <paths>`), not `git add -A`, unless every change was reviewed above.
  Commit messages: imperative subject ≤ 72 chars, a body explaining *why* when it isn't obvious.
- **Show the user the PR title and the file list and ask before pushing.** It's a public repo.
  Skip the question only if they already said to ship in this request.
- `git rebase origin/main` (rerun step 2 if anything came in), then `git push -u origin HEAD`,
  then `gh pr create` with a title and body that read well as the squash commit. End the body
  with the attribution line this session uses.
- `gh pr merge --squash`. GitHub deletes the branch. Then `git switch main && git pull --ff-only`.
  Never force-push or enable auto-merge.

## 5. Report

One or two lines: the jobsmith commit (short SHA + subject) and test count. Mention anything
skipped.
