---
name: ship
description: Check, commit and push jobsmith changes — and, when jobsmith is a submodule of a data repo, commit and push the updated submodule pointer there too, in the right order. Use when the user says ship, commit and push, or publish their jobsmith changes.
disable-model-invocation: true
---

# Ship jobsmith changes

jobsmith is **public**. Every push publishes. Its data repo (if any) is private and pins jobsmith
by commit, so jobsmith must be pushed **before** the data repo's pointer update.

## 1. Locate the repos

```bash
J="$(git rev-parse --show-toplevel)"          # run from inside jobsmith
P="$(git -C "$J" rev-parse --show-superproject-working-tree)"   # empty if standalone
```

If the current directory is the data repo rather than jobsmith, use `J=tools/jobsmith`.
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

- If this work ships or changes something listed in `docs/ROADMAP.md`, update it now so it's in
  the same commit.
- `git -C "$J" status --short` and `git -C "$J" diff --stat`. If nothing changed, say so and skip
  to step 5 (the pointer may still need committing).
- Read the full diff. Look for anything personal: real names, emails, phone numbers,
  companies the user applied to, resume content, paths under `/Users/<name>`. The pre-commit hook
  catches only the obvious cases. **If you find anything, stop and show it to the user.**
- If on `main` with unrelated changes mixed together, offer to split them into separate commits.

## 4. Commit and push jobsmith

A freshly checked-out submodule is on a detached HEAD. Before committing, `git -C "$J" switch main`
and `git pull --rebase`, keeping the working-tree changes (`git stash` around it if needed).
jobsmith changes go to its `main`.

- Stage explicitly (`git add <paths>`), not `git add -A`, unless every change was reviewed above.
- Commit message: imperative subject ≤ 72 chars, a body explaining *why* when it isn't obvious,
  ending with the attribution trailer this session uses.
- **Show the user the commit subject and file list and ask before pushing.** It's a public repo.
  Skip the question only if they already said to push in this request (e.g. "ship it").
- `git -C "$J" push`. If rejected because the remote moved: `git pull --rebase`, rerun step 2,
  push again. Never force-push.

## 5. Update the data repo (only if `$P` is set)

```bash
git -C "$P" add tools/jobsmith
git -C "$P" commit -m "Bump jobsmith: <jobsmith commit subject>"
git -C "$P" push
```

If `$P` is a worktree on a branch other than `main`, the push publishes that branch. Tell the
user it still has to be merged into `main`, or merge it if they ask.

Commit only the submodule pointer here unless the user asked to include other data-repo changes.
`push.recurseSubmodules=check` makes this push fail if step 4 didn't land. If it does, go back
and push jobsmith.

## 6. Report

One or two lines: the jobsmith commit (short SHA + subject), whether the data repo pointer was
updated, and test count. Mention anything skipped.
