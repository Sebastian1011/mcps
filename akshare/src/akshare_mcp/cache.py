"""Disk-backed response cache with tiered TTLs.

Backed by diskcache (SQLite under the hood) so it's a single dependency,
safe across threads/processes, and trivially persisted by mounting
CACHE_DIR onto a Docker volume. We cache the already-normalized payload
(columns/rows), never a raw pandas DataFrame, so a pandas version bump in a
future image can't break unpickling of old cache entries.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import diskcache

from akshare_mcp.config import Settings

_AKSHARE_VERSION: str | None = None


def _akshare_version() -> str:
    global _AKSHARE_VERSION
    if _AKSHARE_VERSION is None:
        import akshare

        _AKSHARE_VERSION = getattr(akshare, "__version__", "unknown")
    return _AKSHARE_VERSION


def make_key(namespace: str, **parts: Any) -> str:
    """Stable cache key: namespace + akshare version + sorted params hash.

    Including the akshare version means an akshare upgrade that changes a
    function's output shape naturally invalidates old cache entries instead
    of serving stale/incompatible data.
    """
    payload = json.dumps({"akshare_version": _akshare_version(), **parts}, sort_keys=True, default=str)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"{namespace}:{digest}"


def today(settings: Settings) -> date:
    return datetime.now(tz=settings.tz).date()


def history_cache_tier(settings: Settings, end: str | None) -> tuple[str, int]:
    """Decide the TTL tier for a history-bars query.

    "closed": caller gave an explicit `end` that is strictly before today
    (their tz) -- that date range can never produce new bars, so it's safe
    to cache for a long time (default 7 days).
    "open": `end` is missing or covers today/the future (still-updating
    data) -- short TTL (default 1h) so we don't serve yesterday's snapshot
    of an in-progress trading session for too long.
    """
    if end:
        try:
            end_date = datetime.strptime(end[:10], "%Y-%m-%d").date()
        except ValueError:
            end_date = None
        if end_date is not None and end_date < today(settings):
            return "closed", settings.cache_ttl_closed
    return "open", settings.cache_ttl_open


class ResponseCache:
    """Thin diskcache wrapper. get()/set() are synchronous (diskcache's
    SQLite backend is local and fast enough that offloading to a worker
    thread isn't worth the complexity for a server this size); callers on
    the async request path call these directly.
    """

    def __init__(self, settings: Settings):
        self._settings = settings
        self._cache = diskcache.Cache(settings.cache_dir, size_limit=settings.cache_size_limit)

    def get(self, key: str) -> Any | None:
        return self._cache.get(key, default=None)

    def set(self, key: str, value: Any, ttl: int) -> None:
        self._cache.set(key, value, expire=ttl)

    def close(self) -> None:
        self._cache.close()


_cache: ResponseCache | None = None


def get_cache(settings: Settings) -> ResponseCache:
    global _cache
    if _cache is None:
        _cache = ResponseCache(settings)
    return _cache
