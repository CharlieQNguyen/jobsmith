---
name: add-ats
description: Add support for a new applicant tracking system (Greenhouse, Lever, iCIMS, SmartRecruiters, Taleo, …) or fix an existing one's selectors, with a fake local sign-in page and a headless-Chrome test. Use when a job site's login isn't recognised, `jobsmith login` fails on a new ATS, or the user asks to support a new ATS.
---

# Add or fix an ATS

Each ATS is a small declarative module in `src/jobsmith/ats/`, listed in `REGISTRY`
(`src/jobsmith/ats/__init__.py`). `jobsmith login` picks one by host via `ats.for_host()`; the
unmatched fallback is `generic`. Every ATS has a fake sign-in page in
`tests/fixtures/ats/<name>/login.html` that `tests/test_ats.py` drives in headless Chrome.
Read `src/jobsmith/ats/workday.py` and `tests/fixtures/ats/workday/login.html` first as the model.

## 1. Learn the real sign-in form without signing in

You need: the hostnames the ATS uses, and the attributes of its username field, password field
and submit control.

- Ask the user for a real posting or sign-in URL on that ATS if you don't have one.
- Open it read-only (in-app browser, or `jobsmith-browser` MCP tools if already running) and
  inspect the form: `read_page`, or JavaScript that lists `input`/`button` elements with their
  `type`, `name`, `id`, `autocomplete`, `aria-label` and any `data-*` attributes.
- Prefer stable hooks in this order: `data-*` test/automation ids → `autocomplete` → `name` →
  `type`. Avoid generated class names and positional selectors.
- Note quirks: late rendering, iframes, multi-step (username page → password page), overlays
  over the submit button, SSO-only sign-in.
- **Never** type into the real form, create an account or submit anything. If the page shows a
  CAPTCHA or bot check, stop and tell the user.

## 2. Write the module

`src/jobsmith/ats/<name>.py`:

```python
"""<ATS name>. <one line on how tenants/hosts work and any quirk>."""

from jobsmith.ats import ATS

<NAME> = ATS(
    name="<name>",                       # lowercase, matches the fixture folder
    host_patterns=("*.example-ats.com",),
    username_selectors=(...),            # most specific first
    password_selectors=(...),
    submit_selector=None,                # None = press Enter; set only if Enter doesn't submit
)
```

Import it in `ats/__init__.py` and add it to `REGISTRY`. Put more specific host patterns earlier.

If the ATS needs behaviour `ATS` can't express (iframe, two-step login), extend `ATS` with a
small optional field and handle it in `browser.fill_login`. Keep existing ATSes working, and
add a fixture that exercises the new path.

## 3. Build the fake page

`tests/fixtures/ats/<name>/login.html`, following `tests/fixtures/ats/README.md`:

- Reproduce the **structure** your selectors depend on (element types, attributes, late
  rendering, overlays, extra steps). Don't copy the vendor's markup, text, scripts, styles or logos.
- On submit, render `<output id="jobsmith-result">ok:${username}:${password.length}</output>`.
- No real names, emails or employer data.

## 4. Test

Add `host → name` cases to `test_for_host` in `tests/test_ats.py`, including one case that must
*not* match. The fixture and login tests pick up new `REGISTRY` entries automatically.

```bash
uv run pytest -q tests/test_ats.py
uv run ruff format . && uv run ruff check .
```

Browser tests need Google Chrome installed. They're marked `browser`; if one fails, open the
fixture in the in-app browser to watch it.

## 5. Verify on the real site (optional, user-driven)

If the user has an account there: they run `jobsmith creds new …` (if needed), then
`! jobsmith login <host>`. Report what happened. If it didn't sign in, compare the real page to
the fixture and go back to step 1. You never run `jobsmith login` yourself.

## 6. Finish

Add a line to the ATS list in `README.md` and suggest `/ship`.
