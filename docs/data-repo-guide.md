# jobsmith data repo

This repo holds one person's job search data. It is **private**. The tool that reads it is
jobsmith, a **public** repo included as a submodule at `tools/jobsmith` (see
`tools/jobsmith/CLAUDE.md`). This guide lives in jobsmith and is imported by the data repo's
CLAUDE.md, so it updates with the submodule.

## Layout

- `profile/profile.yaml` — contact info, work authorization, and reusable answers to common
  application questions (`standard_answers`). Use these when filling forms.
- `resumes/` — JSON Resume files. `base.json` is the master; tailored copies are named
  `YYYY-MM-<company>-<role>.json`. Never edit `base.json` just to tailor for one job.
- `cover-letters/` — Markdown, named like the tailored resume.
- `applications/` — one `<company>-<role>.md` per job: YAML frontmatter (schema: `Application` in
  `tools/jobsmith/src/jobsmith/models.py`) plus free-form notes. Append to `events` rather than
  rewriting history; keep `status` and `next_followup` current.
- `linkedin/` — drafted posts and profile text.
- `accounts.yaml` — which site accounts exist (host, username, created, login_url). **No
  passwords** — those live in the OS keychain under `jobsmith:<host>`.

## Commands

`jobsmith` is installed as an editable uv tool from `tools/jobsmith` in the main checkout.
`tools/jobsmith/scripts/sync.sh` keeps it installed and reinstalls when dependencies change; it
runs on Claude Code session start and after git merge/checkout. Commands find the data from the
current directory (nearest folder with `accounts.yaml`), so they act on whichever checkout or
worktree you're in.

- `jobsmith check` — validate all data files
- `jobsmith apps add --company … --role … [--url …]` — start tracking; prints the slug
- `jobsmith apps update <slug or words> [--status …] [--event "…"] [--on DATE] [--followup +7d|DATE|none]`
  — prefer this to hand-editing frontmatter; status changes are logged as events
- `jobsmith apps list --open`, `jobsmith apps show <query>`
- `jobsmith apps due` — follow-ups due
- `jobsmith browser status` — is the signed-in Chrome up?
- `jobsmith init --force .` — refresh this repo's scaffolding from the current jobsmith (never
  touches your data files)

## Claude Code plugin

`.claude/settings.json` registers `tools/jobsmith` as a local plugin marketplace and enables the
`jobsmith` plugin for this repo only. It provides the `jobsmith-browser` MCP server and the
`/jobsmith:*` skills — `apply` (job URL → submitted application) and `track` (status news,
follow-ups). It loads in place from the submodule, so it always matches the pinned CLI.

## Sessions, worktrees and development

- Sessions often run in a **git worktree** of this repo. The session-start hook checks out the
  submodule there. Data commands act on the worktree's files, so commit there and merge to
  `main`. The global `jobsmith` command still runs the main checkout's code. To test jobsmith
  changes made in a worktree, use `uv run --project tools/jobsmith jobsmith …`.
- The browser profile is per user (`~/.local/share/jobsmith/chrome-profile`), so sign-ins carry
  over between sessions and worktrees.
- **Project status and next steps:** `tools/jobsmith/docs/ROADMAP.md`. Read it before
  development work and update it when something ships.
- To hand work to a fresh session, start it in this repo, not in `tools/jobsmith`, so this guide,
  the plugin and the hooks load. Put the task and any context not written down here in its
  first message.

## Signing in to sites

1. New site: the user runs `jobsmith creds new <host> <email> --login-url <sign-in page>`, then
   pastes the clipboard password into the site's sign-up form.
2. The user runs `jobsmith login <host>` (starts Chrome if needed, fills credentials from the
   keychain). Suggest they type it as `! jobsmith login <host>` in the chat.
3. Claude drives that same Chrome with the `jobsmith-browser` MCP tools (from the jobsmith
   plugin, CDP on 127.0.0.1:9222). If those tools can't connect, ask the user to run step 2.
4. `jobsmith browser stop` when done — the open DevTools port lets any local program drive Chrome.

## Rules

- `tools/jobsmith` is **public**. Never copy anything from this repo into it. Its pre-commit hook
  blocks obvious leaks; don't rely on it.
- When changing jobsmith: commit and push inside `tools/jobsmith` first, then commit the updated
  submodule pointer here (the `ship` skill does this). `push.recurseSubmodules=check` refuses a
  push that gets the order wrong.
- Credentials: never read, print, or type passwords, and never run `jobsmith login` or
  `jobsmith creds copy` — those are the user's steps. Claude takes over after login.
- Browser actions on third-party sites (Workday, LinkedIn): confirm before entering personal data
  and before every submit/post. Keep LinkedIn activity human-paced and low-volume, never scrape,
  and stop immediately on a CAPTCHA or "unusual activity" warning.
