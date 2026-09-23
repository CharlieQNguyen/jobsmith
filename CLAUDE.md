# jobsmith

Public, MIT-licensed Python tool (uv, src layout, Python ≥3.12). Users keep their data in a
separate private repo that includes this one as a submodule at `tools/jobsmith`.

## Rules

- **No personal data in this repo, ever.** Only fictional data in `examples/` (example.com
  emails, 555-01xx phone numbers). The `.githooks/pre-commit` hook enforces this — enable it with
  `git config core.hooksPath .githooks`.
- Passwords live only in the OS keychain (`jobsmith.credentials`). Never print, log, or write them
  to files. Claude does not type passwords into sites and does not run `jobsmith login` — the user
  runs it, then Claude drives the signed-in browser over CDP (`browser.py`).
- Data is plain files so humans and agents can edit it and diffs stay readable. Add fields to the
  pydantic models in `models.py` rather than inventing ad-hoc keys.

## Layout

- `models.py` / `store.py` — data file schemas and plain-file read/write
- `credentials.py` — OS keychain; `browser.py` — CDP Chrome + `fill_login`
- `ats/` — one declarative module per applicant tracking system, `REGISTRY` in `__init__.py`;
  fake sign-in pages in `tests/fixtures/ats/<name>/` (see the `add-ats` skill)
- `scaffold.py` — `jobsmith init`. Data repos *reference* `docs/data-repo-guide.md` and
  `scripts/sync.sh` rather than copying them, so improvements ship via the submodule. Change
  those files here, not in a data repo.
- `.claude-plugin/marketplace.json` + `plugin/` — the Claude Code plugin data repos enable
  (user-facing skills in `plugin/skills/`, `jobsmith-browser` MCP server). Developer skills stay
  in `.claude/skills/`. Validate with `claude plugin validate .`

## Commands

- `uv run pytest` — tests (browser tests need Chrome; `-m "not browser"` skips them)
- `uv run jobsmith --data examples browser status` — is the CDP browser up?
- `uv run ruff check && uv run ruff format --check` — lint
- `uv run jobsmith --data examples apps list` — try the CLI against example data

Ship changes with `/ship` — it handles the jobsmith-then-data-repo push order.
