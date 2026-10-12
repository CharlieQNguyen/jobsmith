import json
import subprocess

from jobsmith import scaffold


def test_init_creates_repo_and_is_idempotent(tmp_path):
    r = scaffold.init(tmp_path)
    assert "CLAUDE.md" in r.created and ".claude/settings.json" in r.created
    assert (tmp_path / ".git").is_dir()
    settings = json.loads((tmp_path / ".claude/settings.json").read_text())
    assert "env" not in settings  # data dir is found from cwd, so worktrees use their own files
    assert "hooks" not in settings  # the plugin brings its own
    market = settings["extraKnownMarketplaces"]["jobsmith"]["source"]
    assert market == {"source": "github", "repo": "CharlieQNguyen/jobsmith"}
    assert settings["enabledPlugins"] == {"jobsmith@jobsmith": True}
    assert (tmp_path / "CLAUDE.md").read_text().startswith("@.jobsmith/guide.md\n")
    assert "# jobsmith data repo" in (tmp_path / ".jobsmith/guide.md").read_text()
    assert not (tmp_path / ".githooks").exists() and not (tmp_path / "tools").exists()
    assert ".claude/worktrees/" in (tmp_path / ".gitignore").read_text()

    again = scaffold.init(tmp_path)
    assert not again.created and not again.updated and not again.kept
    assert scaffold.stale(tmp_path) == []


def test_force_refreshes_wiring_but_never_data(tmp_path):
    scaffold.init(tmp_path)
    (tmp_path / ".gitignore").write_text("mine\n")
    (tmp_path / "profile/profile.yaml").write_text("name: Alex Example\n")
    (tmp_path / "CLAUDE.md").write_text("my notes\n")

    kept = scaffold.init(tmp_path)
    assert set(kept.kept) == {".gitignore", "profile/profile.yaml", "CLAUDE.md"}

    forced = scaffold.init(tmp_path, force=True)
    assert forced.updated == [".gitignore"]
    assert (tmp_path / "profile/profile.yaml").read_text() == "name: Alex Example\n"
    assert (tmp_path / "CLAUDE.md").read_text() == "my notes\n"


def test_force_removes_unmodified_obsolete_wiring(tmp_path):
    scaffold.init(tmp_path)
    (tmp_path / ".mcp.json").write_text(scaffold._OBSOLETE[".mcp.json"])
    assert ".mcp.json" not in scaffold.init(tmp_path).removed
    assert scaffold.init(tmp_path, force=True).removed == [".mcp.json"]

    (tmp_path / ".mcp.json").write_text('{"mcpServers": {"mine": {}}}')
    assert scaffold.init(tmp_path, force=True).removed == []
    assert (tmp_path / ".mcp.json").exists()


def test_check_reports_stale_wiring_and_changes_nothing(tmp_path):
    scaffold.init(tmp_path)
    (tmp_path / ".jobsmith/guide.md").write_text("an older guide\n")
    (tmp_path / "linkedin/posts/.gitkeep").unlink()  # starter files are the user's to delete

    before = (tmp_path / ".jobsmith/guide.md").read_text()
    assert scaffold.stale(tmp_path) == [".jobsmith/guide.md"]
    assert (tmp_path / ".jobsmith/guide.md").read_text() == before


def test_force_migrates_a_submodule_era_data_repo(tmp_path):
    scaffold.init(tmp_path)
    git = ["git", "-C", str(tmp_path)]
    (tmp_path / ".githooks").mkdir()
    for hook in (".githooks/post-merge", ".githooks/post-checkout"):
        (tmp_path / hook).write_text(scaffold._OLD_GIT_HOOK)
    subprocess.run([*git, "config", "core.hooksPath", ".githooks"], check=True)
    (tmp_path / "CLAUDE.md").write_text("@tools/jobsmith/docs/data-repo-guide.md\n\nmy notes\n")

    assert any("CLAUDE.md imports the old guide" in c for c in scaffold.stale(tmp_path))
    r = scaffold.init(tmp_path, force=True)
    assert sorted(r.removed) == [".githooks/post-checkout", ".githooks/post-merge"]
    assert not (tmp_path / ".githooks").exists()
    hooks_path = subprocess.run([*git, "config", "core.hooksPath"], capture_output=True, text=True)
    assert hooks_path.stdout.strip() == ""
    assert (tmp_path / "CLAUDE.md").read_text().endswith("my notes\n")  # never rewritten


def _plugin(tmp_path, version):
    root = tmp_path / "plugin"
    (root / ".claude-plugin").mkdir(parents=True)
    (root / ".claude-plugin/plugin.json").write_text(json.dumps({"name": "jobsmith", "version": version}))
    return root


def test_one_version_across_the_package_and_the_plugin():
    import tomllib
    from pathlib import Path

    from jobsmith import __version__

    repo = Path(__file__).parent.parent
    pyproject = tomllib.loads((repo / "pyproject.toml").read_text())["project"]["version"]
    assert __version__ == pyproject == scaffold.plugin_version(repo)


def test_init_pins_the_version_and_check_is_quiet_when_all_agree(tmp_path):
    from jobsmith import __version__

    scaffold.init(tmp_path)
    assert (tmp_path / ".jobsmith/version").read_text() == __version__ + "\n"
    assert scaffold.check(tmp_path, _plugin(tmp_path, __version__)) == []


def test_check_names_the_side_to_update(tmp_path):
    from jobsmith import __version__

    scaffold.init(tmp_path)
    (plugin_line,) = scaffold.check(tmp_path, _plugin(tmp_path, "999.0.0"))
    assert "the plugin is 999.0.0" in plugin_line and "editable install" in plugin_line

    (tmp_path / ".jobsmith/version").write_text("999.0.0\n")  # set up by a newer jobsmith
    (ahead,) = scaffold.check(tmp_path)
    assert f"set up for jobsmith 999.0.0 and the CLI is {__version__}" in ahead
    assert "/plugin marketplace update jobsmith" in ahead

    (tmp_path / ".jobsmith/version").write_text("0.0.1\n")  # set up by an older jobsmith
    (behind,) = scaffold.check(tmp_path)
    assert "jobsmith init --force ." in behind


def _hook_env(tmp_path, *, editable=False):
    """A jobsmith shim on PATH, a fake uv that records installs, and a throwaway HOME, so the
    hook can never touch the real install."""
    import os
    import sys

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    shim = bin_dir / "jobsmith"
    shim.write_text(f'#!/bin/sh\nexec "{sys.executable}" -c "from jobsmith import main; main()" "$@"\n')
    shim.chmod(0o755)
    tools = tmp_path / "tools"
    (tools / "jobsmith").mkdir(parents=True)
    receipt = 'requirements = [{ name = "jobsmith", editable = "/src/jobsmith" }]' if editable else ""
    (tools / "jobsmith/uv-receipt.toml").write_text(receipt + "\n")
    log = tmp_path / "uv.log"
    uv = bin_dir / "uv"
    uv.write_text(
        f'#!/bin/sh\nif [ "$1 $2" = "tool dir" ]; then echo "{tools}"; else echo "$@" >> "{log}"; fi\n'
    )
    uv.chmod(0o755)
    data = tmp_path / "data"
    scaffold.init(data)
    env = {"PATH": f"{bin_dir}:/usr/bin:/bin", "HOME": str(tmp_path), "CLAUDE_PROJECT_DIR": str(data)}
    return {**os.environ, **env}, data, log


def _run_hook(env, plugin_root):
    from pathlib import Path

    hook = Path(__file__).parent.parent / "plugin/hooks/session-start.sh"
    out = subprocess.run(
        [str(hook)], env={**env, "CLAUDE_PLUGIN_ROOT": str(plugin_root)}, capture_output=True, text=True
    )
    assert out.returncode == 0
    return json.loads(out.stdout)["systemMessage"] if out.stdout else None


def test_session_start_hook_is_quiet_when_all_agree(tmp_path):
    from pathlib import Path

    env, _, log = _hook_env(tmp_path)
    assert _run_hook(env, Path(__file__).parent.parent) is None
    assert not log.exists()


def test_session_start_hook_installs_the_cli_from_the_plugin(tmp_path):
    from jobsmith import __version__

    env, _, log = _hook_env(tmp_path)
    plugin = _plugin(tmp_path, "999.0.0")
    message = _run_hook(env, plugin)
    assert log.read_text().split() == ["tool", "install", "--reinstall", "--quiet", str(plugin)]
    assert f"installed the jobsmith command 999.0.0 to match the plugin (was {__version__})" in message


def test_session_start_hook_leaves_an_editable_install_and_says_so(tmp_path):
    env, data, log = _hook_env(tmp_path, editable=True)
    (data / ".jobsmith/version").write_text("0.0.1\n")
    message = _run_hook(env, _plugin(tmp_path, "999.0.0"))
    assert not log.exists()
    lines = message.split("\n")
    assert len(lines) == 2 and all(line.startswith("jobsmith: ") for line in lines)
    assert "editable install" in lines[0] and "set up for jobsmith 0.0.1" in lines[1]


def test_gitignore_keeps_other_tools_lines(tmp_path):
    scaffold.init(tmp_path)
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text(gitignore.read_text() + "/.sessions/\n/projects/\n")  # another tool's lines
    assert scaffold.stale(tmp_path) == []

    gitignore.write_text("/.sessions/\n.DS_Store\n")  # jobsmith's other lines are gone
    assert scaffold.stale(tmp_path) == [".gitignore"]
    scaffold.init(tmp_path, force=True)
    lines = gitignore.read_text().splitlines()
    assert lines[:2] == ["/.sessions/", ".DS_Store"]
    assert ".claude/worktrees/" in lines and lines.count(".DS_Store") == 1
    assert scaffold.stale(tmp_path) == []


def test_settings_keep_other_keys_and_lose_the_old_sync_hook(tmp_path):
    scaffold.init(tmp_path)
    path = tmp_path / ".claude/settings.json"
    old_sync = {"type": "command", "command": "cd x && tools/jobsmith/scripts/sync.sh || true"}
    mine = {"type": "command", "command": "echo mine"}
    path.write_text(
        json.dumps(
            {
                "permissions": {"allow": ["Bash(ls:*)"]},
                "extraKnownMarketplaces": {
                    "jobsmith": {"source": {"source": "directory", "path": "/old/tools/jobsmith"}},
                    "other": {"source": {"source": "github", "repo": "o/other"}},
                },
                "enabledPlugins": {"jobsmith@jobsmith": True, "other@other": True},
                "hooks": {"SessionStart": [{"hooks": [old_sync]}, {"hooks": [mine]}]},
            }
        )
    )
    assert scaffold.stale(tmp_path) == [".claude/settings.json"]
    scaffold.init(tmp_path, force=True)
    settings = json.loads(path.read_text())
    assert settings["permissions"] == {"allow": ["Bash(ls:*)"]}
    assert settings["extraKnownMarketplaces"]["jobsmith"]["source"] == {
        "source": "github",
        "repo": "CharlieQNguyen/jobsmith",
    }
    assert settings["extraKnownMarketplaces"]["other"] and settings["enabledPlugins"]["other@other"]
    assert settings["hooks"] == {"SessionStart": [{"hooks": [mine]}]}
    assert scaffold.stale(tmp_path) == []

    # Another tool's keys alone never make the wiring stale.
    path.write_text(json.dumps({**settings, "env": {"X": "1"}}))
    assert scaffold.stale(tmp_path) == []
