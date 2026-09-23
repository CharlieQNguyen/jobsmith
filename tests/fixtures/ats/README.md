# Fake ATS sign-in pages

One folder per ATS module in `src/jobsmith/ats/`, each with a `login.html` that mimics the real
site's form **structure** — the element types and attributes jobsmith's selectors rely on — and
nothing else: no copied markup, text, scripts or branding, and no real personal data.

Contract every `login.html` follows so `tests/test_ats.py` can drive it:

- The form may render late (real ATS pages are single-page apps); keep a short `setTimeout`.
- On submit, replace the form with `<output id="jobsmith-result">ok:USERNAME:PASSWORD_LENGTH</output>`.
