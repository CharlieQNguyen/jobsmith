"""Command-line interface."""

from __future__ import annotations

import shutil
import subprocess
from datetime import date
from pathlib import Path
from typing import Annotated
from urllib.parse import urlparse

import typer

from jobsmith import ats, browser, credentials, resume, scaffold, store
from jobsmith.models import Account, Application, Event, Status

app = typer.Typer(no_args_is_help=True, help="Keep your job search in plain files.")
apps_cmd = typer.Typer(no_args_is_help=True, help="Job applications.")
creds_cmd = typer.Typer(no_args_is_help=True, help="Site credentials in the OS keychain.")
browser_cmd = typer.Typer(no_args_is_help=True, help="The Chrome that you log into and an agent drives.")
resume_cmd = typer.Typer(no_args_is_help=True, help="Resumes (JSON Resume files in resumes/).")
app.add_typer(apps_cmd, name="apps")
app.add_typer(creds_cmd, name="creds")
app.add_typer(browser_cmd, name="browser")
app.add_typer(resume_cmd, name="resume")

DataOpt = Annotated[
    Path | None,
    typer.Option("--data", "-d", help="Data directory (default: nearest data repo, $JOBSMITH_DATA, cwd)"),
]


@app.command()
def init(
    directory: Annotated[Path, typer.Argument(help="Data repo to create or refresh")] = Path("."),
    force: Annotated[bool, typer.Option(help="Overwrite jobsmith-owned wiring (never your data)")] = False,
    submodule: Annotated[bool, typer.Option(help="Add jobsmith as a submodule at tools/jobsmith")] = True,
) -> None:
    """Create a private data repo wired up for jobsmith and Claude Code, or refresh one."""
    r = scaffold.init(directory, force=force, submodule=submodule)
    for label, paths, color in [
        ("created", r.created, "green"),
        ("updated", r.updated, "yellow"),
        ("removed", r.removed, "yellow"),
        ("kept", r.kept, None),
    ]:
        for p in paths:
            typer.secho(f"  {label:<8} {p}", fg=color)
    for note in r.notes:
        typer.echo(f"  • {note}")
    if r.kept and not force:
        typer.echo("Kept files differ from the template; `jobsmith init --force` refreshes wiring files.")
    typer.echo("Next: fill in profile/profile.yaml, then open Claude Code in this directory.")


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


def _resolve(root: Path, query: str) -> str:
    try:
        return store.resolve_application(root, query)
    except LookupError as e:
        typer.secho(str(e), fg="red")
        raise typer.Exit(1) from e


def _when(text: str) -> date:
    try:
        return store.parse_date(text)
    except ValueError as e:
        typer.secho(f"Bad date {text!r}: use today, +3d, +2w or YYYY-MM-DD", fg="red")
        raise typer.Exit(1) from e


@apps_cmd.command("add")
def apps_add(
    company: Annotated[str, typer.Option(help="Employer name")],
    role: Annotated[str, typer.Option(help="Job title as posted")],
    url: Annotated[str | None, typer.Option(help="Posting URL")] = None,
    status: Annotated[Status, typer.Option(help="Starting status")] = Status.INTERESTED,
    data: DataOpt = None,
) -> None:
    """Start tracking an application. Prints its slug."""
    root = store.data_dir(data)
    slug = store.slugify(company, role)
    if slug in store.load_applications(root):
        typer.secho(f"Already tracked: {slug}", fg="yellow")
        raise typer.Exit(1)
    site = None
    if url and (host := urlparse(url).hostname):
        detected = ats.for_host(host)
        site = None if detected is ats.GENERIC else detected.name
    today = date.today()
    app_ = Application(company=company, role=role, url=url, ats=site)
    app_.events.append(Event(when=today, what="Started tracking"))
    app_.set_status(status, today)
    store.write_application(root, app_, slug)
    typer.echo(slug)


@apps_cmd.command("update")
def apps_update(
    query: Annotated[str, typer.Argument(help="Slug, or words matching company/role")],
    status: Annotated[Status | None, typer.Option(help="New status (logged as an event)")] = None,
    event: Annotated[str | None, typer.Option(help="Something that happened, e.g. 'Phone screen'")] = None,
    on: Annotated[str, typer.Option(help="When it happened: today, +3d, YYYY-MM-DD")] = "today",
    followup: Annotated[str | None, typer.Option(help="Next follow-up: +7d, YYYY-MM-DD, or none")] = None,
    resume: Annotated[str | None, typer.Option(help="Resume file sent")] = None,
    cover_letter: Annotated[str | None, typer.Option(help="Cover letter sent")] = None,
    data: DataOpt = None,
) -> None:
    """Update an application's status, log an event, or set the next follow-up."""
    root = store.data_dir(data)
    slug = _resolve(root, query)
    a = store.read_application(root / "applications" / f"{slug}.md")
    when = _when(on)
    if status:
        a.set_status(status, when)
    if event:
        a.events.append(Event(when=when, what=event))
    if followup:
        a.next_followup = None if followup.lower() == "none" else _when(followup)
    if resume:
        a.resume = resume
    if cover_letter:
        a.cover_letter = cover_letter
    store.write_application(root, a, slug)
    nxt = f", follow up {a.next_followup}" if a.next_followup else ""
    typer.echo(f"{slug}: {a.status}{nxt}")


@apps_cmd.command("show")
def apps_show(query: str, data: DataOpt = None) -> None:
    """Print an application's file."""
    root = store.data_dir(data)
    path = root / "applications" / f"{_resolve(root, query)}.md"
    typer.echo(f"# {path.relative_to(root)}\n")
    typer.echo(path.read_text())


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
def browser_start() -> None:
    """Launch Chrome with the jobsmith profile and a localhost DevTools port."""
    try:
        started = browser.start()
    except browser.BrowserError as e:
        typer.secho(str(e), fg="red")
        raise typer.Exit(1) from e
    typer.echo(f"{'Started' if started else 'Already running'} — DevTools at {browser.endpoint()}")


@browser_cmd.command("stop")
def browser_stop() -> None:
    """Quit the Chrome that `browser start` launched."""
    typer.echo("Stopped." if browser.stop() else "Not running (or not started by jobsmith).")


@browser_cmd.command("status")
def browser_status() -> None:
    """Is the browser up?"""
    up = browser.is_running()
    typer.echo(f"{'Running' if up else 'Not running'} ({browser.endpoint()})")
    raise typer.Exit(0 if up else 1)


@resume_cmd.command("render")
def resume_render(
    file: Annotated[Path | None, typer.Argument(help="JSON Resume file [default: resumes/base.json]")] = None,
    out: Annotated[
        Path | None, typer.Option("--out", "-o", help="PDF to write [default: beside the JSON]")
    ] = None,
    full_roles: Annotated[
        int, typer.Option(help="Roles shown with highlights; older ones get one line. 0 = all")
    ] = 5,
    bullets: Annotated[int, typer.Option(help="Highlights per role. 0 = all")] = 2,
    accent: Annotated[str, typer.Option(help="Accent colour for the name line and headings")] = "#2c6a57",
    html: Annotated[bool, typer.Option("--html", help="Also write the HTML beside the PDF")] = False,
    data: DataOpt = None,
) -> None:
    """Render a resume to a one-page PDF (the compact layout) with headless Chrome."""
    root = store.data_dir(data)
    src = file or root / "resumes" / "base.json"
    if not src.exists() and not src.is_absolute() and (root / src).exists():
        src = root / src
    target = out or src.with_suffix(".pdf")
    try:
        page = resume.to_html(
            resume.load(src), resume.Layout(full_roles=full_roles, bullets=bullets, accent=accent)
        )
        if html:
            target.with_suffix(".html").write_text(page)
        pages = resume.to_pdf(page, target)
    except (OSError, resume.ResumeError) as e:
        typer.secho(str(e), fg="red")
        raise typer.Exit(1) from e
    shown = target.relative_to(root) if target.is_relative_to(root) else target
    typer.secho(f"Wrote {shown} ({pages} page{'s' if pages != 1 else ''})", fg="green")
    if pages > 1:
        typer.secho(
            "The compact layout is meant for one page. Try --bullets 1, a lower --full-roles, "
            "or shorter highlights.",
            fg="yellow",
        )


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
        browser.start()
        typer.echo(browser.login(host, account.username, target))
    except browser.BrowserError as e:
        typer.secho(str(e), fg="red")
        raise typer.Exit(1) from e
