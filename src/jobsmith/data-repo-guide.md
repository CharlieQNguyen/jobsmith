# jobsmith data repo

This repo holds one person's job search data. It is **private**. The tool that reads it is
jobsmith (https://github.com/CharlieQNguyen/jobsmith), which is **public** and is not part of
this repo. This guide ships with jobsmith: `jobsmith init --force .` writes it to
`.jobsmith/guide.md`, which this repo's CLAUDE.md imports.

## Layout

- `profile/profile.yaml` — contact info, work authorization, and reusable answers to common
  application questions (`standard_answers`). Use these when filling forms.
- `resumes/` — JSON Resume files. `base.json` is the master; tailored copies are named
  `YYYY-MM-<company>-<role>.json`. Never edit `base.json` just to tailor for one job. PDFs are
  rendered from them (`jobsmith resume render`) and sit beside them with the same name.
- `cover-letters/` — Markdown, named like the tailored resume.
- `applications/` — one `<company>-<role>.md` per job: YAML frontmatter (schema: `Application` in
  jobsmith's `src/jobsmith/models.py`) plus free-form notes. Append to `events` rather than
  rewriting history; keep `status` and `next_followup` current.
- `linkedin/` — drafted posts and profile text.
- `accounts.yaml` — which site accounts exist (host, username, created, login_url). **No
  passwords** — those live in the OS keychain under `jobsmith:<host>`.

## Commands

The jobsmith plugin installs the `jobsmith` command (a uv tool) from its own copy at session
start, so the two are always the same version; update the plugin and the command follows. An
editable install, for developing jobsmith, is left alone. Commands find the data from the current directory
(nearest folder with `accounts.yaml`), so they act on whichever checkout or worktree you're in.

- `jobsmith check` — validate all data files
- `jobsmith apps add --company … --role … [--url …]` — start tracking; prints the slug
- `jobsmith apps update <slug or words> [--status …] [--event "…"] [--on DATE] [--followup +7d|DATE|none]`
  — prefer this to hand-editing frontmatter; status changes are logged as events
- `jobsmith apps list --open`, `jobsmith apps show <query>`
- `jobsmith apps due` — follow-ups due
- `jobsmith resume render [resumes/<file>.json] [--bullets N] [--full-roles N] [--html]` — PDF
  in the one-page compact layout (default `resumes/base.json`); warns if it overflows a page
- `jobsmith browser status` — is the signed-in Chrome up?
- `jobsmith init --force .` — refresh this repo's wiring and this guide from the installed
  jobsmith, and record its version in `.jobsmith/version` (never touches your data files).
- `jobsmith init --check .` — what is out of step: the plugin and CLI versions, this repo's
  recorded version, its wiring. The plugin runs it at session start and shows any line it prints.

## Claude Code plugin

`.claude/settings.json` registers jobsmith's GitHub repo as a plugin marketplace and enables the
`jobsmith` plugin for this repo only. It provides the `jobsmith-browser` MCP server and the
`/jobsmith:*` skills — `apply` (job URL → submitted application), `track` (status news,
follow-ups) and `import-linkedin` (seed the profile and base resume from your LinkedIn). Update
it with `/plugin marketplace update jobsmith`; the `jobsmith` command follows at the next
session start.

## Sessions and worktrees

- Sessions often run in a **git worktree** of this repo. Data commands act on the worktree's
  files, and the work reaches `main` when the session lands.
- The browser profile is per user (`~/.local/share/jobsmith/chrome-profile`), so sign-ins carry
  over between sessions and worktrees.
- To hand work to a fresh session, start it in this repo so this guide and the plugin load. Put
  the task and any context not written down here in its first message.

## Signing in to sites

1. New site: the user runs `jobsmith creds new <host> <email> --login-url <sign-in page>`, then
   pastes the clipboard password into the site's sign-up form.
2. The user runs `jobsmith login <host>` (starts Chrome if needed, fills credentials from the
   keychain). Suggest they type it as `! jobsmith login <host>` in the chat.
3. Claude drives that same Chrome with the `jobsmith-browser` MCP tools (from the jobsmith
   plugin, CDP on 127.0.0.1:9222). If those tools can't connect, ask the user to run step 2.
4. `jobsmith browser stop` when done — the open DevTools port lets any local program drive Chrome.

## Rules

- jobsmith is **public**. Never copy anything from this repo into it, or into an issue or pull
  request on it. Its pre-commit hook blocks obvious leaks; don't rely on it.
- Land work the way this repo's own notes in CLAUDE.md say. Without a rule there, commit on a
  branch and open a pull request; don't push to `main` directly.
- Credentials: never read, print, or type passwords, and never run `jobsmith login` or
  `jobsmith creds copy` — those are the user's steps. Claude takes over after login.
- Browser actions on third-party sites (Workday, LinkedIn): confirm before entering personal data
  and before every submit/post. Keep LinkedIn activity human-paced and low-volume, never scrape,
  and stop immediately on a CAPTCHA or "unusual activity" warning.
