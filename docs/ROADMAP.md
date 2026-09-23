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
  `jobsmith-browser` MCP server plus the `/jobsmith:apply` and `/jobsmith:track` skills.
- **Developer skills** (`.claude/skills/`). `/ship` and `add-ats`.

## Next

1. **Import from LinkedIn.** Fill `profile/profile.yaml` and `resumes/base.json` from the user's
   own LinkedIn profile, read in the jobsmith Chrome after the user signs in. Read a handful of
   pages at a human pace, no crawling. Likely becomes a `/jobsmith:import-linkedin` skill.
2. **Render resumes to PDF.** JSON Resume → PDF (Typst or HTML→PDF). `/jobsmith:apply` needs a
   file to upload and currently asks the user for an existing PDF. Add a `tailor-resume` skill
   on top of it.
3. **First real Workday application** with `/jobsmith:apply`. Fix what breaks via `add-ats`.
4. **LinkedIn posting and profile skills.** Draft → user approval → post through the browser.
   Human-paced, low daily caps, stop on any CAPTCHA or unusual-activity page, never scrape.
5. **Follow-ups.** A `followups` skill that drafts messages for `apps due` items (never sends
   without approval), plus optionally a SessionStart summary of what's due.
6. **Cover letters.** Markdown drafts per application, rendered like resumes.
