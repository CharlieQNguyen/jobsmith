"""Command-line interface."""

from __future__ import annotations

import shutil
import subprocess
from datetime import date
from pathlib import Path
from typing import Annotated

import typer
import yaml

from jobsmith import credentials, store
from jobsmith.models import Status

app = typer.Typer(no_args_is_help=True, help="Keep your job search in plain files.")
apps_cmd = typer.Typer(no_args_is_help=True, help="Job applications.")
creds_cmd = typer.Typer(no_args_is_help=True, help="Site credentials in the OS keychain.")
app.add_typer(apps_cmd, name="apps")
app.add_typer(creds_cmd, name="creds")

DataOpt = Annotated[
    Path | None,
    typer.Option("--data", "-d", help="Data directory (default: $JOBSMITH_DATA or cwd)"),
]


@app.command()
def check(data: DataOpt = None) -> None:
    """Validate every data file."""
    root = store.data_dir(data)
    problems = 0
    for path in sorted((root / "applications").glob("*.md")):
        try:
            store.read_application(path)
        except Exception as e:  # noqa: BLE001 - report every bad file, keep going
            problems += 1
            typer.secho(f"✗ {path.relative_to(root)}: {e}", fg="red")
    if (root / "profile" / "profile.yaml").exists():
        try:
            store.load_profile(root)
        except Exception as e:  # noqa: BLE001
            problems += 1
            typer.secho(f"✗ profile/profile.yaml: {e}", fg="red")
    if problems:
        raise typer.Exit(1)
    typer.secho("✓ all data files valid", fg="green")


@apps_cmd.command("list")
def apps_list(
    data: DataOpt = None,
    status: Annotated[Status | None, typer.Option(help="Only this status")] = None,
    open_only: Annotated[bool, typer.Option("--open", help="Hide closed applications")] = False,
) -> None:
    """List applications."""
    for slug, a in store.load_applications(store.data_dir(data)).items():
        if status and a.status != status:
            continue
        if open_only and not a.status.is_open:
            continue
        followup = f"  follow up {a.next_followup}" if a.next_followup and a.status.is_open else ""
        typer.echo(f"{a.status:<13} {a.company} — {a.role}  [{slug}]{followup}")


@apps_cmd.command("due")
def apps_due(data: DataOpt = None) -> None:
    """Applications whose follow-up date has arrived."""
    today = date.today()
    due = [(s, a) for s, a in store.load_applications(store.data_dir(data)).items() if a.followup_due(today)]
    if not due:
        typer.echo("Nothing due.")
        return
    for slug, a in sorted(due, key=lambda x: x[1].next_followup):
        typer.echo(f"{a.next_followup}  {a.company} — {a.role} ({a.status})  [{slug}]")


def _copy_to_clipboard(text: str) -> bool:
    if not shutil.which("pbcopy"):
        return False
    subprocess.run(["pbcopy"], input=text.encode(), check=True)
    return True


def _record_account(root: Path, host: str, username: str) -> None:
    path = root / "accounts.yaml"
    accounts = (yaml.safe_load(path.read_text()) if path.exists() else None) or []
    if not any(a["host"] == host and a["username"] == username for a in accounts):
        accounts.append({"host": host, "username": username, "created": date.today().isoformat()})
        path.write_text(yaml.safe_dump(accounts, sort_keys=False))


@creds_cmd.command("new")
def creds_new(
    host: Annotated[str, typer.Argument(help="Site host, e.g. acme.wd5.myworkdayjobs.com")],
    username: str,
    data: DataOpt = None,
) -> None:
    """Generate a password, store it in the keychain, and copy it to the clipboard."""
    if credentials.exists(host, username):
        typer.secho(f"{username}@{host} already has a stored password.", fg="yellow")
        raise typer.Exit(1)
    pw = credentials.generate_password()
    credentials.store(host, username, pw)
    _record_account(store.data_dir(data), host, username)
    if _copy_to_clipboard(pw):
        typer.echo("Stored in keychain and copied to clipboard — paste it into the sign-up form.")
    else:
        typer.echo("Stored in keychain. Run `jobsmith creds copy` on a machine with a clipboard.")


@creds_cmd.command("copy")
def creds_copy(host: str, username: str) -> None:
    """Copy a stored password to the clipboard (never prints it)."""
    pw = credentials.get(host, username)
    if pw is None:
        typer.secho(f"No password stored for {username}@{host}.", fg="red")
        raise typer.Exit(1)
    if not _copy_to_clipboard(pw):
        typer.secho("No clipboard available.", fg="red")
        raise typer.Exit(1)
    typer.echo("Copied to clipboard.")


@creds_cmd.command("check")
def creds_check(host: str, username: str) -> None:
    """Report whether a password is stored (never prints it)."""
    ok = credentials.exists(host, username)
    typer.echo(f"{username}@{host}: {'stored' if ok else 'missing'}")
    raise typer.Exit(0 if ok else 1)
