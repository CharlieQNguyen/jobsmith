---
name: land
description: Finish a session's work in a jobsmith data repo — commit, land any jobsmith changes through a squash-merged PR first, then open and squash-merge the data repo PR with the updated submodule pointer, rebasing as needed, and update the main checkout. Use at the end of every working session, or when the user says land, merge, wrap up or finish.
disable-model-invocation: true
---

# Land a session

Both repos merge through **pull requests, squash only**, and GitHub deletes merged branches.
Order matters because of the submodule: **jobsmith lands first**, then the data repo points
`tools/jobsmith` at the squash commit on jobsmith's `main`, never at a branch commit, which
disappears with its branch.

Never force-push, never enable auto-merge, and never merge a PR whose checks are failing.
Stop and ask on any conflict you can't resolve mechanically.

## 0. Orient

```bash
D="$(git rev-parse --show-toplevel)"          # data repo checkout (often a worktree)
J="$D/tools/jobsmith"
M="$(dirname "$(git -C "$D" rev-parse --path-format=absolute --git-common-dir)")"   # main checkout
git -C "$D" status --short; git -C "$J" status --short
git -C "$D" fetch -q origin; git -C "$J" fetch -q origin
```

Pick a short kebab-case branch name `B` describing the work (e.g. `linkedin-import`). If `D` is on
a detached HEAD or on `main`, `git -C "$D" switch -c "$B"`. Otherwise use its current branch.

## 1. Land jobsmith (skip if it has no changes)

jobsmith has changes if `git -C "$J" status --short` is non-empty or it has commits not on
`origin/main` (`git -C "$J" log origin/main..HEAD`).

1. Run `/ship`'s check and review steps (format, lint, tests, personal-data review, roadmap).
   jobsmith is **public**.
2. Branch: `git -C "$J" switch -c "$B"` (it's usually on a detached HEAD). Commit. Then
   `git -C "$J" rebase origin/main` and rerun the tests if anything came in.
3. `git -C "$J" push -u origin "$B"`, then open the PR:
   `gh pr create -R CharlieQNguyen/jobsmith --head "$B" --title "<imperative summary>" --body "<why + what>"`.
   End the body with the attribution line this session uses. The title and body become the
   squash commit, so make them read well.
4. Merge: `gh pr merge <url> --squash`. Don't pass `--delete-branch`: it tries to check out
   `main` locally, which fails in a worktree. GitHub deletes the branch.
5. Move the submodule to the result: `git -C "$J" fetch -q origin && git -C "$J" switch --detach origin/main`.

## 2. Land the data repo

1. Stage and commit in `D`: data changes plus `tools/jobsmith` if it moved. This repo is
   private, so personal data is fine here, but make sure nothing from here went into jobsmith.
2. `git -C "$D" rebase origin/main`. If the only conflict is the `tools/jobsmith` pointer, pick
   the newer commit: `git -C "$J" merge-base --is-ancestor <a> <b>` says whether `b` descends
   from `a`. `git -C "$J" checkout <newer>`, `git add tools/jobsmith`, `git rebase --continue`.
   If neither descends from the other, stop and ask. Data-file conflicts: show them to the user.
3. `git -C "$D" push -u origin "$B"`, then
   `gh pr create -R CharlieQNguyen/job-search --head "$B" --title "…" --body "…"`, then
   `gh pr merge <url> --squash`.

If `origin/main` moved during all this and the merge is refused as out of date, rebase again
(2.2) and retry.

## 3. Update the main checkout

If `M` differs from `D` and `git -C "$M" status --short` is clean:

```bash
git -C "$M" switch -q main && git -C "$M" pull -q --ff-only   # submodule.recurse moves tools/jobsmith
```

The post-merge hook then runs `sync.sh`, which reinstalls `jobsmith` if its dependencies changed.
If `M` has uncommitted changes, don't touch it. Tell the user instead.

## 4. Clean up and report

- The session's worktree and local branch go away when the user archives the session in the
  app. Don't delete the worktree you're running in. `git -C "$M" worktree prune` clears leftovers.
- Report in two or three lines: the PR links, what landed, and anything left open (update
  `tools/jobsmith/docs/ROADMAP.md` in step 1 if an item moved).
