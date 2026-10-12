# jobsmith

Keep your job search in plain files — profile, resumes, cover letters, and every
application you've sent — and let an AI agent (Claude Code) do the busywork:
tailoring resumes, tracking follow-ups, filling Workday forms, drafting LinkedIn posts.

> Early days. Expect breaking changes.

## How it works

jobsmith is the **tool**, installed as a command and a Claude Code plugin. Your **data** lives
in a separate, private repo of plain files. Nothing personal ever goes in this repo, and
nothing of jobsmith's is copied into yours beyond a little wiring.

```
your-private-repo/
├── profile/profile.yaml   contact info, work authorization, standard answers
├── resumes/               JSON Resume files: base.json + tailored versions
├── cover-letters/
├── applications/          one Markdown file per application (YAML frontmatter + notes)
├── linkedin/
├── accounts.yaml          which site accounts exist (passwords live in the OS keychain)
└── .jobsmith/guide.md     the agent guide, written by `jobsmith init`
```

See [`examples/`](examples/) for the file formats. Resumes use the
[JSON Resume](https://jsonresume.org) schema.

## Get started

You need [uv](https://docs.astral.sh/uv/), git, and Google Chrome (for browser features). Then:

```bash
uv tool install git+https://github.com/CharlieQNguyen/jobsmith
jobsmith init ~/Developer/my-job-search
cd ~/Developer/my-job-search
gh repo create my-job-search --private --source . --push   # or any private remote
```

`jobsmith init` creates your data repo and wires up Claude Code:

- `CLAUDE.md` imports jobsmith's [data repo guide](src/jobsmith/data-repo-guide.md), written to
  `.jobsmith/guide.md`, and leaves room for your own notes
- the `jobsmith` Claude Code plugin from this repo's marketplace, enabled for that repo only:
  job-search skills (`/jobsmith:*`), a `jobsmith-browser` MCP server so Claude can drive the
  browser you sign into, and a session-start check that the command is installed and the wiring
  is current

| Skill | What it does |
|---|---|
| `/jobsmith:apply <url>` | Records the job, gets you signed in, fills the application from your profile, and submits only when you say so |
| `/jobsmith:import-linkedin` | Reads your own LinkedIn profile (a few pages, human-paced) and fills your profile and base resume after you review it |
| `/jobsmith:track <news>` | "Acme rejected me", "screen with Globex Tuesday", "what's due?" |

Run `jobsmith init --force .` later to refresh that wiring. It never touches your data. The data
repo records the jobsmith version it was set up with in `.jobsmith/version`, and at the start of
each session the plugin says when that, the CLI and the plugin disagree. Update with
`uv tool upgrade jobsmith` and `/plugin marketplace update jobsmith`.

A data repo made by an older jobsmith has jobsmith as a submodule at `tools/jobsmith`. Remove it
(`git rm tools/jobsmith`), run `jobsmith init --force .`, and change the first line of
`CLAUDE.md` to `@.jobsmith/guide.md`.

## Commands

```bash
jobsmith init [DIR] [--force | --check]  # create or refresh a data repo
jobsmith check                           # validate all data files
jobsmith apps add --company C --role R [--url URL]   # start tracking (detects the ATS)
jobsmith apps update QUERY [--status S] [--event TEXT] [--followup +7d]
jobsmith apps show QUERY                 # QUERY: slug or words from company/role
jobsmith apps list --open                # open applications
jobsmith apps due                        # follow-ups due today or earlier
jobsmith resume render [FILE.json]       # one-page PDF beside it (default resumes/base.json)
jobsmith creds new HOST USERNAME         # generate a password, keep it in the keychain, copy it
jobsmith creds copy HOST USERNAME        # copy a stored password to the clipboard
jobsmith browser start | stop | status   # the Chrome you sign into and an agent drives
jobsmith login HOST [--url LOGIN_PAGE]   # sign in there with the keychain password
```

Commands find the data directory from `--data`, then the nearest data repo at or above the current
directory, then `$JOBSMITH_DATA`, then the current directory.

## Supported applicant tracking systems

| ATS | Hosts |
|---|---|
| Workday | `*.myworkdayjobs.com`, `*.myworkdaysite.com`, `*.myworkday.com` |
| Anything else | Generic login-form detection |

Adding one is a small module plus a fake sign-in page for tests; the `add-ats` Claude Code skill
walks through it.

## Credentials

Site passwords are stored in the OS keychain through [`keyring`](https://pypi.org/project/keyring/)
under the service name `jobsmith:<host>`. jobsmith never prints a password; it copies
it to the clipboard. The data repo only records that an account exists.

## Signing in, then handing off to an agent

`jobsmith browser start` launches your installed Google Chrome with its own profile
(`~/.local/share/jobsmith/chrome-profile`, shared by all your data repos) and a DevTools port on
`127.0.0.1:9222` (override with `$JOBSMITH_CDP_PORT`). Sessions persist between runs.

`jobsmith login HOST` opens the account's sign-in page there and fills the username and
keychain password. **Run it yourself** — it's the one step that touches your password. Handle
any MFA or CAPTCHA in the window.

An agent then attaches to the same browser and carries on signed in. In Claude Code the jobsmith
plugin's `jobsmith-browser` MCP server does this; other agents can use any CDP client on the port.

While the port is open, any program on your machine can drive that browser. Run
`jobsmith browser stop` when you're done.

## Contributing

```bash
git config core.hooksPath .githooks   # blocks commits that look like personal data
uv run pytest                         # browser tests need Chrome; skip with -m "not browser"
uv run ruff check
uv tool install --editable .          # the `jobsmith` command runs this checkout
```

Working with Claude Code in this repo gives you two skills:

- `/ship` — format, lint, test, review the diff for personal data, commit, push and merge
- `add-ats` — add or fix an applicant tracking system with a fake sign-in page and a headless test

## License

MIT
