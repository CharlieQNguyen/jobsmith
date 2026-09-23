import json
import subprocess

from jobsmith import scaffold


def test_init_creates_repo_and_is_idempotent(tmp_path):
    r = scaffold.init(tmp_path, submodule=False)
    assert "CLAUDE.md" in r.created and ".claude/settings.json" in r.created
    assert (tmp_path / ".git").is_dir()
    settings = json.loads((tmp_path / ".claude/settings.json").read_text())
    assert settings["env"]["JOBSMITH_DATA"] == str(tmp_path.resolve())
    assert "tools/jobsmith/scripts/sync.sh" in settings["hooks"]["SessionStart"][0]["hooks"][0]["command"]
    assert (tmp_path / ".githooks/post-merge").stat().st_mode & 0o111
    hooks_path = subprocess.run(
        ["git", "-C", str(tmp_path), "config", "core.hooksPath"], capture_output=True, text=True
    ).stdout.strip()
    assert hooks_path == ".githooks"

    again = scaffold.init(tmp_path, submodule=False)
    assert not again.created and not again.updated and not again.kept


def test_force_refreshes_wiring_but_never_data(tmp_path):
    scaffold.init(tmp_path, submodule=False)
    (tmp_path / ".mcp.json").write_text("{}")
    (tmp_path / "profile/profile.yaml").write_text("name: Alex Example\n")
    (tmp_path / "CLAUDE.md").write_text("my notes\n")

    kept = scaffold.init(tmp_path, submodule=False)
    assert set(kept.kept) == {".mcp.json", "profile/profile.yaml", "CLAUDE.md"}

    forced = scaffold.init(tmp_path, force=True, submodule=False)
    assert forced.updated == [".mcp.json"]
    assert (tmp_path / "profile/profile.yaml").read_text() == "name: Alex Example\n"
    assert (tmp_path / "CLAUDE.md").read_text() == "my notes\n"
