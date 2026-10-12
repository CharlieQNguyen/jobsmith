User-facing skills for people *using* jobsmith in a data repo live here, one folder per skill
(`<name>/SKILL.md`), invoked as `/jobsmith:<name>`.

Skills for *developing* jobsmith (`ship`, `add-ats`) live in `.claude/skills/` at the repo root
instead, so they load only when working on jobsmith itself.

Data repos install the plugin from this repo's GitHub marketplace. The plugin is the whole repo,
and `plugin/hooks/session-start.sh` installs the `jobsmith` command from it whenever the versions
differ, then reports anything else out of step (`jobsmith init --check`).
