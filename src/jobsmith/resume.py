"""Render a JSON Resume (https://jsonresume.org/schema) to HTML and PDF.

One layout for now, "compact": a single US Letter page in one column, with real text and
standard section headings so applicant tracking systems can parse it. The most recent roles get
full entries with a few highlights; older ones collapse to one line each under "Earlier roles".
Styles live in resume.css. Rendered by the user's installed Chrome (headless) via Playwright.

Rendered sections: basics, work, certificates, education, skills. Others in the schema
(projects, volunteer, awards, …) are ignored for now.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from html import escape
from pathlib import Path

from jobsmith import browser

CSS = Path(__file__).with_name("resume.css")
FONTS = "https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;600;700&display=swap"
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
# "Backlog Management: Directed the …" → the part before the colon is set in bold.
LEAD = re.compile(r"^([^:]{3,60}):\s+(.+)$", re.DOTALL)


class ResumeError(ValueError):
    pass


@dataclass
class Layout:
    full_roles: int = 5  # roles shown with highlights; the rest go under "Earlier roles". 0 = all
    bullets: int = 2  # highlights per full role. 0 = all
    accent: str = "#2c6a57"


def load(path: Path) -> dict:
    try:
        resume = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        raise ResumeError(f"{path}: not valid JSON ({e})") from e
    if not (resume.get("basics") or {}).get("name"):
        raise ResumeError(f"{path}: basics.name is required")
    return resume


def month(value: str | None) -> str:
    """'2024-01' or '2024-01-15' → 'Jan 2024'; '2024' → '2024'; missing → 'Present'."""
    if not value:
        return "Present"
    parts = value.split("-")
    return f"{MONTHS[int(parts[1]) - 1]} {parts[0]}" if len(parts) > 1 else parts[0]


def year(value: str | None) -> str:
    return value.split("-")[0] if value else "Present"


def _join(sep: str, *parts: str | None) -> str:
    """Join the non-empty parts."""
    return sep.join(p for p in parts if p)


def _span(cls: str, text: str | None) -> str:
    return f'<span class="{cls}">{escape(text or "")}</span>'


def _link(url: str) -> str:
    return f'<a href="{escape(url)}">{escape(url.split("://", 1)[-1].removeprefix("www."))}</a>'


def _highlight(text: str) -> str:
    if m := LEAD.match(text):
        return f"<li>{_span('lead', m[1] + ':')} {escape(m[2])}</li>"
    return f"<li>{escape(text)}</li>"


def _full_role(w: dict, bullets: int) -> str:
    when = escape(_join(" · ", w.get("location"), f"{month(w.get('startDate'))} – {month(w.get('endDate'))}"))
    title = f"<span>{_span('position', w.get('position'))} · {_span('company', w.get('name'))}</span>"
    items = w.get("highlights") or []
    lis = "\n".join(_highlight(h) for h in (items[:bullets] if bullets else items))
    return _join(
        "\n",
        '<div class="role">',
        f'<div class="line">{title}<span class="when">{when}</span></div>',
        lis and f"<ul>\n{lis}\n</ul>",
        "</div>",
    )


def _earlier_role(w: dict) -> str:
    title = f"<span>{_span('position', w.get('position'))} · {escape(w.get('name', ''))}</span>"
    start, end = year(w.get("startDate")), year(w.get("endDate"))
    when = start if start == end else f"{start} – {end}"
    return f'<div class="line">{title}<span class="when">{when}</span></div>'


def _header(b: dict) -> str:
    loc = b.get("location") or {}
    city = _join(", ", loc.get("city"), _join(" ", loc.get("region"), loc.get("postalCode")))
    place = escape(_join(", ", loc.get("address"), city))
    reach = escape(_join(" · ", b.get("phone"), b.get("email")))
    urls = [b.get("url"), *(p.get("url") for p in b.get("profiles") or [])]
    links = _join(" · ", *(_link(u) for u in urls if u))
    contact = "\n".join(f"<span>{x}</span>" for x in [place, reach, links] if x)
    label = b.get("label") and f'<div class="label">{escape(b["label"])}</div>'
    who = _join("\n", '<div class="who">', f"<h1>{escape(b['name'])}</h1>", label, "</div>")
    return f'<header>\n{who}\n<div class="contact">\n{contact}\n</div>\n</header>'


def _cert(c: dict) -> str:
    issued = f" · {year(c['date'])}" if c.get("date") else ""
    return f"<div>{_span('name', c.get('name'))}{escape(issued)}</div>"


def _school(x: dict) -> str:
    degree = _join(", ", x.get("studyType"), x.get("area"), x.get("endDate") and year(x["endDate"]))
    return f"<div>{_span('name', x.get('institution'))}<br>{escape(degree)}</div>"


def _skill(s: dict) -> str:
    return f"<div>{_span('name', s.get('name', '') + ':')} {escape(', '.join(s.get('keywords') or []))}</div>"


def _section(title: str, body: str, cls: str = "") -> str:
    attr = f' class="{cls}"' if cls else ""
    return f"<section{attr}>\n<h2>{title}</h2>\n{body}\n</section>"


def to_html(resume: dict, layout: Layout | None = None) -> str:
    layout = layout or Layout()
    b = resume["basics"]
    parts = [_header(b)]
    if b.get("summary"):
        parts.append(f'<p class="summary">{escape(b["summary"])}</p>')

    if work := resume.get("work"):
        n = layout.full_roles or len(work)
        body = "\n".join(_full_role(w, layout.bullets) for w in work[:n])
        if earlier := work[n:]:
            rows = "\n".join(_earlier_role(w) for w in earlier)
            body += f'\n<div class="earlier">\n<h3>Earlier roles</h3>\n{rows}\n</div>'
        parts.append(_section("Experience", body))

    pair = []
    if certs := resume.get("certificates"):
        pair.append(_section("Certifications", "\n".join(map(_cert, certs))))
    if edu := resume.get("education"):
        pair.append(_section("Education", "\n".join(map(_school, edu))))
    if len(pair) == 2:
        parts.append('<div class="pair">\n' + "\n".join(pair) + "\n</div>")
    else:
        parts.extend(pair)

    if skills := resume.get("skills"):
        parts.append(_section("Skills", "\n".join(map(_skill, skills)), "skills"))

    body = "\n".join(parts)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{escape(b["name"])} — Resume</title>
<link rel="stylesheet" href="{FONTS}">
<style>
:root {{ --accent: {escape(layout.accent)}; }}
{CSS.read_text()}
</style>
</head>
<body>
<main>
{body}
</main>
</body>
</html>
"""


def page_count(pdf: bytes) -> int:
    return len(re.findall(rb"/Type\s*/Page(?![s\w])", pdf))


def to_pdf(html: str, out: Path) -> int:
    """Print `html` to a Letter PDF at `out` with headless Chrome. Returns the page count."""
    if not Path(browser.CHROME).exists():
        raise ResumeError(f"Chrome not found at {browser.CHROME}")
    from playwright.sync_api import sync_playwright

    out.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        b = pw.chromium.launch(channel="chrome", headless=True)
        try:
            page = b.new_page()
            page.set_content(html, wait_until="networkidle")
            page.evaluate("document.fonts.ready.then(() => true)")
            pdf = page.pdf(path=str(out), prefer_css_page_size=True, print_background=True)
        finally:
            b.close()
    return page_count(pdf)
