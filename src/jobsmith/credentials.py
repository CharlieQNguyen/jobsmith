"""Site credentials kept in the OS keychain via `keyring`.

Passwords never touch the data directory. The data directory only records which
accounts exist (see `accounts.yaml`), so the repo stays safe to sync.
"""

from __future__ import annotations

import secrets
import string

import keyring

SERVICE_PREFIX = "jobsmith"
ALPHABET = string.ascii_letters + string.digits + "!@#$%^&*-_=+"


def _service(host: str) -> str:
    return f"{SERVICE_PREFIX}:{host.lower()}"


def generate_password(length: int = 24) -> str:
    """Random password that satisfies the usual upper/lower/digit/symbol rules."""
    while True:
        pw = "".join(secrets.choice(ALPHABET) for _ in range(length))
        if (
            any(c.islower() for c in pw)
            and any(c.isupper() for c in pw)
            and any(c.isdigit() for c in pw)
            and any(not c.isalnum() for c in pw)
        ):
            return pw


def store(host: str, username: str, password: str) -> None:
    keyring.set_password(_service(host), username, password)


def get(host: str, username: str) -> str | None:
    return keyring.get_password(_service(host), username)


def exists(host: str, username: str) -> bool:
    return get(host, username) is not None


def delete(host: str, username: str) -> None:
    keyring.delete_password(_service(host), username)
