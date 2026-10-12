"""`jobsmith init`: create or refresh a private data repo wired up for jobsmith.

Two kinds of files:

- SCAFFOLD — wiring owned by jobsmith (Claude Code settings, the agent guide, .gitignore).
  Created if missing; overwritten by `--force` so `jobsmith init --force .` picks up improvements.
  The agent guide ships inside the package, so the copy written here always matches the installed
  CLI. The Claude Code plugin comes from jobsmith's GitHub marketplace; its SessionStart hook runs
  `jobsmith init --check` and says when this wiring is out of date.
- STARTER — the user's data (profile, accounts, CLAUDE.md with personal notes). Created if
  missing, never overwritten.

The data repo holds no copy of jobsmith itself: the CLI is a uv tool and the plugin is installed
by Claude Code, so a data repo is plain files that any checkout or worktree of it can use.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from importlib.resources import files
from pathlib import Path

from jobsmith import __version__

JOBSMITH_REPO = "CharlieQNguyen/jobsmith"
MARKETPLACE = "jobsmith"
PLUGIN = f"jobsmith@{MARKETPLACE}"
GUIDE = ".jobsmith/guide.md"
# The jobsmith version this data repo was last set up with. Its pin: `init --check` compares it
# with the installed CLI, and with the plugin's version, which ship separately.
VERSION = ".jobsmith/version"
UPGRADE = "uv tool upgrade jobsmith"


def _guide() -> str:
    return files("jobsmith").joinpath("data-repo-guide.md").read_text()


def _settings() -> str:
    return json.dumps(
        {
            "extraKnownMarketplaces": {MARKETPLACE: {"source": {"source": "github", "repo": JOBSMITH_REPO}}},
            "enabledPlugins": {PLUGIN: True},
        },
        indent=2,
    )


_OLD_SYNC = "tools/jobsmith/scripts/sync.sh"
_OLD_GIT_HOOK = f"""#!/usr/bin/env bash
cd "$(git rev-parse --show-toplevel)" && [ -x {_OLD_SYNC} ] && {_OLD_SYNC} >/dev/null || true
"""

# Wiring from earlier jobsmith versions, removed by `init --force` if unmodified.
_OBSOLETE: dict[str, str] = {
    ".mcp.json": json.dumps(
        {
            "mcpServers": {
                "jobsmith-browser": {
                    "command": "npx",
                    "args": ["@playwright/mcp@latest", "--cdp-endpoint", "http://127.0.0.1:9222"],
                }
            }
        },
        indent=2,
    ),
    ".githooks/post-merge": _OLD_GIT_HOOK,
    ".githooks/post-checkout": _OLD_GIT_HOOK,
}

# The guide's import line in CLAUDE.md from when jobsmith was a submodule of the data repo.
_OLD_GUIDE_IMPORT = "@tools/jobsmith/docs/data-repo-guide.md"

_GITIGNORE = """.DS_Store
.venv/
__pycache__/
# Claude Code session worktrees
.claude/worktrees/
# Old location of jobsmith's browser profile (now under ~/.local/share/jobsmith)
.browser-profiles/
"""

_CLAUDE_MD = f"""@{GUIDE}

## Personal notes

<!-- Anything specific to you: target roles, companies to avoid, how you like cover letters
     written. jobsmith never overwrites this file. -->
"""

_PROFILE = f"""# Schema: Profile in https://github.com/{JOBSMITH_REPO}/blob/main/src/jobsmith/models.py
name:
email:
phone:
location:
linkedin:
github:
website:
work_authorization:
requires_sponsorship:
standard_answers:
  how_did_you_hear:
  salary_expectation:
  willing_to_relocate:
"""


def scaffold_files() -> dict[str, str]:
    return {
        ".claude/settings.json": _settings() + "\n",
        GUIDE: _guide(),
        VERSION: __version__ + "\n",
        ".gitignore": _GITIGNORE,
    }


STARTER_FILES: dict[str, str] = {
    "CLAUDE.md": _CLAUDE_MD,
    "profile/profile.yaml": _PROFILE,
    "accounts.yaml": "[]\n",
    "resumes/.gitkeep": "",
    "cover-letters/.gitkeep": "",
    "applications/.gitkeep": "",
    "linkedin/posts/.gitkeep": "",
}


@dataclass
class Report:
    created: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    kept: list[str] = field(default_factory=list)
    """Existing files left alone (differ from the template, no --force, or user data)."""
    notes: list[str] = field(default_factory=list)


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=False)


def _same(rel: str, a: str, b: str) -> bool:
    return json.loads(a) == json.loads(b) if rel.endswith(".json") else a == b


def _write(root: Path, rel: str, content: str, *, overwrite: bool, dry_run: bool, report: Report) -> None:
    path = root / rel
    if path.exists():
        if path.read_text() == content:
            report.unchanged.append(rel)
            return
        if not overwrite:
            report.kept.append(rel)
            return
        report.updated.append(rel)
    else:
        report.created.append(rel)
    if dry_run:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def init(root: Path, *, force: bool = False, dry_run: bool = False) -> Report:
    """Create or refresh the data repo at `root`. With `dry_run`, report what would change."""
    root = root.expanduser().resolve()
    report = Report()

    if not dry_run:
        root.mkdir(parents=True, exist_ok=True)
        if _git(root, "rev-parse", "--show-toplevel").stdout.strip() != str(root):
            _git(root, "init", "-q")
            report.notes.append("initialized git repo")

    for rel, content in scaffold_files().items():
        _write(root, rel, content, overwrite=force, dry_run=dry_run, report=report)
    for rel, content in STARTER_FILES.items():
        _write(root, rel, content, overwrite=False, dry_run=dry_run, report=report)
    for rel, old in _OBSOLETE.items():
        path = root / rel
        if not path.exists() or not _same(rel, path.read_text(), old):
            continue  # absent, or the user's own file
        if force:
            if not dry_run:
                path.unlink()
            report.removed.append(rel)
        else:
            report.notes.append(f"{rel} is from an older jobsmith; `init --force` removes it")

    hooks = root / ".githooks"
    if not dry_run and hooks.is_dir() and not any(hooks.iterdir()):
        hooks.rmdir()
        if _git(root, "config", "core.hooksPath").stdout.strip() == ".githooks":
            _git(root, "config", "--unset", "core.hooksPath")

    claude_md = root / "CLAUDE.md"
    if claude_md.exists() and _OLD_GUIDE_IMPORT in claude_md.read_text():
        report.notes.append(f"CLAUDE.md imports the old guide: change `{_OLD_GUIDE_IMPORT}` to `@{GUIDE}`")
    return report


def stale(root: Path) -> list[str]:
    """What `init --force` would change in the data repo at `root`; empty when it is current."""
    r = init(root, force=True, dry_run=True)
    wiring = scaffold_files().keys()
    # A missing starter file is the user's business: they may have deleted it on purpose.
    return [*(p for p in [*r.created, *r.updated] if p in wiring), *r.removed, *r.notes]


def _parse(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def plugin_version(plugin_root: Path) -> str | None:
    try:
        return json.loads((plugin_root / ".claude-plugin/plugin.json").read_text()).get("version")
    except (OSError, ValueError):
        return None


def check(root: Path, plugin_root: Path | None = None) -> list[str]:
    """One line for each thing out of step: the plugin and the CLI, the pin and the CLI, and
    the wiring. Empty when the data repo at `root` is current."""
    lines = []
    if plugin_root is not None and (plugin := plugin_version(plugin_root)) != __version__:
        lines.append(
            f"the plugin is {plugin or 'unversioned'} and the CLI is {__version__}. "
            f"Run `{UPGRADE}` and `/plugin marketplace update {MARKETPLACE}`, then restart the session."
        )
    pin_file = root.expanduser().resolve() / VERSION
    pin = pin_file.read_text().strip() if pin_file.exists() else None
    if pin and pin != __version__:
        try:
            behind = _parse(__version__) < _parse(pin)
        except ValueError:
            behind = False
        fix = f"`{UPGRADE}`" if behind else "`jobsmith init --force .`, then commit"
        lines.append(f"this data repo is set up for jobsmith {pin} and the CLI is {__version__}. Run {fix}.")
    if wiring := [p for p in stale(root) if p != VERSION]:
        lines.append(
            f"this data repo's wiring is out of date ({', '.join(wiring)}). Run `jobsmith init --force .`"
        )
    return [f"jobsmith: {line}" for line in lines]
