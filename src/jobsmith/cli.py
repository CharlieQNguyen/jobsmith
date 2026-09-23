"""Command-line interface."""

from __future__ import annotations

import shutil
import subprocess
from datetime import date
from pathlib import Path
from typing import Annotated

import typer

from jobsmith import browser, credentials, store
from jobsmith.models import Account, Status

app = typer.Typer(no_args_is_help=True, help="Keep your job search in plain files.")
apps_cmd = typer.Typer(no_args_is_help=True, help="Job applications.")
creds_cmd = typer.Typer(no_args_is_help=True, help="Site credentials in the OS keychain.")
browser_cmd = typer.Typer(no_args_is_help=True, help="The Chrome that you log into and an agent drives.")
app.add_typer(apps_cmd, name="apps")
app.add_typer(creds_cmd, name="creds")
app.add_typer(browser_cmd, name="browser")

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


@creds_cmd.command("new")
def creds_new(
    host: Annotated[str, typer.Argument(help="Site host, e.g. acme.wd5.myworkdayjobs.com")],
    username: str,
    login_url: Annotated[str | None, typer.Option(help="Page with the sign-in form")] = None,
    data: DataOpt = None,
) -> None:
    """Generate a password, store it in the keychain, and copy it to the clipboard."""
    host = host.lower()
    if credentials.exists(host, username):
        typer.secho(f"{username}@{host} already has a stored password.", fg="yellow")
        raise typer.Exit(1)
    pw = credentials.generate_password()
    credentials.store(host, username, pw)
    store.upsert_account(
        store.data_dir(data),
        Account(host=host, username=username, created=date.today(), login_url=login_url),
    )
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


@browser_cmd.command("start")
def browser_start(data: DataOpt = None) -> None:
    """Launch Chrome with the jobsmith profile and a localhost DevTools port."""
    try:
        started = browser.start(store.data_dir(data))
    except browser.BrowserError as e:
        typer.secho(str(e), fg="red")
        raise typer.Exit(1) from e
    typer.echo(f"{'Started' if started else 'Already running'} — DevTools at {browser.endpoint()}")


@browser_cmd.command("stop")
def browser_stop(data: DataOpt = None) -> None:
    """Quit the Chrome that `browser start` launched."""
    typer.echo(
        "Stopped." if browser.stop(store.data_dir(data)) else "Not running (or not started by jobsmith)."
    )


@browser_cmd.command("status")
def browser_status() -> None:
    """Is the browser up?"""
    up = browser.is_running()
    typer.echo(f"{'Running' if up else 'Not running'} ({browser.endpoint()})")
    raise typer.Exit(0 if up else 1)


@app.command()
def login(
    host: Annotated[str, typer.Argument(help="Site host, as used with `creds new`")],
    username: Annotated[
        str | None, typer.Option("--user", "-u", help="Needed if the site has several")
    ] = None,
    url: Annotated[str | None, typer.Option(help="Sign-in page; saved for next time")] = None,
    data: DataOpt = None,
) -> None:
    """Sign in to a site in the jobsmith browser using the keychain password.

    Run this yourself — it's the step that handles your password. Starts the browser if needed.
    """
    root = store.data_dir(data)
    host = host.lower()
    account = store.find_account(root, host, username)
    if account is None:
        typer.secho(
            f"No single account for {host}"
            + (f" / {username}" if username else "")
            + " in accounts.yaml. Add one with `jobsmith creds new`, or pass --user.",
            fg="red",
        )
        raise typer.Exit(1)
    if url and url != account.login_url:
        account.login_url = url
        store.upsert_account(root, account)
    target = account.login_url or f"https://{host}/"
    try:
        browser.start(root)
        typer.echo(browser.login(host, account.username, target))
    except browser.BrowserError as e:
        typer.secho(str(e), fg="red")
        raise typer.Exit(1) from e
