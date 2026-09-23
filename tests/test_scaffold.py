import json
import subprocess

from jobsmith import scaffold


def test_init_creates_repo_and_is_idempotent(tmp_path):
    r = scaffold.init(tmp_path, submodule=False)
    assert "CLAUDE.md" in r.created and ".claude/settings.json" in r.created
    assert (tmp_path / ".git").is_dir()
    settings = json.loads((tmp_path / ".claude/settings.json").read_text())
    assert "env" not in settings  # data dir is found from cwd, so worktrees use their own files
    assert "tools/jobsmith/scripts/sync.sh" in settings["hooks"]["SessionStart"][0]["hooks"][0]["command"]
    market = settings["extraKnownMarketplaces"]["jobsmith"]["source"]
    assert market == {"source": "directory", "path": str(tmp_path.resolve() / "tools/jobsmith")}
    assert settings["enabledPlugins"] == {"jobsmith@jobsmith": True}
    assert (tmp_path / ".githooks/post-merge").stat().st_mode & 0o111
    hooks_path = subprocess.run(
        ["git", "-C", str(tmp_path), "config", "core.hooksPath"], capture_output=True, text=True
    ).stdout.strip()
    assert hooks_path == ".githooks"

    again = scaffold.init(tmp_path, submodule=False)
    assert not again.created and not again.updated and not again.kept


def test_force_refreshes_wiring_but_never_data(tmp_path):
    scaffold.init(tmp_path, submodule=False)
    (tmp_path / ".gitignore").write_text("mine\n")
    (tmp_path / "profile/profile.yaml").write_text("name: Alex Example\n")
    (tmp_path / "CLAUDE.md").write_text("my notes\n")

    kept = scaffold.init(tmp_path, submodule=False)
    assert set(kept.kept) == {".gitignore", "profile/profile.yaml", "CLAUDE.md"}

    forced = scaffold.init(tmp_path, force=True, submodule=False)
    assert forced.updated == [".gitignore"]
    assert (tmp_path / "profile/profile.yaml").read_text() == "name: Alex Example\n"
    assert (tmp_path / "CLAUDE.md").read_text() == "my notes\n"


def test_force_removes_unmodified_obsolete_wiring(tmp_path):
    scaffold.init(tmp_path, submodule=False)
    (tmp_path / ".mcp.json").write_text(scaffold._OBSOLETE[".mcp.json"])
    assert ".mcp.json" not in scaffold.init(tmp_path, submodule=False).removed
    assert scaffold.init(tmp_path, force=True, submodule=False).removed == [".mcp.json"]

    (tmp_path / ".mcp.json").write_text('{"mcpServers": {"mine": {}}}')
    assert scaffold.init(tmp_path, force=True, submodule=False).removed == []
    assert (tmp_path / ".mcp.json").exists()


def test_marketplace_points_at_main_checkout_from_a_worktree(tmp_path):
    main = tmp_path / "main"
    scaffold.init(main, submodule=False)
    git = ["git", "-C", str(main), "-c", "user.name=t", "-c", "user.email=t@example.com"]
    subprocess.run([*git, "add", "-A"], check=True)
    subprocess.run([*git, "commit", "-qm", "init"], check=True)
    wt = tmp_path / "wt"
    subprocess.run([*git, "worktree", "add", "-q", str(wt)], check=True)

    scaffold.init(wt, force=True, submodule=False)
    settings = json.loads((wt / ".claude/settings.json").read_text())
    path = settings["extraKnownMarketplaces"]["jobsmith"]["source"]["path"]
    assert path == str(main.resolve() / "tools/jobsmith")
