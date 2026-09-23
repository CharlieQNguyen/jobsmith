import json
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from jobsmith import browser, resume
from jobsmith.cli import app

EXAMPLE = Path(__file__).parents[1] / "examples" / "resumes" / "base.json"


@pytest.fixture
def data():
    return json.loads(EXAMPLE.read_text())


def test_dates():
    assert resume.month("2024-01") == "Jan 2024"
    assert resume.month("2024-09-01") == "Sep 2024"
    assert resume.month("2018") == "2018"
    assert resume.month(None) == "Present"
    assert resume.year("2015-11") == "2015"


def test_html_has_the_standard_sections(data):
    html = resume.to_html(data)
    assert "<h1>Alex Example</h1>" in html
    for heading in ("Experience", "Certifications", "Education", "Skills"):
        assert f"<h2>{heading}</h2>" in html
    assert "Portland, OR" in html and "555-0100" in html
    assert '<a href="https://github.com/alex-example">github.com/alex-example</a>' in html
    assert "Jan 2022" not in html and "Mar 2022 – Present" in html


def test_lead_in_before_a_colon_is_bold(data):
    html = resume.to_html(data)
    assert '<span class="lead">Billing migration:</span> Moved billing' in html
    assert "<li>Built the internal API gateway used by 30+ services</li>" in html


def test_layout_trims_bullets_and_collapses_older_roles(data):
    html = resume.to_html(data, resume.Layout(full_roles=1, bullets=1))
    assert "Built the internal API gateway" not in html
    assert "<h3>Earlier roles</h3>" in html
    assert "Junior Developer" in html and "2019 – 2022" in html
    assert "Wrote the inventory sync" not in html
    assert '<span class="when">2018</span>' in html  # same start and end year shown once

    everything = resume.to_html(data, resume.Layout(full_roles=0, bullets=0))
    assert "Earlier roles" not in everything and "Ran the on-call rotation" in everything


def test_text_is_escaped(data):
    data["work"][0]["highlights"] = ["<script>alert(1)</script> & more"]
    html = resume.to_html(data)
    assert "<script>" not in html and "&lt;script&gt;alert(1)&lt;/script&gt; &amp; more" in html


def test_load_rejects_bad_files(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{")
    with pytest.raises(resume.ResumeError, match="not valid JSON"):
        resume.load(bad)
    bad.write_text('{"basics": {}}')
    with pytest.raises(resume.ResumeError, match="basics.name"):
        resume.load(bad)


def test_page_count():
    assert resume.page_count(b"<< /Type /Pages /Count 2 >> << /Type /Page >> << /Type/Page >>") == 2


@pytest.mark.browser
def test_render_command_writes_a_one_page_pdf(tmp_path):
    if not Path(browser.CHROME).exists():
        pytest.skip("Google Chrome not installed")
    (tmp_path / "resumes").mkdir()
    shutil.copy(EXAMPLE, tmp_path / "resumes" / "base.json")
    result = CliRunner().invoke(app, ["resume", "render", "--html", "--data", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "Wrote resumes/base.pdf (1 page)" in result.output
    pdf = (tmp_path / "resumes" / "base.pdf").read_bytes()
    assert pdf.startswith(b"%PDF") and resume.page_count(pdf) == 1
    assert (tmp_path / "resumes" / "base.html").is_file()
