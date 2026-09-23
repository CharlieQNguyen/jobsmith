from datetime import date, timedelta

import pytest
from typer.testing import CliRunner

from jobsmith import store
from jobsmith.cli import app
from jobsmith.models import Status

runner = CliRunner()
TODAY = date.today()


def run(tmp_path, *args):
    result = runner.invoke(app, [*args, "--data", str(tmp_path)])
    return result.exit_code, result.output.strip()


def test_parse_date():
    d = date(2026, 9, 23)
    assert store.parse_date("today", d) == d
    assert store.parse_date("+3d", d) == date(2026, 9, 26)
    assert store.parse_date("+2W", d) == date(2026, 10, 7)
    assert store.parse_date("2026-10-01", d) == date(2026, 10, 1)
    with pytest.raises(ValueError):
        store.parse_date("next tuesday", d)


def test_add_detects_ats_and_refuses_duplicates(tmp_path):
    code, out = run(
        tmp_path, "apps", "add", "--company", "Acme Corp", "--role", "Backend Engineer",
        "--url", "https://acme.wd5.myworkdayjobs.com/en-US/careers/job/X_R-1",
    )  # fmt: skip
    assert (code, out) == (0, "acme-corp-backend-engineer")
    a = store.read_application(tmp_path / "applications" / f"{out}.md")
    assert a.ats == "workday" and a.status is Status.INTERESTED
    assert [e.what for e in a.events] == ["Started tracking"]

    code, _ = run(tmp_path, "apps", "add", "--company", "Acme Corp", "--role", "Backend Engineer")
    assert code == 1


def test_update_flow(tmp_path):
    run(tmp_path, "apps", "add", "--company", "Globex", "--role", "Platform Engineer")
    code, out = run(tmp_path, "apps", "update", "globex", "--status", "applied", "--followup", "+7d")
    assert code == 0 and out.startswith("globex-platform-engineer: applied")
    a = store.read_application(tmp_path / "applications" / "globex-platform-engineer.md")
    assert a.applied_on == TODAY
    assert a.next_followup == TODAY + timedelta(days=7)
    assert a.events[-1].what == "Status: interested → applied"

    run(
        tmp_path, "apps", "update", "platform", "--event", "Phone screen with recruiter", "--on", "2026-10-02"
    )
    run(tmp_path, "apps", "update", "globex", "--status", "rejected")
    a = store.read_application(tmp_path / "applications" / "globex-platform-engineer.md")
    assert a.status is Status.REJECTED and a.next_followup is None
    assert [e.what for e in a.events][-2:] == ["Phone screen with recruiter", "Status: applied → rejected"]


def test_update_keeps_notes(tmp_path):
    run(tmp_path, "apps", "add", "--company", "Initech", "--role", "SRE")
    path = tmp_path / "applications" / "initech-sre.md"
    path.write_text(path.read_text() + "\nReferred by a former teammate.\n")
    run(tmp_path, "apps", "update", "initech", "--followup", "+3d")
    assert "Referred by a former teammate." in path.read_text()


def test_resolve_ambiguous_and_missing(tmp_path):
    run(tmp_path, "apps", "add", "--company", "Acme", "--role", "Backend Engineer")
    run(tmp_path, "apps", "add", "--company", "Acme", "--role", "Data Engineer")
    code, out = run(tmp_path, "apps", "update", "acme", "--status", "applied")
    assert code == 1 and "Several" in out and "acme-backend-engineer" in out
    assert run(tmp_path, "apps", "update", "acme data", "--status", "applied")[0] == 0
    assert "No applications" in run(tmp_path, "apps", "show", "hooli")[1]
