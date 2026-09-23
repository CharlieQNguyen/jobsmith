"""Read and write the plain-file data directory.

Layout (all paths relative to the data directory):

    profile/profile.yaml
    applications/<slug>.md      YAML frontmatter + Markdown notes
    accounts.yaml               site accounts (no passwords)
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import yaml

from jobsmith.models import Account, Application, Profile

FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n?(.*)\Z", re.DOTALL)


def data_dir(override: Path | None = None) -> Path:
    if override:
        return override
    if env := os.environ.get("JOBSMITH_DATA"):
        return Path(env)
    return Path.cwd()


def slugify(*parts: str) -> str:
    text = "-".join(parts).lower()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


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
