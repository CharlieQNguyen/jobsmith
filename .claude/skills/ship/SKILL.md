---
name: ship
description: Check, review and land jobsmith changes through a squash-merged PR. When jobsmith is a submodule of a data repo, hand off to /jobsmith:land so the data repo lands after it. Use when the user says ship, commit and push, or publish their jobsmith changes.
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

## 4. Land jobsmith through a PR

If jobsmith is a submodule of a data repo (`$P` is set), stop here and run `/jobsmith:land`.
It does this step and then lands the data repo in the right order.

Standalone:
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

## 6. Report

One or two lines: the jobsmith commit (short SHA + subject), whether the data repo pointer was
updated, and test count. Mention anything skipped.
