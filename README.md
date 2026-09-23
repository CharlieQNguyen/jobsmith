# jobsmith

Keep your job search in plain files — profile, resumes, cover letters, and every
application you've sent — and let an AI agent (Claude Code) do the busywork:
tailoring resumes, tracking follow-ups, filling Workday forms, drafting LinkedIn posts.

> Early days. Expect breaking changes.

## How it works

jobsmith is the **tool**. Your **data** lives in a separate, private repo that
includes jobsmith as a git submodule. Nothing personal ever goes in this repo.

```
your-private-repo/
├── tools/jobsmith/        ← this repo (submodule)
├── profile/profile.yaml   contact info, work authorization, standard answers
├── resumes/               JSON Resume files: base.json + tailored versions
├── cover-letters/
├── applications/          one Markdown file per application (YAML frontmatter + notes)
├── linkedin/
└── accounts.yaml          which site accounts exist (passwords live in the OS keychain)
```

See [`examples/`](examples/) for the file formats. Resumes use the
[JSON Resume](https://jsonresume.org) schema.

## Install

```bash
uv tool install --editable tools/jobsmith   # from your private repo
```

## Commands

```bash
jobsmith check                           # validate all data files
jobsmith apps list --open                # open applications
jobsmith apps due                        # follow-ups due today or earlier
jobsmith creds new HOST USERNAME         # generate a password, keep it in the keychain, copy it
jobsmith creds copy HOST USERNAME        # copy a stored password to the clipboard
jobsmith browser start | stop | status   # the Chrome you sign into and an agent drives
jobsmith login HOST [--url LOGIN_PAGE]   # sign in there with the keychain password
```

Commands read the data directory from `--data`, then `$JOBSMITH_DATA`, then the current directory.

## Credentials

Site passwords are stored in the OS keychain through [`keyring`](https://pypi.org/project/keyring/)
under the service name `jobsmith:<host>`. jobsmith never prints a password; it copies
it to the clipboard. The data repo only records that an account exists.

## Signing in, then handing off to an agent

`jobsmith browser start` launches your installed Google Chrome with its own profile
(`.browser-profiles/` in your data repo — keep it out of git) and a DevTools port on
`127.0.0.1:9222` (override with `$JOBSMITH_CDP_PORT`). Sessions persist between runs.

`jobsmith login HOST` opens the account's sign-in page there and fills the username and
keychain password. **Run it yourself** — it's the one step that touches your password. Handle
any MFA or CAPTCHA in the window.

An agent then attaches to the same browser and carries on signed in. For Claude Code, add a
Playwright MCP server pointed at the port (in your data repo's `.mcp.json`):

```json
{ "mcpServers": { "jobsmith-browser": {
  "command": "npx", "args": ["@playwright/mcp@latest", "--cdp-endpoint", "http://127.0.0.1:9222"] } } }
```

While the port is open, any program on your machine can drive that browser. Run
`jobsmith browser stop` when you're done.

## Contributing

```bash
git config core.hooksPath .githooks   # blocks commits that look like personal data
uv run pytest
uv run ruff check
```

## License

MIT
