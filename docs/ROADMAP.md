# Roadmap

Where jobsmith stands and what's next. Agents: read this at the start of a development session
and update it when something ships or plans change. Keep it free of personal data (it's public).

## Built

- **Data model and CLI.** Profile, applications (Markdown + YAML frontmatter, event history),
  accounts. `apps add/update/show/list/due`, `check`.
- **Credentials.** OS keychain via `keyring`. `creds new/copy/check` never print passwords.
- **Browser.** `browser start/stop/status` runs the user's Chrome with a per-user profile
  (`~/.local/share/jobsmith/chrome-profile`) and a DevTools port on 127.0.0.1:9222. `login`
  fills the sign-in form from the keychain, and the user runs it.
- **ATS support.** Declarative modules in `src/jobsmith/ats/` (Workday, generic), each with a
  fake sign-in page in `tests/fixtures/ats/` driven by headless-Chrome tests.
- **Data repos.** `jobsmith init` scaffolds a private data repo with jobsmith as a submodule.
  It's worktree-safe: the data dir is found from the cwd, the marketplace points at the main
  checkout, and `sync.sh` leaves the global install alone in worktrees.
- **Claude Code plugin** (`plugin/`, root `.claude-plugin/marketplace.json`). The
  `jobsmith-browser` MCP server plus the `/jobsmith:apply`, `/jobsmith:track` and
  `/jobsmith:import-linkedin` skills.
- **Import from LinkedIn.** `/jobsmith:import-linkedin` reads five pages of the user's own
  profile (main, experience, education, skills, certifications) in a browser they signed into,
  asks about gaps, then writes `profile/profile.yaml` and a schema-valid `resumes/base.json`.
- **Resume PDFs.** `jobsmith resume render` turns a JSON Resume into a one-page Letter PDF with
  headless Chrome: the "compact" layout in `src/jobsmith/resume.css` (single column, real text,
  standard headings for ATS parsing). Recent roles get a few highlights, older ones one line;
  `--full-roles`, `--bullets` and `--accent` adjust it, and it warns when content overflows.
- **Developer skills** (`.claude/skills/`). `/ship` and `add-ats`.
- **Landing.** `/jobsmith:land` lands a session's work: a squash-merged jobsmith PR first, then
  a data repo PR pointing at the squash commit, then a fast-forward of the main checkout.

## Next

The data repo is the source of truth for applications. Items 1–3 build on it.

1. **Import applications from a spreadsheet.** `jobsmith apps import FILE.csv`: map common
   headers (date, company, job title/role, link/website/url, notes, req/rec id), take a
   `--date-format` (e.g. `%d-%m-%Y`), turn LinkedIn tracking URLs into `linkedin.com/jobs/view/<id>`,
   create each row as `applied` on its date with the note in the Markdown body (rows whose note
   says the user hasn't applied yet become `interested`), and be idempotent: skip a row whose
   company, role and URL already exist; disambiguate repeat company/role pairs by date. Print a
   summary and dry-run with `--dry-run`. The user exports the CSV (File → Download); don't scrape it.
2. **Inbox sweep via the Gmail connector.** A `/jobsmith:inbox` skill (no credentials in
   jobsmith: it uses Claude's Gmail connector). Search mail since the last sweep for ATS senders
   (greenhouse, lever, ashby, workday, icims, smartrecruiters, …) and application subjects
   (thank you for applying, unfortunately, next steps, interview, schedule). Match to
   applications by company, show a table of proposed updates (status, event, contact), apply only
   approved ones with `apps update`, and record the sweep time in the data repo. Read-only on
   mail. Afterwards, optionally offer to mark long-silent applications `ghosted` (show the count
   and threshold first).
3. **Follow-ups.** A `/jobsmith:followups` skill for `apps due` items and follow-up intentions in
   application notes: drafts each message as a **Gmail draft** for the user to review and send
   (never sends). Optionally a daily scheduled sweep + summary, and a SessionStart line for what's
   due.
4. **Tailor resumes.** A `tailor-resume` skill: posting → `resumes/YYYY-MM-<company>-<role>.json`
   (reorder, trim and rephrase highlights from `base.json`, never invent) → `resume render` →
   one page. Then `/jobsmith:apply` uses it.
5. **First real Workday application** with `/jobsmith:apply`. Fix what breaks via `add-ats`.
6. **LinkedIn posting and profile skills.** Draft → user approval → post through the browser.
   Human-paced, low daily caps, stop on any CAPTCHA or unusual-activity page, never scrape.
7. **Cover letters.** Markdown drafts per application, rendered like resumes.
8. **Validate resumes in `jobsmith check`.** It checks the profile, applications and accounts
   but not `resumes/*.json`. Validate against the JSON Resume schema (bundled, no network).
9. **Resume fonts offline.** The layout loads Source Sans 3 from Google Fonts at render time and
   falls back to Helvetica offline, which changes line breaks. Bundle the font files (OFL).
