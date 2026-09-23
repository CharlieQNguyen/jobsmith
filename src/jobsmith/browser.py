"""A long-lived Chrome that the user logs into and an agent then drives.

jobsmith launches the user's installed Chrome with a dedicated profile directory (so sessions
persist between runs) and a DevTools port bound to localhost. `login()` connects over CDP and fills
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

from jobsmith import credentials

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
DEFAULT_PORT = 9222

# Tried in order. Workday tenants share data-automation-id attributes.
USERNAME_SELECTORS = [
    '[data-automation-id="email"]',
    'input[type="email"]',
    'input[autocomplete="username"]',
    'input[name*="user" i]',
    'input[name*="email" i]',
    'input[id*="user" i]',
    'input[id*="email" i]',
]
PASSWORD_SELECTORS = ['[data-automation-id="password"]', 'input[type="password"]']


class BrowserError(RuntimeError):
    pass


@dataclass
class Paths:
    profile: Path
    pidfile: Path

    @classmethod
    def under(cls, root: Path) -> Paths:
        base = root / ".browser-profiles"
        return cls(profile=base / "chrome", pidfile=base / "chrome.pid")


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


def start(root: Path, chrome: str = CHROME) -> bool:
    """Launch Chrome if it isn't already listening. Returns True if newly started."""
    if is_running():
        return False
    if not Path(chrome).exists():
        raise BrowserError(f"Chrome not found at {chrome}")
    paths = Paths.under(root)
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


def stop(root: Path) -> bool:
    """Quit the Chrome that `start` launched. Returns False if none was running."""
    pidfile = Paths.under(root).pidfile
    if not pidfile.exists():
        return False
    pid = int(pidfile.read_text())
    pidfile.unlink()
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return False
    return True


def _first_visible(page: Page, selectors: list[str], timeout_ms: int) -> str | None:
    """Wait up to timeout_ms for any selector to become visible; return the first that does."""
    combined = ", ".join(selectors)
    try:
        page.locator(combined).first.wait_for(state="visible", timeout=timeout_ms)
    except PlaywrightTimeout:
        return None
    for sel in selectors:
        if page.locator(sel).first.is_visible():
            return sel
    return None


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

        pw_sel = _first_visible(page, PASSWORD_SELECTORS, timeout_ms)
        if pw_sel is None:
            return "No password field appeared — maybe already signed in? Check the browser."
        user_sel = _first_visible(page, USERNAME_SELECTORS, 2_000)
        if user_sel:
            page.locator(user_sel).first.fill(username)
        page.locator(pw_sel).first.fill(password)
        page.locator(pw_sel).first.press("Enter")

        try:
            page.locator(pw_sel).first.wait_for(state="hidden", timeout=timeout_ms)
        except PlaywrightTimeout:
            return "Submitted, but the login form is still showing — check for MFA, CAPTCHA or an error."
        return "Signed in."
        # Leaving the `with` block disconnects Playwright; Chrome and the tab stay open.
