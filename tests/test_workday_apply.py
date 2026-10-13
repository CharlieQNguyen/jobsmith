"""Drive the fake Workday application (tests/fixtures/ats/workday/apply.html) in headless Chrome
the way the apply skill teaches, and show that the techniques it warns against fail there."""

import json
from datetime import date
from pathlib import Path
from urllib.parse import quote

import pytest
from playwright.sync_api import Error as PlaywrightError

from jobsmith import browser, textsafe
from jobsmith.ats import workday

FIXTURE = Path(__file__).parent / "fixtures" / "ats" / "workday"
RESUME = json.loads((FIXTURE / "resume.json").read_text())
# Answers that would come from the profile (work authorization, standard_answers).
PROFILE = {
    "authorized": "Yes",
    "sponsorship": "No",
    "how_did_you_hear": "Company Website",
    "employment_types": ["Full-time", "Contract"],
    "veteran_status": "I am not a protected veteran",
}
# JSON Resume studyType → Workday's degree names.
DEGREES = {"B.A.": "Bachelor of Arts (B.A)", "B.S.": "Bachelor of Science (B.S)"}
Q_AUTHORIZED = "Are you legally authorized to work in the country where this job is located?"
Q_SPONSORSHIP = "Will you now or in the future require sponsorship for an employment visa?"
Q_HEARD = "How did you hear about this position?"
Q_TYPES = "Which types of employment are you open to?"
DISABILITY_DECLINE = "I do not want to answer"

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
def open_app(chrome):
    """Open the fixture; with a page title, start there (applying manually)."""
    pages = []

    def opener(start_at: str | None = None):
        p = chrome.new_page()
        p.set_default_timeout(5_000)
        pages.append(p)
        url = (FIXTURE / "apply.html").as_uri() + (f"#page={quote(start_at)}" if start_at else "")
        p.goto(url)
        if start_at:
            assert heading(p) == start_at
        return p

    yield opener
    for p in pages:
        p.close()


@pytest.fixture
def resume_pdf(tmp_path):
    pdf = tmp_path / "Alex Example Resume.pdf"
    pdf.write_bytes(b"%PDF-1.4\n%%EOF\n")
    return pdf


def heading(page) -> str:
    return page.locator('[data-automation-id="pageHeader"]').inner_text()


def errors(page) -> list[str]:
    return page.locator('[data-automation-id="errorMessage"]').all_inner_texts()


def save_and_continue(page, expect: str) -> None:
    page.locator(workday.CLICK_FILTER).click()
    assert heading(page) == expect, errors(page)


def group(scope, name: str):
    return scope.get_by_role("group", name=name, exact=True)


def result(page) -> dict:
    page.locator(workday.CLICK_FILTER).click()
    return json.loads(page.locator("#jobsmith-result").inner_text())


# --- the whole application ---------------------------------------------------------------


def contact_fields(basics: dict) -> dict[str, str]:
    """The skill's step-1 table: text field label → value from base.json basics."""
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


def fill_my_information(page) -> dict:
    basics = RESUME["basics"]
    assert basics["location"]["countryCode"] == "US"
    workday.select_one(page, "United States of America", label="Country")
    contact = contact_fields(basics)
    for label, value in contact.items():
        page.get_by_label(label, exact=True).fill(value)
    workday.select_one(page, basics["location"]["region"], label="State")
    workday.select_one(page, "Mobile", label="Phone Device Type")
    workday.search_prompt(
        page.get_by_label("Country Phone Code"), "United States", "United States of America (+1)"
    )
    p = "My Information"
    return {
        f"{p}/Country": "United States of America",
        **{f"{p}/{k}": v for k, v in contact.items() if v},
        f"{p}/State": "Oregon",
        f"{p}/Phone Device Type": "Mobile",
        f"{p}/Country Phone Code": "United States of America (+1)",
    }


def month_year(iso: str) -> str:
    year, month = iso.split("-")[:2]
    return f"{month}/{year}"


def fill_my_experience(page, resume_pdf) -> dict:
    expected = {}
    section = group(page, "Work Experience")
    for n, job in enumerate(RESUME["work"], start=1):
        section.get_by_role("button", name="Add" if n == 1 else "Add Another", exact=True).click()
        g = group(page, f"Work Experience {n}")
        prefix = f"My Experience/Work Experience {n}"
        g.get_by_label("Job Title").fill(job["position"])
        g.get_by_label("Company").fill(job["name"])
        g.get_by_label("Location").fill(job["location"])
        if "endDate" not in job:
            g.get_by_label("I currently work here").check()
            expected[f"{prefix}/I currently work here"] = True
        workday.fill_date(group(g, "From"), month_year(job["startDate"]))
        if "endDate" in job:
            workday.fill_date(group(g, "To"), month_year(job["endDate"]))
            expected[f"{prefix}/To"] = month_year(job["endDate"])
        description = textsafe.sanitize(job["summary"], workday.WORKDAY.illegal_characters).text
        g.get_by_label("Role Description").fill(description)
        expected |= {
            f"{prefix}/Job Title": job["position"],
            f"{prefix}/Company": job["name"],
            f"{prefix}/Location": job["location"],
            f"{prefix}/From": month_year(job["startDate"]),
            f"{prefix}/Role Description": description,
        }

    school = RESUME["education"][0]
    group(page, "Education").get_by_role("button", name="Add", exact=True).click()
    g = group(page, "Education 1")
    g.get_by_label("School or University").fill(school["institution"])
    workday.select_one(g, DEGREES[school["studyType"]], label="Degree")
    # "Computer Science" isn't on the fixed list; the closest is.
    workday.search_prompt(g.get_by_label("Field of Study"), "Computer", "Computer and Information Sciences")
    workday.fill_date(group(g, "From"), school["startDate"])
    workday.fill_date(group(g, "To (Actual or Expected)"), school["endDate"])
    expected |= {
        "My Experience/Education 1/School or University": school["institution"],
        "My Experience/Education 1/Degree": "Bachelor of Arts (B.A)",
        "My Experience/Education 1/Field of Study": "Computer and Information Sciences",
        "My Experience/Education 1/From": "2015",
        "My Experience/Education 1/To (Actual or Expected)": "2019",
    }

    page.locator(workday.RESUME_UPLOAD).set_input_files(resume_pdf)
    expected["My Experience/Resume/CV"] = resume_pdf.name

    urls = [RESUME["basics"]["profiles"][0]["url"], RESUME["basics"]["url"]]
    websites = group(page, "Websites")
    for n, url in enumerate(urls, start=1):
        websites.get_by_role("button", name="Add" if n == 1 else "Add Another", exact=True).click()
        group(page, f"Websites {n}").get_by_label("URL").fill(url)
        expected[f"My Experience/Websites {n}/URL"] = url
    return expected


def fill_application_questions(page) -> dict:
    workday.select_one(group(page, Q_AUTHORIZED), PROFILE["authorized"])
    workday.select_one(group(page, Q_SPONSORSHIP), PROFILE["sponsorship"])
    workday.select_one(group(page, Q_HEARD), PROFILE["how_did_you_hear"])
    for kind in PROFILE["employment_types"]:
        workday.check_box(group(page, Q_TYPES).get_by_label(kind))
    p = "Application Questions"
    return {
        f"{p}/{Q_AUTHORIZED}": "Yes",
        f"{p}/{Q_SPONSORSHIP}": "No",
        f"{p}/{Q_HEARD}": "Company Website",
        f"{p}/{Q_TYPES}": ["Full-time", "Contract"],
    }


def fill_voluntary_disclosures(page) -> dict:
    workday.select_one(page, "Not declared", label="Gender")  # its decline option
    workday.select_one(page, "I do not wish to answer", label="Ethnicity")
    workday.select_one(page, PROFILE["veteran_status"], label="Veteran Status")  # no decline option
    page.get_by_label("I have read and consent to the terms and conditions").check()
    p = "Voluntary Disclosures"
    return {
        f"{p}/Gender": "Not declared",
        f"{p}/Ethnicity": "I do not wish to answer",
        f"{p}/Veteran Status": "I am not a protected veteran",
        f"{p}/I have read and consent to the terms and conditions": True,
    }


def fill_self_identify(page) -> dict:
    today = date.today().strftime("%m/%d/%Y")
    page.get_by_label("Name", exact=True).fill(RESUME["basics"]["name"])
    workday.fill_date(group(page, "Date"), today)
    workday.check_box(group(page, "Disability status").get_by_label(DISABILITY_DECLINE))
    return {
        "Self Identify/Name": "Alex Example",
        "Self Identify/Date": today,
        "Self Identify/Disability status": [DISABILITY_DECLINE],
    }


def test_apply_manually_and_fill_every_page_from_base_json(open_app, resume_pdf):
    page = open_app()
    page.locator(workday.APPLY).click()
    page.locator(workday.APPLY_MANUALLY).click()
    assert heading(page) == "My Information"
    assert page.get_by_label("First Name", exact=True).input_value() == ""  # nothing prefilled

    expected = fill_my_information(page)
    save_and_continue(page, "My Experience")
    expected |= fill_my_experience(page, resume_pdf)
    save_and_continue(page, "Application Questions")
    expected |= fill_application_questions(page)
    save_and_continue(page, "Voluntary Disclosures")
    expected |= fill_voluntary_disclosures(page)
    save_and_continue(page, "Self Identify")
    expected |= fill_self_identify(page)
    save_and_continue(page, "Review")

    assert result(page) == {"mode": "manual", "values": expected}


# --- one widget at a time: the wrong technique fails, the taught one works ----------------


def test_next_sits_under_the_click_filter(open_app):
    page = open_app("My Information")
    with pytest.raises(PlaywrightError, match="intercepts pointer events"):
        page.get_by_role("button", name="Save and Continue").click(timeout=1_000)
    page.locator(workday.CLICK_FILTER).click()
    assert page.get_by_role("alert").inner_text().startswith("Errors Found")


def test_the_resume_is_required_when_applying_manually(open_app, resume_pdf):
    page = open_app("My Experience")
    page.locator(workday.CLICK_FILTER).click()
    assert "Error: Upload a resume." in errors(page)
    page.locator(workday.RESUME_UPLOAD).set_input_files(resume_pdf)
    assert page.locator('[data-automation-id="file-upload-successful"]').inner_text() == resume_pdf.name


def self_identify_except_date(page) -> None:
    page.get_by_label("Name", exact=True).fill("Alex Example")
    workday.check_box(group(page, "Disability status").get_by_label(DISABILITY_DECLINE))


def test_date_spinbuttons_ignore_click_and_fill(open_app):
    page = open_app("Self Identify")
    self_identify_except_date(page)
    date_group = group(page, "Date")
    month = date_group.locator('[data-automation-id="dateSectionMonth-input"]')
    with pytest.raises(PlaywrightError, match="outside of the viewport"):
        month.click(timeout=1_000)
    month.fill("10")
    assert month.input_value() == ""
    assert date_group.locator('[data-automation-id="dateSectionMonth-display"]').inner_text() == "MM"
    page.locator(workday.CLICK_FILTER).click()
    assert heading(page) == "Self Identify"
    assert "Error: The field Date is required and must have a value." in errors(page)


def test_date_takes_focus_type_and_tab(open_app):
    page = open_app("Self Identify")
    self_identify_except_date(page)
    date_group = group(page, "Date")
    workday.fill_date(date_group, "10/12/2026")
    shown = [
        date_group.locator(f'[data-automation-id="dateSection{s}-display"]').inner_text()
        for s in ("Month", "Day", "Year")
    ]
    assert shown == ["10", "12", "2026"]
    assert date_group.evaluate("g => !g.contains(document.activeElement)")  # tabbed out
    save_and_continue(page, "Review")
    assert result(page)["values"]["Self Identify/Date"] == "10/12/2026"


def test_refilling_a_date_replaces_it(open_app):
    page = open_app("Self Identify")
    self_identify_except_date(page)
    date_group = group(page, "Date")
    workday.fill_date(date_group, "10/12/2026")
    workday.fill_date(date_group, "1/2/2027")  # unpadded, and over a full date
    shown = [
        date_group.locator(f'[data-automation-id="dateSection{s}-display"]').inner_text()
        for s in ("Month", "Day", "Year")
    ]
    assert shown == ["01", "02", "2027"]
    save_and_continue(page, "Review")
    assert result(page)["values"]["Self Identify/Date"] == "01/02/2027"


def test_a_date_that_does_not_fit_is_refused_before_typing(open_app):
    page = open_app("Self Identify")
    date_group = group(page, "Date")
    with pytest.raises(ValueError, match="doesn't fit"):
        workday.fill_date(date_group, "10/2026")  # this group has month, day and year
    month = date_group.locator('[data-automation-id="dateSectionMonth-input"]')
    assert month.input_value() == ""
    assert not date_group.evaluate("g => g.contains(document.activeElement)")


def test_select_one_is_a_button_and_a_listbox_not_a_select(open_app):
    page = open_app("My Information")
    button = page.get_by_role("button", name="Country Select One Required")
    with pytest.raises(PlaywrightError, match="not a <select> element"):
        button.select_option("Canada", timeout=1_000)
    workday.select_one(page, "Canada", label="Country")
    assert page.get_by_role("button", name="Country Canada Required").is_visible()
    assert page.get_by_role("listbox").count() == 0


def test_select_one_matches_the_whole_label(open_app):
    page = open_app("My Information")
    workday.select_one(page, "Oregon", label="State")
    assert page.get_by_role("button", name="State Oregon Required", exact=True).is_visible()
    assert page.get_by_role("button", name="Home State Select One", exact=True).is_visible()


def test_question_dropdowns_are_found_by_their_group(open_app):
    page = open_app("Application Questions")
    with pytest.raises(PlaywrightError, match="strict mode violation"):
        page.get_by_role("button", name="Select One Required").click(timeout=1_000)
    workday.select_one(group(page, Q_SPONSORSHIP), "No")
    assert group(page, Q_SPONSORSHIP).get_by_role("button", name="No Required").is_visible()
    assert (
        group(page, Q_AUTHORIZED).get_by_role("button", name="Select One Required", exact=True).is_visible()
    )
    workday.select_one(group(page, Q_HEARD), "Job Board")  # not "Other Job Board"
    assert group(page, Q_HEARD).get_by_role("button", name="Job Board Required", exact=True).is_visible()


def test_search_prompt_needs_enter_and_the_not_checked_option(open_app):
    page = open_app("My Information")
    field = page.get_by_label("Country Phone Code")
    field.press_sequentially("United States")
    assert page.get_by_role("option").count() == 0  # typing alone lists nothing
    page.locator(workday.CLICK_FILTER).click()
    assert "Error: The field Country Phone Code is required and must have a value." in errors(page)

    field.press("Enter")
    assert page.get_by_role("option", name="United States of America (+1)", exact=True).count() == 0
    assert page.get_by_role("option", name="United States of America (+1) not checked").count() == 1


def test_search_prompt_helper(open_app):
    page = open_app("My Information")
    workday.search_prompt(
        page.get_by_label("Country Phone Code"), "United States", "United States of America (+1)"
    )
    selected = page.get_by_role("button", name="United States of America (+1), press delete to clear value.")
    assert selected.is_visible()


def test_search_prompt_picks_from_its_own_list(open_app):
    # Lists open in the fields before and after the one being filled, with the same options, so
    # neither "the first list" nor "the last list" is its own.
    page = open_app("My Experience")
    education = group(page, "Education")
    education.get_by_role("button", name="Add", exact=True).click()
    for _ in range(2):
        education.get_by_role("button", name="Add Another", exact=True).click()
    for other in ("Education 1", "Education 3"):
        field = group(page, other).get_by_label("Field of Study")
        field.fill("Computer")
        field.press("Enter")
    workday.search_prompt(
        group(page, "Education 2").get_by_label("Field of Study"), "Computer", "Computer Engineering"
    )
    selected = "Computer Engineering, press delete to clear value."
    assert group(page, "Education 2").get_by_role("button", name=selected).is_visible()
    for other in ("Education 1", "Education 3"):
        assert group(page, other).get_by_role("button", name=selected).count() == 0
        assert group(page, other).get_by_role("listbox").count() == 1  # open throughout


def test_field_of_study_is_a_fixed_list(open_app):
    page = open_app("My Experience")
    group(page, "Education").get_by_role("button", name="Add", exact=True).click()
    field = group(page, "Education 1").get_by_label("Field of Study")
    field.fill("Computer Science")
    field.press("Enter")
    assert page.get_by_role("listbox").inner_text() == "No Items."
    workday.search_prompt(field, "Computer", "Computer and Information Sciences")
    selected = "Computer and Information Sciences, press delete to clear value."
    assert page.get_by_role("button", name=selected).is_visible()


def test_checkbox_grids_need_force(open_app):
    page = open_app("Application Questions")
    box = group(page, Q_TYPES).get_by_label("Full-time")
    with pytest.raises(PlaywrightError, match="intercepts pointer events"):
        box.check(timeout=1_000)
    assert not box.is_checked()
    workday.check_box(box)
    assert box.is_checked()


def test_illegal_characters_are_rejected_until_sanitized(open_app):
    page = open_app("My Experience")
    group(page, "Work Experience").get_by_role("button", name="Add", exact=True).click()
    description = group(page, "Work Experience 1").get_by_label("Role Description")
    raw = RESUME["work"][0]["summary"]
    description.fill(raw)
    description.blur()
    assert "Error: Contains illegal characters" in errors(page)
    clean = textsafe.sanitize(raw, workday.WORKDAY.illegal_characters)
    assert clean.changed
    description.fill(clean.text)
    description.blur()
    assert "Error: Contains illegal characters" not in errors(page)


def test_repeating_groups_add_then_add_another(open_app):
    page = open_app("My Experience")
    websites = group(page, "Websites")
    websites.get_by_role("button", name="Add", exact=True).click()
    assert websites.get_by_role("button", name="Add Another", exact=True).is_visible()
    assert group(page, "Websites 1").get_by_label("URL").is_visible()

    group(page, "Work Experience").get_by_role("button", name="Add", exact=True).click()
    job = group(page, "Work Experience 1")
    assert group(job, "To").is_visible()
    job.get_by_label("I currently work here").check()
    assert not group(job, "To").is_visible()
