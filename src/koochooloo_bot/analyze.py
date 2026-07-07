"""Pure analyses over fetched accounts, posts, and story engagement."""

from __future__ import annotations

from koochooloo_bot.models import (
    Account,
    AnalysisResult,
    EngagementScore,
    FollowerDelta,
    Post,
    PostStat,
    SuspiciousFollower,
)


def _sorted_accounts(ids: frozenset[str], lookup: dict[str, Account]) -> list[Account]:
    """Resolve ids to accounts and sort them by username for stable output."""
    accounts = [lookup[user_id] for user_id in ids if user_id in lookup]
    return sorted(accounts, key=lambda account: account.username.lower())


def _suspicion_reasons(account: Account) -> tuple[str, ...]:
    """Cheap, request-free heuristics flagging a possibly-fake follower.

    Uses only fields already present on the follower list — no extra API calls.
    Verified accounts are never flagged. Conservative on purpose: a strong
    numeric-handle signal, or a missing display name paired with a numeric
    handle, is required.
    """
    if account.is_verified:
        return ()

    digits = sum(char.isdigit() for char in account.username)
    digit_ratio = digits / max(len(account.username), 1)
    no_name = not account.full_name.strip()

    reasons: list[str] = []
    if digit_ratio >= 0.5:
        reasons.append("username is mostly digits")
    if no_name:
        reasons.append("no display name")

    strong = digit_ratio >= 0.5 or (no_name and digit_ratio >= 0.3)
    return tuple(reasons) if (strong and reasons) else ()


def analyze(
    followers: dict[str, Account],
    following: dict[str, Account],
    posts: list[Post],
    registry: dict[str, Account],
    story_viewer_counts: dict[str, int],
    delta: FollowerDelta,
    stories_checked: int,
    whitelist: frozenset[str],
) -> AnalysisResult:
    """Compute every analysis from the fetched data.

    - ghost_followers: followers who never liked, commented, or viewed a story
      (excluding whitelisted usernames).
    - not_following_back / fans: the two non-mutual sets.
    - suspicious_followers: heuristic fake-account flags.
    - non_follower_likers: accounts that liked posts but don't follow you.
    - engagement: per-follower like/comment/story-view scores (engaged only).
    - per_post: total vs. follower likes/comments per post.
    """
    follower_ids = frozenset(followers)
    following_ids = frozenset(following)

    likers: set[str] = set()
    commenters: set[str] = set()
    for post in posts:
        likers |= post.liker_ids
        commenters |= post.commenter_ids
    story_viewers = frozenset(story_viewer_counts)
    engaged = frozenset(likers) | frozenset(commenters) | story_viewers
    engagement_available = bool(engaged)

    whitelisted = {
        user_id for user_id, acc in followers.items() if acc.username.lower() in whitelist
    }
    ghost_ids = follower_ids - engaged - frozenset(whitelisted)
    ghost_followers = _sorted_accounts(ghost_ids, followers) if engagement_available else []

    not_following_back = _sorted_accounts(following_ids - follower_ids, following)
    fans = _sorted_accounts(follower_ids - following_ids, followers)

    non_follower_liker_ids = frozenset(likers) - follower_ids
    non_follower_likers = _sorted_accounts(non_follower_liker_ids, registry)

    suspicious_followers = sorted(
        (
            SuspiciousFollower(account=account, reasons=reasons)
            for account in followers.values()
            if (reasons := _suspicion_reasons(account))
        ),
        key=lambda s: s.account.username.lower(),
    )

    engagement = _engagement_scores(followers, posts, story_viewer_counts)

    per_post = [
        PostStat(
            code=post.code,
            url=post.url,
            taken_at=post.taken_at,
            total_likes=post.like_count,
            follower_likes=len(post.liker_ids & follower_ids),
            follower_comments=len(post.commenter_ids & follower_ids),
        )
        for post in sorted(posts, key=lambda p: p.taken_at, reverse=True)
    ]

    return AnalysisResult(
        ghost_followers=ghost_followers,
        not_following_back=not_following_back,
        fans=fans,
        suspicious_followers=suspicious_followers,
        non_follower_likers=non_follower_likers,
        engagement=engagement,
        per_post=per_post,
        delta=delta,
        engagement_available=engagement_available,
        stories_checked=stories_checked,
    )


def _engagement_scores(
    followers: dict[str, Account],
    posts: list[Post],
    story_viewer_counts: dict[str, int],
) -> list[EngagementScore]:
    """Rank followers by total engagement (likes + comments + story views)."""
    scores: list[EngagementScore] = []
    for user_id, account in followers.items():
        likes = sum(1 for post in posts if user_id in post.liker_ids)
        comments = sum(1 for post in posts if user_id in post.commenter_ids)
        story_views = story_viewer_counts.get(user_id, 0)
        if likes + comments + story_views == 0:
            continue
        scores.append(
            EngagementScore(
                account=account, likes=likes, comments=comments, story_views=story_views
            )
        )
    scores.sort(key=lambda s: (-s.total, s.account.username.lower()))
    return scores
