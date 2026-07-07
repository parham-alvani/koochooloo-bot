"""Follower snapshots and unfollower diffs (feature: who unfollowed me).

Each run writes a timestamped ``followers-*.json`` snapshot. Comparing this
run's followers against the most recent prior snapshot yields new followers and
lost followers (unfollowers). Persist the snapshot directory across runs (e.g.
commit it into the stats repo) to build real history over time.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from koochooloo_bot.models import Account, FollowerDelta

_SNAPSHOT_GLOB = "followers-*.json"


def _snapshot_name(now: datetime) -> str:
    return f"followers-{now.strftime('%Y%m%dT%H%M%S')}.json"


def load_latest_snapshot(snapshot_dir: Path) -> tuple[dict[str, str], str] | None:
    """Return ``({user_id: username}, created_iso)`` from the newest snapshot, or None.

    Snapshots are named by timestamp, so lexical ordering is chronological.
    """
    if not snapshot_dir.exists():
        return None
    files = sorted(snapshot_dir.glob(_SNAPSHOT_GLOB))
    if not files:
        return None
    data = json.loads(files[-1].read_text(encoding="utf-8"))
    followers: dict[str, str] = {str(k): str(v) for k, v in data.get("followers", {}).items()}
    created = str(data.get("created", ""))
    return followers, created


def save_snapshot(snapshot_dir: Path, followers: dict[str, Account], now: datetime) -> Path:
    """Write the current followers to a new timestamped snapshot file."""
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    path = snapshot_dir / _snapshot_name(now)
    payload = {
        "created": now.isoformat(),
        "followers": {user_id: account.username for user_id, account in followers.items()},
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def compute_delta(
    baseline: tuple[dict[str, str], str] | None,
    current: dict[str, Account],
) -> FollowerDelta:
    """Diff the current followers against a baseline snapshot.

    New followers are resolved from the current account map (rich data). Lost
    followers only exist in the baseline, so they carry just id + username.
    """
    if baseline is None:
        return FollowerDelta(
            new_followers=[], lost_followers=[], has_baseline=False, baseline_at=None
        )

    previous, created = baseline
    current_ids = frozenset(current)
    previous_ids = frozenset(previous)

    new_followers = sorted(
        (current[user_id] for user_id in current_ids - previous_ids),
        key=lambda account: account.username.lower(),
    )
    lost_followers = sorted(
        (
            Account(user_id=user_id, username=previous[user_id])
            for user_id in previous_ids - current_ids
        ),
        key=lambda account: account.username.lower(),
    )
    return FollowerDelta(
        new_followers=new_followers,
        lost_followers=lost_followers,
        has_baseline=True,
        baseline_at=created or None,
    )
