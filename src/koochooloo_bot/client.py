"""Login and session management for the Instagram private API."""

from __future__ import annotations

import typer
from instagrapi import Client
from instagrapi.exceptions import TwoFactorRequired

from koochooloo_bot.config import DELAY_RANGE, SESSION_FILE, Credentials


def _login(client: Client, creds: Credentials) -> None:
    """Perform a login, prompting interactively if 2FA is required."""
    try:
        client.login(creds.username, creds.password)
    except TwoFactorRequired:
        code = typer.prompt("Two-factor code required — enter the code from your app/SMS")
        client.login(creds.username, creds.password, verification_code=code.strip())


def get_client(creds: Credentials) -> Client:
    """Return a logged-in client, reusing a saved session when possible.

    A saved session avoids repeated full logins, which is the single most
    important thing we can do to keep the account out of trouble. If reusing the
    session fails (expired/invalidated), we fall back to a fresh login and
    persist the new session for next time.
    """
    client = Client()
    client.delay_range = DELAY_RANGE

    if SESSION_FILE.exists():
        client.load_settings(SESSION_FILE)
        try:
            _login(client, creds)
            # Cheap authenticated call to confirm the session is actually valid.
            client.get_timeline_feed()
            return client
        except Exception:
            typer.secho(
                "Saved session was invalid — logging in fresh.",
                fg=typer.colors.YELLOW,
            )
            client = Client()
            client.delay_range = DELAY_RANGE

    _login(client, creds)
    client.dump_settings(SESSION_FILE)
    return client


def get_client_by_sessionid(sessionid: str) -> Client:
    """Return a client authenticated with an existing browser ``sessionid``.

    This reuses a live session (e.g. exported from a browser via gallery-dl),
    so there is no password login and no login challenge. The resolved session
    is persisted to ``session.json`` for subsequent runs.
    """
    client = Client()
    client.delay_range = DELAY_RANGE
    client.login_by_sessionid(sessionid)
    client.dump_settings(SESSION_FILE)
    return client
