"""Drive the fake Workday application (tests/fixtures/ats/workday/apply.html) in headless Chrome
the way the apply skill teaches, and show that the techniques it warns against fail there."""

import json
from pathlib import Path

import pytest

from jobsmith import browser
from jobsmith.ats import workday

FIXTURE = Path(__file__).parent / "fixtures" / "ats" / "workday"
RESUME = json.loads((FIXTURE / "resume.json").read_text())

pytestmark = pytest.mark.browser


@pytest.fixture(scope="module")
def chrome():
    if not Path(browser.CHROME).exists():
        pytest.skip("Google Chrome not installed")
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        b = pw.chromium.launch(channel="chrome", headless=True)
        yield b
        b.close()


@pytest.fixture
def page(chrome):
    p = chrome.new_page()
    p.set_default_timeout(5_000)
    p.goto((FIXTURE / "apply.html").as_uri())
    yield p
    p.close()


@pytest.fixture
def resume_pdf(tmp_path):
    pdf = tmp_path / "Alex Example Resume.pdf"
    pdf.write_bytes(b"%PDF-1.4\n%%EOF\n")
    return pdf


def heading(page) -> str:
    return page.locator('[data-automation-id="pageHeader"]').inner_text()


def save_and_continue(page, expect: str) -> None:
    page.locator(workday.CLICK_FILTER).click()
    assert heading(page) == expect, page.locator('[data-automation-id="errorMessage"]').all_inner_texts()


def contact_fields(basics: dict) -> dict[str, str]:
    """The skill's step-1 table: form label → value from base.json basics."""
    first, last = basics["name"].rsplit(" ", 1)
    loc = basics["location"]
    lines = loc["address"].split("\n")
    return {
        "First Name": first,
        "Last Name": last,
        "Address Line 1": lines[0],
        "Address Line 2": lines[1] if len(lines) > 1 else "",
        "City": loc["city"],
        "Postal Code": loc["postalCode"],
        "Email Address": basics["email"],
        "Phone Number": basics["phone"].removeprefix("+1").strip(),
    }


def start_manually(page) -> None:
    page.locator(workday.APPLY).click()
    page.locator(workday.APPLY_MANUALLY).click()
    assert heading(page) == "My Information"


def fill_my_information(page) -> dict[str, str]:
    contact = contact_fields(RESUME["basics"])
    for label, value in contact.items():
        page.get_by_label(label, exact=True).fill(value)
    return {f"My Information/{k}": v for k, v in contact.items() if v}


def test_apply_manually_fills_from_base_json_and_uploads_the_resume(page, resume_pdf):
    start_manually(page)
    assert page.get_by_label("First Name", exact=True).input_value() == ""  # nothing prefilled
    expected = fill_my_information(page)
    save_and_continue(page, "My Experience")

    page.locator(workday.CLICK_FILTER).click()  # applying manually still needs the resume
    assert heading(page) == "My Experience"
    assert "Error: Upload a resume." in page.locator('[data-automation-id="errorMessage"]').all_inner_texts()
    page.locator(workday.RESUME_UPLOAD).set_input_files(resume_pdf)
    assert page.locator('[data-automation-id="file-upload-successful"]').inner_text() == resume_pdf.name
    save_and_continue(page, "Review")

    page.locator(workday.CLICK_FILTER).click()
    result = json.loads(page.locator("#jobsmith-result").inner_text())
    expected["My Experience/Resume/CV"] = resume_pdf.name
    assert result == {"mode": "manual", "values": expected}


def test_next_sits_under_the_click_filter(page):
    start_manually(page)
    with pytest.raises(Exception, match="intercepts pointer events"):
        page.get_by_role("button", name="Save and Continue").click(timeout=1_000)
    page.locator(workday.CLICK_FILTER).click()
    assert page.get_by_role("alert").inner_text().startswith("Errors Found")
