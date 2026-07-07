"""Configuration and credential loading."""

from __future__ import annotations

import os
from dataclasses import dataclass
from http.cookiejar import MozillaCookieJar
from pathlib import Path

from dotenv import load_dotenv

SESSION_FILE = Path("session.json")
DEFAULT_OUTPUT_DIR = Path("output")

# Human-like pacing between private-API calls (seconds). Instagrapi picks a
# random delay in this closed interval before each request.
DELAY_RANGE: list[int] = [1, 3]


class MissingCredentialsError(RuntimeError):
    """Raised when IG_USERNAME / IG_PASSWORD are not available."""


class CookiesError(RuntimeError):
    """Raised when a cookies file is missing or has no Instagram sessionid."""


@dataclass(frozen=True, slots=True)
class Credentials:
    """Instagram login credentials loaded from the environment."""

    username: str
    password: str


def load_credentials() -> Credentials:
    """Load credentials from a local ``.env`` file (or the process environment).

    Raises:
        MissingCredentialsError: if either variable is absent or empty.
    """
    load_dotenv()
    username = os.getenv("IG_USERNAME", "").strip()
    password = os.getenv("IG_PASSWORD", "").strip()
    if not username or not password:
        raise MissingCredentialsError(
            "IG_USERNAME and IG_PASSWORD must be set. "
            "Copy .env.example to .env and fill in your credentials."
        )
    return Credentials(username=username, password=password)


def resolve_cookies_path(cli_path: Path | None) -> Path | None:
    """Return the cookies path from the CLI flag or IG_COOKIES_FILE, if any."""
    if cli_path is not None:
        return cli_path
    load_dotenv()
    env_path = os.getenv("IG_COOKIES_FILE", "").strip()
    return Path(env_path) if env_path else None


def sessionid_from_cookies(path: Path) -> str:
    """Extract the Instagram ``sessionid`` from a Netscape cookies.txt file.

    Reuses an existing browser session (e.g. the gallery-dl export), which
    avoids a password login and the challenges that come with it.

    Raises:
        CookiesError: if the file is missing or has no Instagram sessionid.
    """
    if not path.exists():
        raise CookiesError(f"Cookies file not found: {path}")
    jar = MozillaCookieJar(str(path))
    jar.load(ignore_discard=True, ignore_expires=True)
    for cookie in jar:
        if cookie.name == "sessionid" and "instagram" in (cookie.domain or ""):
            if not cookie.value:
                break
            return cookie.value
    raise CookiesError(f"No Instagram 'sessionid' cookie found in {path}")


def resolve_whitelist_path(cli_path: Path | None) -> Path | None:
    """Return the whitelist path from the CLI flag or IG_WHITELIST_FILE, if any."""
    if cli_path is not None:
        return cli_path
    load_dotenv()
    env_path = os.getenv("IG_WHITELIST_FILE", "").strip()
    return Path(env_path) if env_path else None


def load_whitelist(path: Path | None) -> frozenset[str]:
    """Load lowercased usernames to exclude from the ghost report.

    One username per line; blank lines and ``#`` comments are ignored. A leading
    ``@`` is stripped. Returns an empty set when no path is given.

    Raises:
        CookiesError: reused as a generic config error if the file is missing.
    """
    if path is None:
        return frozenset()
    if not path.exists():
        raise CookiesError(f"Whitelist file not found: {path}")
    names: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        entry = line.strip().lstrip("@").lower()
        if entry and not entry.startswith("#"):
            names.add(entry)
    return frozenset(names)
