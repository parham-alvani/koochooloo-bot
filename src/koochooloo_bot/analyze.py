"""Pure set-based analyses over fetched accounts and posts."""

from __future__ import annotations

from koochooloo_bot.models import Account, AnalysisResult, Post, PostStat


def _sorted_accounts(ids: frozenset[str], lookup: dict[str, Account]) -> list[Account]:
    """Resolve ids to accounts and sort them by username for stable output."""
    accounts = [lookup[user_id] for user_id in ids if user_id in lookup]
    return sorted(accounts, key=lambda account: account.username.lower())


def analyze(
    followers: dict[str, Account],
    following: dict[str, Account],
    posts: list[Post],
) -> AnalysisResult:
    """Compute the four analyses from followers, following, and posts.

    - ghost_followers: followers whose id appears in *no* post's liker set.
    - not_following_back: accounts we follow that don't follow us.
    - fans: accounts that follow us that we don't follow back.
    - per_post: total likes vs. likes coming from our own followers.
    """
    follower_ids = frozenset(followers)
    following_ids = frozenset(following)

    all_likers: frozenset[str] = frozenset()
    for post in posts:
        all_likers |= post.liker_ids
    likers_available = any(p.liker_ids for p in posts)

    ghost_ids = follower_ids - all_likers
    ghost_followers = _sorted_accounts(ghost_ids, followers) if likers_available else []

    not_following_back = _sorted_accounts(following_ids - follower_ids, following)
    fans = _sorted_accounts(follower_ids - following_ids, followers)

    per_post = [
        PostStat(
            code=post.code,
            url=post.url,
            taken_at=post.taken_at,
            total_likes=post.like_count,
            follower_likes=len(post.liker_ids & follower_ids),
        )
        for post in sorted(posts, key=lambda p: p.taken_at, reverse=True)
    ]

    return AnalysisResult(
        ghost_followers=ghost_followers,
        not_following_back=not_following_back,
        fans=fans,
        per_post=per_post,
        likers_available=likers_available,
    )
