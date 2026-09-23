"""Fallback for sites without a dedicated ATS module: common login-form conventions."""

from jobsmith.ats import ATS

GENERIC = ATS(
    name="generic",
    host_patterns=(),
    username_selectors=(
        'input[type="email"]',
        'input[autocomplete="username"]',
        'input[name*="user" i]',
        'input[name*="email" i]',
        'input[id*="user" i]',
        'input[id*="email" i]',
    ),
    password_selectors=('input[type="password"]',),
)
