"""Read-only data fetching — the boundary that narrows instagrapi models to ours."""

from __future__ import annotations

from collections.abc import Callable, Mapping

from instagrapi import Client
from instagrapi.types import UserShort

from koochooloo_bot.cache import FetchCache
from koochooloo_bot.models import Account, Post


def _account_from_user(user: UserShort) -> Account:
    """Narrow an instagrapi ``UserShort`` into our own ``Account``."""
    return Account(
        user_id=str(user.pk),
        username=str(user.username or "") or str(user.pk),
        full_name=str(user.full_name or ""),
        is_private=bool(user.is_private),
        is_verified=bool(user.is_verified),
    )


def _accounts_from_users(users: Mapping[str, UserShort]) -> dict[str, Account]:
    """Convert instagrapi's ``{user_id: UserShort}`` map into ``{user_id: Account}``."""
    return {str(user_id): _account_from_user(user) for user_id, user in users.items()}


def fetch_followers(client: Client, user_id: str) -> dict[str, Account]:
    """Return the account's followers keyed by user id."""
    return _accounts_from_users(client.user_followers(user_id))


def fetch_following(client: Client, user_id: str) -> dict[str, Account]:
    """Return the accounts the user follows, keyed by user id."""
    return _accounts_from_users(client.user_following(user_id))


def _fetch_likers(client: Client, media_id: str) -> list[Account]:
    return [_account_from_user(user) for user in client.media_likers(media_id)]


def _fetch_commenters(client: Client, media_id: str) -> list[Account]:
    return [
        _account_from_user(comment.user)
        for comment in client.media_comments(media_id, amount=0)
        if comment.user is not None
    ]


def fetch_posts(
    client: Client,
    user_id: str,
    max_posts: int,
    registry: dict[str, Account],
    cache: FetchCache,
    on_progress: Callable[[int, int], None] | None = None,
) -> list[Post]:
    """Fetch the user's own posts with the likers and commenters of each.

    Args:
        max_posts: cap on how many posts to inspect; ``0`` means all posts.
        registry: mutable ``{user_id: Account}`` map, extended in place with
            every liker/commenter seen (used to resolve non-follower likers).
        cache: disk cache keyed by media id; likers/comments are read from it
            when present and written as each post is fetched, making the run
            resumable if it is interrupted partway through.
        on_progress: optional ``(done, total)`` callback for progress display.

    This is the request-heavy step (a ``media_likers`` and a ``media_comments``
    call per post), so the client's ``delay_range`` pacing matters most here.
    """
    medias = client.user_medias(user_id, amount=max_posts)
    total = len(medias)
    posts: list[Post] = []
    for index, media in enumerate(medias, start=1):
        media_id = str(media.id)

        # Likers abort the run on failure (a throttle affects everything), but
        # posts fetched before the failure are already cached and will be reused.
        likers = cache.get_accounts(
            f"likers:{media_id}", lambda mid=media_id: _fetch_likers(client, mid)
        )

        # Comments can be disabled/restricted on a post; tolerate that without
        # caching an empty result (so it is retried next run).
        try:
            commenters = cache.get_accounts(
                f"comments:{media_id}", lambda mid=media_id: _fetch_commenters(client, mid)
            )
        except Exception:
            commenters = []

        for account in (*likers, *commenters):
            registry[account.user_id] = account

        posts.append(
            Post(
                media_id=media_id,
                code=str(media.code),
                taken_at=media.taken_at,
                like_count=int(media.like_count or 0),
                comment_count=int(media.comment_count or 0),
                liker_ids=frozenset(account.user_id for account in likers),
                commenter_ids=frozenset(account.user_id for account in commenters),
            )
        )
        if on_progress is not None:
            on_progress(index, total)
    return posts


def fetch_story_engagement(
    client: Client,
    user_id: str,
    registry: dict[str, Account],
) -> tuple[dict[str, int], int]:
    """Return ``({viewer_id: stories_viewed}, active_story_count)``.

    Only currently-active stories (24h window) are visible, so this is a bonus
    signal that is often empty. Extends ``registry`` with any story viewers.
    """
    stories = client.user_stories(user_id)
    viewer_counts: dict[str, int] = {}
    for story in stories:
        for viewer in client.story_viewers(int(story.pk)):
            viewer_id = str(viewer.pk)
            registry[viewer_id] = _account_from_user(viewer)
            viewer_counts[viewer_id] = viewer_counts.get(viewer_id, 0) + 1
    return viewer_counts, len(stories)
