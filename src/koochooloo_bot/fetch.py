"""Read-only data fetching — the boundary that narrows instagrapi models to ours."""

from __future__ import annotations

from collections.abc import Callable, Mapping

from instagrapi import Client
from instagrapi.types import UserShort

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


def fetch_posts(
    client: Client,
    user_id: str,
    max_posts: int,
    registry: dict[str, Account],
    on_progress: Callable[[int, int], None] | None = None,
) -> list[Post]:
    """Fetch the user's own posts with the likers and commenters of each.

    Args:
        max_posts: cap on how many posts to inspect; ``0`` means all posts.
        registry: mutable ``{user_id: Account}`` map, extended in place with
            every liker/commenter seen (used to resolve non-follower likers).
        on_progress: optional ``(done, total)`` callback for progress display.

    This is the request-heavy step (a ``media_likers`` and a ``media_comments``
    call per post), so the client's ``delay_range`` pacing matters most here.
    """
    medias = client.user_medias(user_id, amount=max_posts)
    total = len(medias)
    posts: list[Post] = []
    for index, media in enumerate(medias, start=1):
        media_id = str(media.id)

        liker_ids: set[str] = set()
        for user in client.media_likers(media_id):
            registry[str(user.pk)] = _account_from_user(user)
            liker_ids.add(str(user.pk))

        commenter_ids: set[str] = set()
        try:
            comments = client.media_comments(media_id, amount=0)
        except Exception:
            # Comments can be disabled/restricted on a post; don't abort the run.
            comments = []
        for comment in comments:
            if comment.user is None:
                continue
            registry[str(comment.user.pk)] = _account_from_user(comment.user)
            commenter_ids.add(str(comment.user.pk))

        posts.append(
            Post(
                media_id=media_id,
                code=str(media.code),
                taken_at=media.taken_at,
                like_count=int(media.like_count or 0),
                comment_count=int(media.comment_count or 0),
                liker_ids=frozenset(liker_ids),
                commenter_ids=frozenset(commenter_ids),
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
