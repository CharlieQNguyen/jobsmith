"""Workday. Each employer runs its own tenant (acme.wd5.myworkdayjobs.com) with its own accounts,
but all tenants share the same `data-automation-id` attributes.

Applying: choose *Apply Manually* (`APPLY_MANUALLY`), never *Autofill with Resume*. Workday's
resume parsing mangles titles, companies and dates, so jobsmith fills every field from
`resumes/base.json` and still uploads the resume PDF (`RESUME_UPLOAD`) in My Experience. The
apply skill (`plugin/skills/apply/SKILL.md`) carries the page-by-page guidance;
`tests/fixtures/ats/workday/apply.html` is a fake application that the tests drive.
"""

from jobsmith.ats import ATS

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
