"""`jobsmith init`: create or refresh a private data repo that uses jobsmith as a submodule.

Two kinds of files:

- SCAFFOLD — wiring owned by jobsmith (Claude Code settings, MCP config, git hooks, .gitignore).
  Created if missing; overwritten by `--force` so `jobsmith init --force .` picks up improvements.
  Anything that should evolve (the agent guide, the sync script) lives in the submodule and is
  *referenced* from here, so a submodule update is usually all that's needed.
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


def _settings(data_dir: Path) -> str:
    return json.dumps(
        {
            "env": {"JOBSMITH_DATA": str(data_dir)},
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


_MCP = json.dumps(
    {
        "mcpServers": {
            "jobsmith-browser": {
                "command": "npx",
                "args": ["@playwright/mcp@latest", "--cdp-endpoint", "http://127.0.0.1:9222"],
            }
        }
    },
    indent=2,
)

_GITIGNORE = """.DS_Store
.venv/
__pycache__/
# Browser profiles hold live session cookies — never commit them
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


def scaffold_files(data_dir: Path) -> dict[str, str]:
    return {
        ".claude/settings.json": _settings(data_dir) + "\n",
        ".mcp.json": _MCP + "\n",
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

    for rel, content in scaffold_files(root).items():
        _write(root, rel, content, overwrite=force, report=report)
    for rel, content in STARTER_FILES.items():
        _write(root, rel, content, overwrite=False, report=report)

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
