"""Typed domain models — the library-agnostic core the rest of the code speaks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class Account:
    """A minimal Instagram account reference (a follower/following/liker)."""

    user_id: str
    username: str

    @property
    def profile_url(self) -> str:
        return f"https://www.instagram.com/{self.username}/"


@dataclass(frozen=True, slots=True)
class Post:
    """One of the logged-in user's own media posts, plus who liked it."""

    media_id: str
    code: str
    taken_at: datetime
    like_count: int
    liker_ids: frozenset[str]

    @property
    def url(self) -> str:
        return f"https://www.instagram.com/p/{self.code}/"


@dataclass(frozen=True, slots=True)
class PostStat:
    """Per-post engagement, restricted to the account's own followers."""

    code: str
    url: str
    taken_at: datetime
    total_likes: int
    follower_likes: int


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    """Everything the four analyses produce, ready to report."""

    ghost_followers: list[Account]
    not_following_back: list[Account]
    fans: list[Account]
    per_post: list[PostStat]
    likers_available: bool
    """False when Instagram returned no liker data (ghost detection degraded)."""
