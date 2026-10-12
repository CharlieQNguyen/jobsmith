"""The apply skill's instructions that can be checked without an agent: its order and its scripts."""

import re
import subprocess
import sys
import time
from pathlib import Path

import pytest

from jobsmith import browser

ROOT = Path(__file__).parents[1]
SKILL = (ROOT / "plugin" / "skills" / "apply" / "SKILL.md").read_text()
FIXTURES = ROOT / "tests" / "fixtures" / "ats"


def section(heading: str) -> str:
    start = SKILL.index(f"\n## {heading}")
    end = SKILL.find("\n## ", start + 1)
    return SKILL[start : end if end != -1 else None]


def test_browser_tools_are_checked_before_anything_else():
    first = re.findall(r"^## (.+)$", SKILL, flags=re.M)[0]
    assert first == "0. Check the browser tools first"
    check = section("0. Check the browser tools first")
    assert "jobsmith-browser" in check
    assert "start a new Claude Code session in their\n  jobsmith data repo" in check
    assert "**Never use a generic `playwright` MCP**" in check
    assert 'connect_over_cdp("http://127.0.0.1:9222")' in check


def fallback_script() -> str:
    block = re.search(r'"\$\(uv tool dir\)/jobsmith/bin/python" - <<\'EOF\'\n(.*?)\nEOF', SKILL, re.S)
    assert block, "the fallback heredoc is missing from the skill"
    return block.group(1)


@pytest.fixture
def signed_in_chrome(tmp_path):
    """A headless Chrome with a DevTools port, standing in for the one `jobsmith login` leaves open."""
    if not Path(browser.CHROME).exists():
        pytest.skip("Google Chrome not installed")
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        context = pw.chromium.launch_persistent_context(
            tmp_path / "profile", channel="chrome", headless=True, args=["--remote-debugging-port=0"]
        )
        port_file = tmp_path / "profile" / "DevToolsActivePort"
        for _ in range(100):
            if port_file.exists() and port_file.read_text().strip():
                break
            time.sleep(0.05)
        page = context.pages[0] if context.pages else context.new_page()
        page.goto((FIXTURES / "workday" / "login.html").as_uri())
        page.locator('[data-automation-id="email"]').wait_for()
        yield page, int(port_file.read_text().splitlines()[0])
        context.close()


@pytest.mark.browser
def test_fallback_script_reads_the_open_tab_and_leaves_it_open(signed_in_chrome):
    page, port = signed_in_chrome
    script = fallback_script().replace("127.0.0.1:9222", f"127.0.0.1:{port}").replace("<host>", "login.html")
    out = subprocess.run([sys.executable, "-"], input=script, capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    assert out.stdout.startswith(f"Workday sign-in (fake) {page.url}\n")
    assert 'textbox "Email Address"' in out.stdout
    assert page.locator('[data-automation-id="email"]').is_visible()


def test_workday_applications_start_manually_and_still_upload_the_resume():
    confirm = section("4. Confirm the data before entering it")
    assert "**On Workday choose *Apply*\n→ *Apply Manually*,** never *Autofill with Resume*" in confirm
    fill = section("5. Fill it in")
    assert "**Upload the resume PDF**" in fill
    assert "After autofill" not in SKILL


def test_the_skill_teaches_every_workday_widget_helper():
    from jobsmith.ats import workday

    widgets = SKILL.split("### Workday's widgets", 1)[1].split("\n## ", 1)[0]
    for helper in (workday.fill_date, workday.select_one, workday.search_prompt, workday.check_box):
        assert f"`{helper.__name__}`" in widgets
    for shape in (
        "dateSectionMonth-input",
        "Select One Required",
        "not checked",
        "press delete to clear value",
    ):
        assert shape in widgets
    assert "check(force=True)" in widgets
