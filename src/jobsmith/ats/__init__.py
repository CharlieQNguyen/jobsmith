"""Applicant tracking systems (ATS): how to recognise each one and drive its forms.

Each ATS lives in its own module and is listed in `REGISTRY`. `for_host` picks the first match,
falling back to `GENERIC`. Every ATS has a fake sign-in page in `tests/fixtures/ats/<name>/` that
the test suite drives in headless Chrome — see the `add-ats` skill.
"""

from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatch


@dataclass(frozen=True)
class ATS:
    name: str
    host_patterns: tuple[str, ...]
    """fnmatch patterns against the lowercased host, e.g. "*.myworkdayjobs.com"."""
    username_selectors: tuple[str, ...]
    password_selectors: tuple[str, ...]
    submit_selector: str | None = None
    """Button to click after filling. None presses Enter in the password field."""

    def matches(self, host: str) -> bool:
        return any(fnmatch(host.lower(), p) for p in self.host_patterns)


from jobsmith.ats.generic import GENERIC  # noqa: E402
from jobsmith.ats.workday import WORKDAY  # noqa: E402

REGISTRY: tuple[ATS, ...] = (WORKDAY,)


def for_host(host: str) -> ATS:
    return next((a for a in REGISTRY if a.matches(host)), GENERIC)


def by_name(name: str) -> ATS:
    return next(a for a in (*REGISTRY, GENERIC) if a.name == name)
