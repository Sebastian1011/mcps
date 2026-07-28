"""Source-aware rate limiting and retry around blocking akshare calls.

Empirically (see plan doc), East Money's push2*.eastmoney.com hosts soft-ban
bursty clients: a dozen or so requests in quick succession start failing
with connection-reset errors for roughly a minute, even though the same URL
via curl succeeds throughout. akshare's own functions have no rate limiting
at all. Without a limiter here, a single agent conversation that asks a few
market-wide questions in a row would reliably trip this and see cascading
failures.

Every akshare call in registry.py goes through `call()` below, tagged with
which upstream host group it hits, so unrelated sources (sina, xueqiu, SGE)
aren't held back by East Money's throttle and vice versa.
"""

from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass, field

import anyio

from akshare_mcp.config import Settings

# Transient network failures worth retrying. akshare wraps requests/pandas,
# so both requests' exceptions and JSON-decode failures on truncated
# responses show up here.
_RETRYABLE = (
    ConnectionError,
    TimeoutError,
    OSError,
)


class SourceThrottle:
    """Per-source-group concurrency cap + minimum inter-request spacing."""

    def __init__(self, concurrency: int, min_interval: float):
        self._sem = asyncio.Semaphore(concurrency)
        self._min_interval = min_interval
        self._lock = asyncio.Lock()
        self._last_call = 0.0

    async def wait_turn(self) -> None:
        async with self._lock:
            now = time.monotonic()
            wait = self._min_interval - (now - self._last_call)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_call = time.monotonic()


@dataclass
class Throttles:
    settings: Settings
    _groups: dict[str, SourceThrottle] = field(default_factory=dict)

    def get(self, source: str) -> SourceThrottle:
        if source not in self._groups:
            min_interval = (
                self.settings.min_interval_eastmoney
                if source == "eastmoney"
                else self.settings.min_interval_default
            )
            self._groups[source] = SourceThrottle(self.settings.source_concurrency, min_interval)
        return self._groups[source]


_throttles: Throttles | None = None


def get_throttles(settings: Settings) -> Throttles:
    global _throttles
    if _throttles is None:
        _throttles = Throttles(settings)
    return _throttles


class UpstreamError(Exception):
    """Raised after retries are exhausted calling an upstream data source."""


async def call(settings: Settings, source: str, fn, *args, **kwargs):
    """Run a blocking akshare function with source-group throttling and
    exponential-backoff retry. `fn` is called in a worker thread so it never
    blocks the event loop.
    """
    throttle = get_throttles(settings).get(source)
    last_exc: Exception | None = None

    for attempt in range(settings.max_retries):
        async with throttle._sem:
            await throttle.wait_turn()
            try:
                return await anyio.to_thread.run_sync(lambda: fn(*args, **kwargs))
            except _RETRYABLE as exc:
                last_exc = exc
            except Exception as exc:  # noqa: BLE001 - akshare raises all sorts (ValueError, KeyError on bad symbols, etc.)
                # Only retry errors that look like transient upstream issues;
                # anything else (bad symbol, akshare bug) should surface
                # immediately instead of being retried 3x for nothing.
                message = str(exc).lower()
                if any(hint in message for hint in ("connection", "timeout", "reset", "proxy", "disconnected")):
                    last_exc = exc
                else:
                    raise

        if attempt < settings.max_retries - 1:
            delay = (2**attempt) + random.uniform(0.2, 0.8)
            await asyncio.sleep(delay)

    raise UpstreamError(
        f"data source {source!r} failed after {settings.max_retries} attempts "
        f"(likely rate-limited upstream, retry later or rely on cached data): {last_exc}"
    ) from last_exc
