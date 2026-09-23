from datetime import date
from pathlib import Path

from jobsmith import credentials, store
from jobsmith.models import Application, Status

EXAMPLES = Path(__file__).parent.parent / "examples"


def test_examples_load():
    assert store.load_profile(EXAMPLES).name == "Alex Example"
    apps = store.load_applications(EXAMPLES)
    acme = apps["acme-backend-engineer"]
    assert acme.status is Status.APPLIED
    assert acme.notes.startswith("Referred by")


def test_round_trip(tmp_path):
    app = Application(
        company="Globex",
        role="Platform Engineer",
        status=Status.INTERVIEWING,
        next_followup=date(2026, 10, 1),
        notes="Second round scheduled.",
    )
    path = store.write_application(tmp_path, app)
    assert path.name == "globex-platform-engineer.md"
    assert store.read_application(path) == app


def test_followup_due():
    app = Application(company="A", role="B", status=Status.APPLIED, next_followup=date(2026, 9, 1))
    assert app.followup_due(date(2026, 9, 1))
    assert not app.followup_due(date(2026, 8, 31))
    app.status = Status.REJECTED
    assert not app.followup_due(date(2026, 9, 2))


def test_generate_password_meets_common_rules():
    for _ in range(50):
        pw = credentials.generate_password()
        assert len(pw) == 24
        assert any(c.isupper() for c in pw) and any(c.islower() for c in pw)
        assert any(c.isdigit() for c in pw) and any(not c.isalnum() for c in pw)


def test_accounts(tmp_path):
    from jobsmith.models import Account

    assert store.find_account(tmp_path, "acme.wd5.myworkdayjobs.com") is None
    a = Account(host="acme.wd5.myworkdayjobs.com", username="alex@example.com", created=date(2026, 9, 1))
    store.upsert_account(tmp_path, a)
    a.login_url = "https://acme.wd5.myworkdayjobs.com/en-US/careers/login"
    store.upsert_account(tmp_path, a)
    assert store.load_accounts(tmp_path) == [a]
    assert store.find_account(tmp_path, "ACME.wd5.myworkdayjobs.com") == a

    store.upsert_account(tmp_path, a.model_copy(update={"username": "other@example.com"}))
    assert store.find_account(tmp_path, a.host) is None  # ambiguous without a username
    assert store.find_account(tmp_path, a.host, "other@example.com").username == "other@example.com"
