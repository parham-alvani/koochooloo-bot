"""Typed domain models — the library-agnostic core the rest of the code speaks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class Account:
    """A minimal Instagram account reference (a follower/following/liker)."""

    user_id: str
    username: str
    full_name: str = ""
    is_private: bool = False
    is_verified: bool = False

    @property
    def profile_url(self) -> str:
        return f"https://www.instagram.com/{self.username}/"


@dataclass(frozen=True, slots=True)
class Post:
    """One of the logged-in user's own posts, plus who engaged with it."""

    media_id: str
    code: str
    taken_at: datetime
    like_count: int
    comment_count: int
    liker_ids: frozenset[str]
    commenter_ids: frozenset[str]

    @property
    def url(self) -> str:
        return f"https://www.instagram.com/p/{self.code}/"


@dataclass(frozen=True, slots=True)
class PostStat:
    """Per-post engagement restricted to the account's own followers."""

    code: str
    url: str
    taken_at: datetime
    total_likes: int
    follower_likes: int
    follower_comments: int


@dataclass(frozen=True, slots=True)
class EngagementScore:
    """How much a single follower engaged across all analyzed posts/stories."""

    account: Account
    likes: int
    comments: int
    story_views: int

    @property
    def total(self) -> int:
        return self.likes + self.comments + self.story_views


@dataclass(frozen=True, slots=True)
class SuspiciousFollower:
    """A follower flagged by cheap, request-free heuristics as possibly fake."""

    account: Account
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FollowerDelta:
    """Change in followers since the previous snapshot."""

    new_followers: list[Account]
    lost_followers: list[Account]
    has_baseline: bool
    baseline_at: str | None


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    """Everything the analyses produce, ready to report."""

    ghost_followers: list[Account]
    ghost_following: list[Account]
    not_following_back: list[Account]
    fans: list[Account]
    suspicious_followers: list[SuspiciousFollower]
    non_follower_likers: list[Account]
    engagement: list[EngagementScore]
    per_post: list[PostStat]
    delta: FollowerDelta
    engagement_available: bool
    """False when Instagram returned no like/comment/story data (ghost detection degraded)."""
    stories_checked: int
