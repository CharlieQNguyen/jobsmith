"""Read and write the plain-file data directory.

Layout (all paths relative to the data directory):

    profile/profile.yaml
    applications/<slug>.md      YAML frontmatter + Markdown notes
    accounts.yaml               site accounts (no passwords)
"""

from __future__ import annotations

import os
import re
from datetime import date, timedelta
from pathlib import Path

import yaml

from jobsmith.models import Account, Application, Profile

FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n?(.*)\Z", re.DOTALL)


def is_data_repo(path: Path) -> bool:
    return (path / "accounts.yaml").is_file() or (path / "profile" / "profile.yaml").is_file()


def data_dir(override: Path | None = None, cwd: Path | None = None) -> Path:
    """Where the data lives: --data, else the nearest data repo at or above the current directory
    (so each git worktree uses its own files), else $JOBSMITH_DATA, else the current directory."""
    if override:
        return override
    cwd = (cwd or Path.cwd()).resolve()
    if found := next((d for d in (cwd, *cwd.parents) if is_data_repo(d)), None):
        return found
    if env := os.environ.get("JOBSMITH_DATA"):
        return Path(env)
    return cwd


def slugify(*parts: str) -> str:
    text = "-".join(parts).lower()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def parse_date(text: str, today: date | None = None) -> date:
    """`today`, `+3d`, `+2w`, or an ISO date."""
    today = today or date.today()
    text = text.strip().lower()
    if text == "today":
        return today
    if m := re.fullmatch(r"\+(\d+)([dw])", text):
        n = int(m[1]) * (7 if m[2] == "w" else 1)
        return today + timedelta(days=n)
    return date.fromisoformat(text)


def load_profile(root: Path) -> Profile:
    return Profile.model_validate(yaml.safe_load((root / "profile" / "profile.yaml").read_text()))


def read_application(path: Path) -> Application:
    match = FRONTMATTER.match(path.read_text())
    if not match:
        raise ValueError(f"{path}: missing YAML frontmatter")
    meta, body = match.groups()
    return Application.model_validate({**(yaml.safe_load(meta) or {}), "notes": body.strip()})


def write_application(root: Path, app: Application, slug: str | None = None) -> Path:
    path = root / "applications" / f"{slug or slugify(app.company, app.role)}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    meta = yaml.safe_dump(app.model_dump(mode="json", exclude_none=True), sort_keys=False)
    path.write_text(f"---\n{meta}---\n\n{app.notes}\n" if app.notes else f"---\n{meta}---\n")
    return path


def load_applications(root: Path) -> dict[str, Application]:
    folder = root / "applications"
    if not folder.is_dir():
        return {}
    return {p.stem: read_application(p) for p in sorted(folder.glob("*.md"))}


def load_accounts(root: Path) -> list[Account]:
    path = root / "accounts.yaml"
    raw = (yaml.safe_load(path.read_text()) if path.exists() else None) or []
    return [Account.model_validate(a) for a in raw]


def save_accounts(root: Path, accounts: list[Account]) -> None:
    data = [a.model_dump(mode="json", exclude_none=True) for a in accounts]
    (root / "accounts.yaml").write_text(yaml.safe_dump(data, sort_keys=False))


def find_account(root: Path, host: str, username: str | None = None) -> Account | None:
    """The account for `host`; `username` picks one when a site has several."""
    matches = [a for a in load_accounts(root) if a.host == host.lower()]
    if username:
        matches = [a for a in matches if a.username == username]
    return matches[0] if len(matches) == 1 else None


def upsert_account(root: Path, account: Account) -> None:
    accounts = [a for a in load_accounts(root) if (a.host, a.username) != (account.host, account.username)]
    save_accounts(root, [*accounts, account])


def resolve_application(root: Path, query: str) -> str:
    """Slug for `query`: an exact slug, or a unique case-insensitive match on slug/company/role.

    Raises LookupError listing the candidates when there are none or several.
    """
    apps = load_applications(root)
    if query in apps:
        return query
    words = query.lower().split()
    hits = [
        slug for slug, a in apps.items() if all(w in f"{slug} {a.company} {a.role}".lower() for w in words)
    ]
    if len(hits) == 1:
        return hits[0]
    raise LookupError(
        f"{'No' if not hits else 'Several'} applications match {query!r}"
        + (": " + ", ".join(hits) if hits else "")
    )
