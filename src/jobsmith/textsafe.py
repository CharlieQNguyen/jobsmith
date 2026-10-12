"""Make text safe for form fields that reject some characters, and say what changed.

Some applicant tracking systems refuse certain characters in free-text fields (Workday answers
"Error: Contains illegal characters"). Each ATS lists them in `ATS.illegal_characters`.
`sanitize` swaps each for the nearest acceptable character and reports every change, so the
agent filling the form can tell the user exactly what it altered.

Run it on a whole answer before typing it into a field:

    echo 'Led the "Atlas" migration [2023]' | python -m jobsmith.textsafe --ats workday

prints JSON: {"text": "...", "changes": [{"from": "\\"", "to": "'", "count": 2}, ...]}.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass

REPLACEMENTS: dict[str, str] = {
    '"': "'",
    "[": "(",
    "]": ")",
    "{": "(",
    "}": ")",
    "<": "(",
    ">": ")",
    "\\": "/",
}
"""What each commonly rejected character becomes. A rejected character not listed here is dropped."""

ARROWS: dict[str, str] = {" -> ": " to ", " => ": " to "}
"""Spaced arrows read better as a word than as "-)"; checked before single characters."""


@dataclass(frozen=True)
class Change:
    old: str
    new: str
    count: int


@dataclass(frozen=True)
class Sanitized:
    text: str
    changes: tuple[Change, ...]

    @property
    def changed(self) -> bool:
        return bool(self.changes)

    def describe(self) -> str:
        """One line for the user, e.g. `" → ' (2×), [ → ( (1×)`. Empty when nothing changed."""
        return ", ".join(f"{c.old} → {c.new or '(removed)'} ({c.count}×)" for c in self.changes)


def sanitize(text: str, illegal: str) -> Sanitized:
    """Replace every character of `illegal` in `text`. Characters outside `illegal` are kept."""
    changes: list[Change] = []
    for arrow, word in ARROWS.items():
        if any(ch in illegal for ch in arrow) and (n := text.count(arrow)):
            text = text.replace(arrow, word)
            changes.append(Change(arrow.strip(), word.strip(), n))
    for ch in dict.fromkeys(c for c in text if c in illegal):
        n = text.count(ch)
        new = REPLACEMENTS.get(ch, "")
        text = text.replace(ch, new)
        changes.append(Change(ch, new, n))
    return Sanitized(text, tuple(changes))


def main(argv: list[str] | None = None) -> int:
    from jobsmith import ats

    parser = argparse.ArgumentParser(prog="python -m jobsmith.textsafe", description=__doc__.split("\n")[0])
    parser.add_argument("--ats", default="workday", help="ATS whose rules apply (default: workday)")
    args = parser.parse_args(argv)
    try:
        site = ats.by_name(args.ats)
    except StopIteration:
        parser.error(f"unknown ATS {args.ats!r}")
    result = sanitize(sys.stdin.read().removesuffix("\n"), site.illegal_characters)
    changes = [{"from": c.old, "to": c.new, "count": c.count} for c in result.changes]
    json.dump({"text": result.text, "changes": changes}, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
