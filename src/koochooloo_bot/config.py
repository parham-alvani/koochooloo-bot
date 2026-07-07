"""Configuration and credential loading."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

SESSION_FILE = Path("session.json")
DEFAULT_OUTPUT_DIR = Path("output")

# Human-like pacing between private-API calls (seconds). Instagrapi picks a
# random delay in this closed interval before each request.
DELAY_RANGE: list[int] = [1, 3]


class MissingCredentialsError(RuntimeError):
    """Raised when IG_USERNAME / IG_PASSWORD are not available."""


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
