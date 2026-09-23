"""Workday. Each employer runs its own tenant (acme.wd5.myworkdayjobs.com) with its own accounts,
but all tenants share the same `data-automation-id` attributes."""

from jobsmith.ats import ATS

WORKDAY = ATS(
    name="workday",
    host_patterns=("*.myworkdayjobs.com", "*.myworkdaysite.com", "*.myworkday.com"),
    username_selectors=('[data-automation-id="email"]', 'input[type="email"]'),
    password_selectors=('[data-automation-id="password"]', 'input[type="password"]'),
    # A transparent click_filter overlay covers Workday's submit button; Enter avoids it.
    submit_selector=None,
)
