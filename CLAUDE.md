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

## Commands

- `uv run pytest` — tests
- `uv run jobsmith --data examples browser status` — is the CDP browser up?
- `uv run ruff check && uv run ruff format --check` — lint
- `uv run jobsmith --data examples apps list` — try the CLI against example data
