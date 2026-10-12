"""Workday. Each employer runs its own tenant (acme.wd5.myworkdayjobs.com) with its own accounts,
but all tenants share the same `data-automation-id` attributes.

Applying: choose *Apply Manually* (`APPLY_MANUALLY`), never *Autofill with Resume*. Workday's
resume parsing mangles titles, companies and dates, so jobsmith fills every field from
`resumes/base.json` and still uploads the resume PDF (`RESUME_UPLOAD`) in My Experience. The
apply skill (`plugin/skills/apply/SKILL.md`) carries the page-by-page guidance;
`tests/fixtures/ats/workday/apply.html` is a fake application that the tests drive.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from jobsmith.ats import ATS

if TYPE_CHECKING:
    from playwright.sync_api import Locator, Page

WORKDAY = ATS(
    name="workday",
    host_patterns=("*.myworkdayjobs.com", "*.myworkdaysite.com", "*.myworkday.com"),
    username_selectors=('[data-automation-id="email"]', 'input[type="email"]'),
    password_selectors=('[data-automation-id="password"]', 'input[type="password"]'),
    # A transparent click_filter overlay covers Workday's submit button; Enter avoids it.
    submit_selector=None,
    # Text fields answer "Error: Contains illegal characters" for any of these.
    illegal_characters='<>[]"{}\\',
)

APPLY = '[data-automation-id="adventureButton"]'
"""The posting's Apply button. It opens a dialog offering the ways to start."""
APPLY_MANUALLY = '[data-automation-id="applyManually"]'
AUTOFILL_WITH_RESUME = '[data-automation-id="autofillWithResume"]'
"""Not used: its parsing mangles the data. Listed so nothing picks it by accident."""
RESUME_UPLOAD = '[data-automation-id="file-upload-input-ref"]'
"""The Resume/CV file input in My Experience; set the PDF on it with set_input_files."""
CLICK_FILTER = '[data-automation-id="click_filter"]'
"""Transparent overlay over the page's Next and Submit buttons. Click it, not the button."""

# Widgets. Each helper is the technique the apply skill teaches, for driving the signed-in Chrome
# with Playwright over CDP (the skill's fallback); the skill gives the same steps for MCP tools.
# `scope` is the page or a group within it, e.g. page.get_by_role("group", name="Work Experience 1").

DATE_FIRST_SECTION = (
    '[data-automation-id="dateSectionMonth-input"], '
    '[data-automation-id="dateSectionDay-input"], '
    '[data-automation-id="dateSectionYear-input"]'
)


def fill_date(group: Locator, value: str) -> None:
    """Type `value` ("MM/YYYY", "YYYY" or "MM/DD/YYYY") into a date group such as "From".

    The spinbuttons sit outside the viewport, so click() never lands, and they keep their own
    digits, so fill() doesn't stick. Focus the first section, type the digits (each section moves
    on by itself) and Tab out, which commits the date.
    """
    group.locator(DATE_FIRST_SECTION).first.focus()
    group.page.keyboard.type(value.replace("/", ""))
    group.page.keyboard.press("Tab")


def select_one(scope: Page | Locator, option: str, label: str = "") -> None:
    """Pick `option` in a "Select One" dropdown: a button named "<label> Select One Required"
    that opens a listbox. For an application question, pass the question's group as `scope` and
    no label: every question's button is named just "Select One Required"."""
    page = getattr(scope, "page", scope)  # a Locator knows its page; a Page is one
    scope.get_by_role("button", name=f"{label} Select One".strip()).click()
    page.get_by_role("listbox").get_by_role("option", name=option, exact=True).click()


def search_prompt(field: Locator, query: str, option: str) -> None:
    """Choose `option` in a search prompt (Field of Study, Country Phone Code): type, press Enter,
    then click the option named "<option> not checked". It then shows as
    "<option>, press delete to clear value."."""
    field.fill(query)
    field.press("Enter")
    field.page.get_by_role("option", name=f"{option} not checked", exact=True).click()


def check_box(box: Locator) -> None:
    """Tick a box in a checkbox grid. A styled panel over each box takes the pointer, so a normal
    check() waits forever; force it."""
    box.check(force=True)
