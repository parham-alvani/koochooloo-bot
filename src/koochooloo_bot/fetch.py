"""Read-only data fetching — the boundary that narrows instagrapi models to ours."""

from __future__ import annotations

from collections.abc import Callable, Mapping

from instagrapi import Client
from instagrapi.types import UserShort

from koochooloo_bot.models import Account, Post


def _accounts_from_users(users: Mapping[str, UserShort]) -> dict[str, Account]:
    """Convert instagrapi's ``{user_id: UserShort}`` map into ``{user_id: Account}``."""
    accounts: dict[str, Account] = {}
    for user_id, user in users.items():
        username = str(user.username or "") or str(user_id)
        accounts[str(user_id)] = Account(user_id=str(user_id), username=username)
    return accounts


def fetch_followers(client: Client, user_id: str) -> dict[str, Account]:
    """Return the account's followers keyed by user id."""
    return _accounts_from_users(client.user_followers(user_id))


def fetch_following(client: Client, user_id: str) -> dict[str, Account]:
    """Return the accounts the user follows, keyed by user id."""
    return _accounts_from_users(client.user_following(user_id))


def fetch_posts(
    client: Client,
    user_id: str,
    max_posts: int,
    on_progress: Callable[[int, int], None] | None = None,
) -> list[Post]:
    """Fetch the user's own posts together with the likers of each post.

    Args:
        max_posts: cap on how many posts to inspect; ``0`` means all posts.
        on_progress: optional callback invoked as ``(done, total)`` after each
            post's likers are fetched, for progress display.

    This is the request-heavy step (one ``media_likers`` call per post), so the
    client's ``delay_range`` pacing matters most here.
    """
    medias = client.user_medias(user_id, amount=max_posts)
    total = len(medias)
    posts: list[Post] = []
    for index, media in enumerate(medias, start=1):
        media_id = str(media.id)
        likers = client.media_likers(media_id)
        liker_ids = frozenset(str(user.pk) for user in likers)
        posts.append(
            Post(
                media_id=media_id,
                code=str(media.code),
                taken_at=media.taken_at,
                like_count=int(media.like_count or 0),
                liker_ids=liker_ids,
            )
        )
        if on_progress is not None:
            on_progress(index, total)
    return posts
