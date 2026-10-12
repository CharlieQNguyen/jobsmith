# Fake ATS sign-in pages

One folder per ATS module in `src/jobsmith/ats/`, each with a `login.html` that mimics the real
site's form **structure** — the element types and attributes jobsmith's selectors rely on — and
nothing else: no copied markup, text, scripts or branding, and no real personal data.

Contract every `login.html` follows so `tests/test_ats.py` can drive it:

- The form may render late (real ATS pages are single-page apps); keep a short `setTimeout`.
- On submit, replace the form with `<output id="jobsmith-result">ok:USERNAME:PASSWORD_LENGTH</output>`.

## Fake applications

`workday/apply.html` is a fake multi-page Workday application that `tests/test_workday_apply.py`
drives the way the apply skill teaches, with `workday/resume.json` (fictional JSON Resume) as the
data. Same rules: reproduce the structure and behaviour the guidance relies on, invent the text,
copy nothing. On Submit it renders `<output id="jobsmith-result">` with JSON of every committed
value: `{"mode": "manual" | "autofill", "values": {"<Page>/<Field>": …}}`. Open
`apply.html#page=<Page title>` to start on one page when testing a single widget.

When the fixture reproduces a quirk, make the wrong technique fail in it too, and test both; a
quirk that the naive approach gets through untouched proves nothing.
