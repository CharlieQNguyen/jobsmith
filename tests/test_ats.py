from pathlib import Path

import pytest

from jobsmith import ats, browser, credentials

FIXTURES = Path(__file__).parent / "fixtures" / "ats"
ALL = (*ats.REGISTRY, ats.GENERIC)


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        ("acme.wd5.myworkdayjobs.com", "workday"),
        ("ACME.WD1.MYWORKDAYJOBS.COM", "workday"),
        ("wd3.myworkdaysite.com", "workday"),
        ("careers.example.com", "generic"),
    ],
)
def test_for_host(host, expected):
    assert ats.for_host(host).name == expected


@pytest.mark.parametrize("site", ALL, ids=lambda a: a.name)
def test_every_ats_has_a_fixture(site):
    assert (FIXTURES / site.name / "login.html").is_file(), f"add tests/fixtures/ats/{site.name}/login.html"


@pytest.fixture(scope="module")
def page():
    if not Path(browser.CHROME).exists():
        pytest.skip("Google Chrome not installed")
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        b = pw.chromium.launch(channel="chrome", headless=True)
        yield b.new_page()
        b.close()


@pytest.mark.browser
@pytest.mark.parametrize("site", ALL, ids=lambda a: a.name)
def test_fill_login_against_fixture(page, site):
    page.goto((FIXTURES / site.name / "login.html").as_uri())
    password = credentials.generate_password()
    status = browser.fill_login(page, site, "alex@example.com", password, timeout_ms=5_000)
    assert status == "Signed in."
    assert page.locator("#jobsmith-result").inner_text() == f"ok:alex@example.com:{len(password)}"
