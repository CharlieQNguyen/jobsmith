import io
import json
from pathlib import Path

import pytest

from jobsmith import ats, textsafe
from jobsmith.textsafe import Change, sanitize

WORKDAY = ats.WORKDAY.illegal_characters


def test_workday_rejects_exactly_these():
    assert sorted(WORKDAY) == sorted('<>[]"{}\\')


def test_clean_text_is_untouched():
    text = "Led the Atlas migration (2023): 40% fewer errors, team of 5 - on time & on budget!\nNext line"
    result = sanitize(text, WORKDAY)
    assert result.text == text
    assert result.changes == ()
    assert not result.changed
    assert result.describe() == ""


@pytest.mark.parametrize(
    ("ch", "new"),
    [('"', "'"), ("[", "("), ("]", ")"), ("{", "("), ("}", ")"), ("<", "("), (">", ")"), ("\\", "/")],
)
def test_every_workday_character(ch, new):
    result = sanitize(f"a{ch}b{ch}", WORKDAY)
    assert result.text == f"a{new}b{new}"
    assert result.changes == (Change(ch, new, 2),)
    assert result.changed


def test_every_printable_ascii_comes_out_accepted():
    text = "".join(chr(c) for c in range(32, 127))
    result = sanitize(text, WORKDAY)
    assert not set(result.text) & set(WORKDAY)
    assert {c.old for c in result.changes} == set(WORKDAY)
    assert len(result.text) == len(text)


def test_changes_are_reported_in_order_of_first_appearance():
    result = sanitize('Said [twice] "ship it"', WORKDAY)
    assert result.text == "Said (twice) 'ship it'"
    assert result.changes == (Change("[", "(", 1), Change("]", ")", 1), Change('"', "'", 2))
    assert result.describe() == "[ → ( (1×), ] → ) (1×), \" → ' (2×)"


def test_spaced_arrows_become_words():
    result = sanitize("monolith -> services => savings", WORKDAY)
    assert result.text == "monolith to services to savings"
    assert result.changes == (Change("->", "to", 1), Change("=>", "to", 1))


def test_unspaced_arrow_falls_back_to_characters():
    assert sanitize("a->b", WORKDAY).text == "a-)b"


def test_only_the_given_characters_are_touched():
    assert sanitize('"quoted" -> [kept]', "").text == '"quoted" -> [kept]'
    assert sanitize('"quoted" -> [kept]', "[]").text == '"quoted" -> (kept)'


def test_character_without_a_replacement_is_removed():
    result = sanitize("a~b~", "~")
    assert result.text == "ab"
    assert result.changes == (Change("~", "", 2),)
    assert result.describe() == "~ → (removed) (2×)"


def test_command_line_prints_json(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO('Built the "Atlas" API\n'))
    assert textsafe.main(["--ats", "workday"]) == 0
    assert json.loads(capsys.readouterr().out) == {
        "text": "Built the 'Atlas' API",
        "changes": [{"from": '"', "to": "'", "count": 2}],
    }


def test_command_line_rejects_unknown_ats(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("x"))
    with pytest.raises(SystemExit) as exc:
        textsafe.main(["--ats", "nope"])
    assert exc.value.code == 2
    assert "unknown ATS 'nope'" in capsys.readouterr().err


def test_apply_skill_lists_the_rejected_characters():
    skill = (Path(__file__).parents[1] / "plugin" / "skills" / "apply" / "SKILL.md").read_text()
    assert 'python" -m jobsmith.textsafe --ats workday' in skill
    listed = skill.split("Workday text fields refuse", 1)[1].split("(", 1)[0]
    assert sorted(listed.replace("`", "").split()) == sorted(WORKDAY)
