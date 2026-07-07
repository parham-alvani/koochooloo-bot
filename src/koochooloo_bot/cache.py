"""Disk-persisted cache for expensive per-media fetches, backed by DiskCache.

DiskCache stores entries in a process-safe SQLite database that survives
restarts, so likers/comments fetched in one run are reused by the next. Beyond
saving requests, this makes runs **resumable**: because each post's data is
written to disk as it is fetched, a run that dies partway through (e.g. an
Instagram rate limit) leaves the completed posts cached, and the next run skips
straight past them instead of re-fetching from scratch.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from typing import Any

from diskcache import Cache

from koochooloo_bot.models import Account

# Bump when the cached shape changes, to invalidate stale entries cleanly.
CACHE_VERSION = "v1"


def _account_from_dict(data: dict[str, Any]) -> Account:
    """Rebuild an Account from a cached dict, tolerant of added fields."""
    return Account(
        user_id=str(data["user_id"]),
        username=str(data["username"]),
        full_name=str(data.get("full_name", "")),
        is_private=bool(data.get("is_private", False)),
        is_verified=bool(data.get("is_verified", False)),
    )


class FetchCache:
    """A thin, typed wrapper over DiskCache for lists of accounts.

    Use as a context manager so the underlying SQLite handle is closed.
    """

    def __init__(
        self,
        directory: Path,
        ttl_seconds: int,
        *,
        enabled: bool = True,
        refresh: bool = False,
    ) -> None:
        self._cache: Cache | None = Cache(str(directory)) if enabled else None
        self._ttl = ttl_seconds
        self._refresh = refresh
        self.hits = 0
        self.misses = 0

    def get_accounts(self, key: str, fetch: Callable[[], list[Account]]) -> list[Account]:
        """Return cached accounts for ``key``, or fetch, cache, and return them.

        On a cache miss the fetcher runs; if it raises, nothing is cached and the
        exception propagates (so a transient error never poisons the cache).
        """
        namespaced = f"{CACHE_VERSION}:{key}"
        if self._cache is not None and not self._refresh:
            cached = self._cache.get(namespaced)
            if cached is not None:
                self.hits += 1
                return [_account_from_dict(item) for item in cached]

        accounts = fetch()
        self.misses += 1
        if self._cache is not None:
            self._cache.set(namespaced, [asdict(a) for a in accounts], expire=self._ttl)
        return accounts

    def close(self) -> None:
        if self._cache is not None:
            self._cache.close()

    def __enter__(self) -> FetchCache:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()
