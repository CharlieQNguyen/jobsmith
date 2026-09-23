"""A long-lived Chrome that the user logs into and an agent then drives.

jobsmith launches the user's installed Chrome with a dedicated profile directory under
$XDG_DATA_HOME/jobsmith (one per user, so sign-ins persist across runs, data repos and worktrees)
and a DevTools port bound to localhost. `login()` connects over CDP and fills
credentials from the keychain; afterwards an agent attaches to the same port (e.g. Playwright MCP
with `--cdp-endpoint`) and continues in the signed-in tab.

Anything on this machine can drive the browser while the port is open, so stop it when done.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from playwright.sync_api import Page, sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeout

from jobsmith import ats, credentials

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
DEFAULT_PORT = 9222


class BrowserError(RuntimeError):
    pass


@dataclass
class Paths:
    profile: Path
    pidfile: Path

    @classmethod
    def default(cls) -> Paths:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "jobsmith"
        return cls(profile=base / "chrome-profile", pidfile=base / "chrome.pid")


def port() -> int:
    return int(os.environ.get("JOBSMITH_CDP_PORT", DEFAULT_PORT))


def endpoint() -> str:
    return f"http://127.0.0.1:{port()}"


def is_running() -> bool:
    try:
        with urllib.request.urlopen(f"{endpoint()}/json/version", timeout=1) as r:
            return "webSocketDebuggerUrl" in json.load(r)
    except OSError:
        return False


def start(chrome: str = CHROME) -> bool:
    """Launch Chrome if it isn't already listening. Returns True if newly started."""
    if is_running():
        return False
    if not Path(chrome).exists():
        raise BrowserError(f"Chrome not found at {chrome}")
    paths = Paths.default()
    paths.profile.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen(
        [
            chrome,
            f"--user-data-dir={paths.profile}",
            f"--remote-debugging-port={port()}",
            "--remote-debugging-address=127.0.0.1",
            "--no-first-run",
            "--no-default-browser-check",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    paths.pidfile.write_text(str(proc.pid))
    for _ in range(50):
        if is_running():
            return True
        time.sleep(0.2)
    raise BrowserError(f"Chrome started but DevTools never answered on {endpoint()}")


def stop() -> bool:
    """Quit the Chrome that `start` launched. Returns False if none was running."""
    pidfile = Paths.default().pidfile
    if not pidfile.exists():
        return False
    pid = int(pidfile.read_text())
    pidfile.unlink()
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return False
    return True


def _first_visible(page: Page, selectors: tuple[str, ...], timeout_ms: int) -> str | None:
    """Wait up to timeout_ms for any selector to become visible; return the first that does."""
    try:
        page.locator(", ".join(selectors)).first.wait_for(state="visible", timeout=timeout_ms)
    except PlaywrightTimeout:
        return None
    return next((sel for sel in selectors if page.locator(sel).first.is_visible()), None)


def fill_login(page: Page, site: ats.ATS, username: str, password: str, timeout_ms: int = 20_000) -> str:
    """Fill and submit the sign-in form on the current page. Returns a short status message."""
    pw_sel = _first_visible(page, site.password_selectors, timeout_ms)
    if pw_sel is None:
        return "No password field appeared — maybe already signed in? Check the browser."
    if user_sel := _first_visible(page, site.username_selectors, 2_000):
        page.locator(user_sel).first.fill(username)
    pw_field = page.locator(pw_sel).first
    pw_field.fill(password)
    if site.submit_selector:
        page.locator(site.submit_selector).first.click()
    else:
        pw_field.press("Enter")
    try:
        pw_field.wait_for(state="hidden", timeout=timeout_ms)
    except PlaywrightTimeout:
        return "Submitted, but the login form is still showing — check for MFA, CAPTCHA or an error."
    return "Signed in."


def login(host: str, username: str, url: str, timeout_ms: int = 20_000) -> str:
    """Open `url` in the running Chrome and sign in with the keychain password.

    Returns a short status message. Leaves the tab open either way.
    """
    password = credentials.get(host, username)
    if password is None:
        raise BrowserError(f"No password in keychain for {username}@{host}")
    if not is_running():
        raise BrowserError("Browser isn't running — `jobsmith browser start` first")

    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(endpoint())
        context = browser.contexts[0] if browser.contexts else browser.new_context()
        page = context.new_page()
        page.goto(url, wait_until="domcontentloaded")
        page.bring_to_front()

        return fill_login(page, ats.for_host(host), username, password, timeout_ms)
