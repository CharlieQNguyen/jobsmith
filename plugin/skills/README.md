User-facing skills for people *using* jobsmith in a data repo live here, one folder per skill
(`<name>/SKILL.md`), invoked as `/jobsmith:<name>`.

Skills for *developing* jobsmith (`ship`, `add-ats`) live in `.claude/skills/` at the repo root
instead, so they load only when working on jobsmith itself.

Data repos install the plugin from this repo's GitHub marketplace. `hooks/session-start.sh` checks
at the start of each session that the `jobsmith` command is installed and that the data repo's
wiring matches it (`jobsmith init --check`).
