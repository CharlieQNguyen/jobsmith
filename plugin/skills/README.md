User-facing skills for people *using* jobsmith in a data repo live here, one folder per skill
(`<name>/SKILL.md`), invoked as `/jobsmith:<name>`.

Skills for *developing* jobsmith (`ship`, `add-ats`) live in `.claude/skills/` at the repo root
instead, so they load only when working on jobsmith itself.

The plugin is served from the data repo's `tools/jobsmith` submodule through a local-directory
marketplace, so it loads in place: skills always match the pinned CLI, with no plugin update step.
