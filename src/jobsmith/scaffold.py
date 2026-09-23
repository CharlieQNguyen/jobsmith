"""`jobsmith init`: create or refresh a private data repo that uses jobsmith as a submodule.

Two kinds of files:

- SCAFFOLD — wiring owned by jobsmith (Claude Code settings, git hooks, .gitignore).
  Created if missing; overwritten by `--force` so `jobsmith init --force .` picks up improvements.
  Anything that should evolve (the agent guide, the sync script, the Claude Code plugin with its
  skills and MCP server) lives in the submodule and is *referenced* from here, so a submodule
  update is usually all that's needed. The plugin comes from a local-directory marketplace at
  the submodule, which Claude Code loads in place — no plugin update step.
- STARTER — the user's data (profile, accounts, CLAUDE.md with personal notes). Created if
  missing, never overwritten.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

JOBSMITH_URL = "https://github.com/CharlieQNguyen/jobsmith.git"
SUBMODULE_PATH = "tools/jobsmith"
MARKETPLACE = "jobsmith"
PLUGIN = f"jobsmith@{MARKETPLACE}"

_SYNC = f"{SUBMODULE_PATH}/scripts/sync.sh"

# Fresh clones without --recurse-submodules: check the submodule out first, then sync.
_SESSION_START = (
    'cd "$CLAUDE_PROJECT_DIR" && '
    f"{{ [ -f {SUBMODULE_PATH}/pyproject.toml ] || git submodule update --init --quiet; }} && "
    f"{_SYNC} 2>/dev/null || true"
)

_GIT_HOOK = f"""#!/usr/bin/env bash
cd "$(git rev-parse --show-toplevel)" && [ -x {_SYNC} ] && {_SYNC} >/dev/null || true
"""


def main_checkout(root: Path) -> Path:
    """The main working tree of the repo at `root`, even when `root` is a linked worktree.

    The plugin marketplace is registered once per user, so it must point at a checkout that
    outlives any worktree.
    """
    common = _git(root, "rev-parse", "--path-format=absolute", "--git-common-dir").stdout.strip()
    return Path(common).parent if common.endswith("/.git") else root


def _settings(main: Path) -> str:
    return json.dumps(
        {
            "extraKnownMarketplaces": {
                MARKETPLACE: {"source": {"source": "directory", "path": str(main / SUBMODULE_PATH)}}
            },
            "enabledPlugins": {PLUGIN: True},
            "hooks": {
                "SessionStart": [
                    {
                        "hooks": [
                            {
                                "type": "command",
                                "command": _SESSION_START,
                                "timeout": 120,
                                "statusMessage": "Syncing jobsmith",
                            }
                        ]
                    }
                ]
            },
        },
        indent=2,
    )


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
}

_GITIGNORE = """.DS_Store
.venv/
__pycache__/
# Old location of jobsmith's browser profile (now under ~/.local/share/jobsmith)
.browser-profiles/
"""

_CLAUDE_MD = f"""@{SUBMODULE_PATH}/docs/data-repo-guide.md

## Personal notes

<!-- Anything specific to you: target roles, companies to avoid, how you like cover letters
     written. jobsmith never overwrites this file. -->
"""

_PROFILE = """# Schema: tools/jobsmith/src/jobsmith/models.py (Profile)
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


def scaffold_files(main: Path) -> dict[str, str]:
    return {
        ".claude/settings.json": _settings(main) + "\n",
        ".gitignore": _GITIGNORE,
        ".githooks/post-merge": _GIT_HOOK,
        ".githooks/post-checkout": _GIT_HOOK,
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

EXECUTABLE = {".githooks/post-merge", ".githooks/post-checkout"}


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


def _write(root: Path, rel: str, content: str, *, overwrite: bool, report: Report) -> None:
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
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    if rel in EXECUTABLE:
        path.chmod(0o755)


def init(root: Path, *, force: bool = False, submodule: bool = True, url: str = JOBSMITH_URL) -> Report:
    root = root.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    report = Report()

    if _git(root, "rev-parse", "--show-toplevel").stdout.strip() != str(root):
        _git(root, "init", "-q")
        report.notes.append("initialized git repo")

    for rel, content in scaffold_files(main_checkout(root)).items():
        _write(root, rel, content, overwrite=force, report=report)
    for rel, content in STARTER_FILES.items():
        _write(root, rel, content, overwrite=False, report=report)
    for rel, old in _OBSOLETE.items():
        path = root / rel
        if not path.exists() or json.loads(path.read_text()) != json.loads(old):
            continue  # absent, or the user's own file
        if force:
            path.unlink()
            report.removed.append(rel)
        else:
            report.notes.append(f"{rel} is from an older jobsmith; `init --force` removes it")

    _git(root, "config", "core.hooksPath", ".githooks")
    _git(root, "config", "push.recurseSubmodules", "check")

    if submodule and not (root / SUBMODULE_PATH / "pyproject.toml").exists():
        added = _git(root, "submodule", "add", "-q", url, SUBMODULE_PATH)
        if added.returncode:
            report.notes.append(f"could not add submodule: {added.stderr.strip()}")
        else:
            report.notes.append(f"added {url} at {SUBMODULE_PATH}")

    sync = root / _SYNC
    if sync.exists():
        out = subprocess.run([str(sync)], capture_output=True, text=True, check=False).stdout.strip()
        if out:
            report.notes.append(json.loads(out)["systemMessage"])
    return report
