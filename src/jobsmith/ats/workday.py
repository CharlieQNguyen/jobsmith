"""Workday. Each employer runs its own tenant (acme.wd5.myworkdayjobs.com) with its own accounts,
but all tenants share the same `data-automation-id` attributes.

Applying: choose *Apply Manually* (`APPLY_MANUALLY`), never *Autofill with Resume*. Workday's
resume parsing mangles titles, companies and dates, so jobsmith fills every field from
`resumes/base.json` and still uploads the resume PDF (`RESUME_UPLOAD`) in My Experience. The
apply skill (`plugin/skills/apply/SKILL.md`) carries the page-by-page guidance;
`tests/fixtures/ats/workday/apply.html` is a fake application that the tests drive.
"""

from __future__ import annotations

import re
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

DATE_SECTIONS = (
    '[data-automation-id="dateSectionMonth-input"], '
    '[data-automation-id="dateSectionDay-input"], '
    '[data-automation-id="dateSectionYear-input"]'
)
_DATE_SHAPES = {1: ((4, None),), 2: ((2, 12), (4, None)), 3: ((2, 12), (2, 31), (4, None))}
"""Sections → (digits, maximum) for each: YYYY, MM/YYYY, MM/DD/YYYY."""


def date_digits(value: str, sections: int) -> list[str]:
    """Split "3/2022", "2022" or "3/5/2026" into zero-padded digits per section, or raise ValueError."""
    parts = value.split("/")
    shape = _DATE_SHAPES.get(sections)
    if shape is None or len(parts) != sections:
        raise ValueError(f"{value!r} doesn't fit a date with {sections} section(s)")
    digits = []
    for part, (width, maximum) in zip(parts, shape, strict=True):
        ok = part.isascii() and part.isdigit() and len(part) <= width and int(part) >= 1
        if not ok or (maximum is None and len(part) != width) or (maximum and int(part) > maximum):
            raise ValueError(f"{value!r} isn't a valid date for {sections} section(s)")
        digits.append(part.zfill(width))
    return digits


_DATE_KINDS = {("Year",): 1, ("Month", "Year"): 2, ("Month", "Day", "Year"): 3}
_READ_DATE_SECTIONS = """els => ({
    kinds: els.map((e) => e.dataset.automationId.replace(/^dateSection|-input$/g, "")),
    groups: new Set(els.map((e) => e.closest('[role="group"]'))).size,
})"""


def date_sections(group: Page | Locator) -> int:
    """How many sections the one date group in `group` has: 1 (YYYY), 2 (MM/YYYY) or 3
    (MM/DD/YYYY). Raises ValueError if `group` holds no date, more than one date group (such as
    "Education 1", which holds "From" and "To"), or sections in any other order."""
    found = group.locator(DATE_SECTIONS).evaluate_all(_READ_DATE_SECTIONS)
    kinds = tuple(found["kinds"])
    if found["groups"] != 1 or kinds not in _DATE_KINDS:
        raise ValueError(
            f"pass a single date group such as 'From', not one holding {found['groups']} date group(s) "
            f"with sections {', '.join(kinds) or 'none'}"
        )
    return _DATE_KINDS[kinds]


def fill_date(group: Locator, value: str) -> None:
    """Type `value` ("MM/YYYY", "YYYY" or "MM/DD/YYYY"; months and days may be unpadded) into a
    single date group such as "From". Raises ValueError, before typing anything, when `group`
    isn't exactly one date group (see `date_sections`) or `value` doesn't fit its sections.

    The spinbuttons sit outside the viewport, so click() never lands, and they keep their own
    digits, so fill() doesn't stick. Each section is focused and emptied with Backspace (a full
    section ignores more digits, so a refill would keep the old date), then the first is
    focused, the digits typed (each section moves on by itself), and Tab commits the date.
    """
    digits = date_digits(value, date_sections(group))
    sections = group.locator(DATE_SECTIONS)
    keyboard = getattr(group, "page", group).keyboard  # a Locator knows its page; a Page is one
    for i, d in enumerate(digits):
        sections.nth(i).focus()
        for _ in d:
            keyboard.press("Backspace")
    sections.first.focus()
    keyboard.type("".join(digits))
    keyboard.press("Tab")


def select_one(scope: Page | Locator, option: str, label: str = "") -> None:
    """Pick `option` in a "Select One" dropdown: a button named "<label> Select One Required"
    that opens a listbox. For an application question, pass the question's group as `scope` and
    no label: every question's button is named just "Select One Required"."""
    page = getattr(scope, "page", scope)  # a Locator knows its page; a Page is one
    # Anchored, so label="State" never matches "Home State Select One Required".
    name = re.compile(rf"^{re.escape(f'{label} Select One'.strip())}( Required)?$")
    scope.get_by_role("button", name=name).click()
    page.get_by_role("listbox").get_by_role("option", name=option, exact=True).click()


def search_prompt(field: Locator, query: str, option: str) -> None:
    """Choose `option` in a search prompt (Field of Study, Country Phone Code): type, press Enter,
    then click the option named "<option> not checked" in the prompt's own list (the one its
    aria-controls names: another prompt's list may be open with the same options). It then
    shows as "<option>, press delete to clear value."."""
    field.fill(query)
    field.press("Enter")
    own_list = field.page.locator(f'[id="{field.get_attribute("aria-controls")}"]')
    own_list.get_by_role("option", name=f"{option} not checked", exact=True).click()


def check_box(box: Locator) -> None:
    """Tick a box in a checkbox grid. A styled panel over each box takes the pointer, so a normal
    check() waits forever; force it."""
    box.check(force=True)
