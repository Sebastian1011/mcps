"""FastMCP app: exactly two tools (get_realtime_quotes, get_history_bars)
plus a markets capability resource and a plain HTTP health check.

Keeping only two tools -- instead of exposing a slice of akshare's 1000+
functions directly -- is the whole point of this server: akshare has zero
naming/column consistency across markets, so an agent given raw access
would have to relearn a different call shape per asset class. Here that
routing, symbol resolution, column normalization, caching, and rate
limiting all happen once in registry.py/normalize.py/cache.py/fetch.py, and
the tool surface stays small and uniform regardless of which of the 16
markets is being queried.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from akshare_mcp.cache import get_cache, history_cache_tier, make_key, today
from akshare_mcp.config import get_settings
from akshare_mcp.fetch import UpstreamError
from akshare_mcp.intervals import apply_limit, filter_by_date_range, parse_interval, pick_source_interval, resample_ohlcv
from akshare_mcp.registry import MARKETS, Ctx, get_market

_settings = get_settings()

mcp: FastMCP = FastMCP(
    name="akshare-mcp",
    instructions=(
        "Realtime quotes and multi-frequency history bars across 16 asset classes (A-shares, HK/US "
        "equities, indices, ETF/LOF funds, CN/global futures, forex, crypto, bonds, REITs, SGE spot, "
        "open-end funds), backed by akshare. Read the akshare://markets resource first: it lists valid "
        "`market` keys, each one's symbol format, and which intervals it natively supports."
    ),
    host=_settings.host,
    port=_settings.port,
)


def _ctx() -> Ctx:
    settings = get_settings()
    return Ctx(settings=settings, cache=get_cache(settings))


def _sort_rows(columns: list[str], rows: list[list[Any]], sort_by: str | None) -> tuple[list[list[Any]], str | None]:
    if not sort_by:
        return rows, None
    key = sort_by[1:] if sort_by.startswith("-") else sort_by
    descending = sort_by.startswith("-")
    if key not in columns:
        return rows, f"sort_by column {sort_by!r} not found; result left unsorted"
    idx = columns.index(key)

    def sort_key(row: list[Any]) -> tuple[int, Any]:
        v = row[idx]
        return (1, 0) if v is None else (0, v)

    try:
        return sorted(rows, key=sort_key, reverse=descending), None
    except TypeError:
        return rows, f"sort_by column {sort_by!r} has mixed types across rows; result left unsorted"


@mcp.tool()
async def get_realtime_quotes(
    market: str,
    symbols: list[str] | None = None,
    limit: int = 50,
    offset: int = 0,
    sort_by: str | None = None,
) -> dict[str, Any]:
    """Realtime quotes for one of 16 asset classes.

    Call the akshare://markets resource first to see valid `market` values,
    each one's symbol format, and whether it supports the single-symbol
    fast path. Without `symbols`, returns a page of the whole market table
    (optionally sorted by `sort_by`, e.g. "change_pct" or "-change_pct" for
    descending); with `symbols`, returns just those (markets with a fast
    path fetch each symbol directly and concurrently instead of pulling the
    whole table).
    """
    ctx = _ctx()
    try:
        spec = get_market(market)
    except ValueError as exc:
        raise ToolError(str(exc)) from exc

    if not (1 <= limit <= 5000):
        raise ToolError("limit must be between 1 and 5000")
    if offset < 0:
        raise ToolError("offset must be >= 0")

    fetched_at = datetime.now(tz=ctx.settings.tz)
    notes: list[str] = []
    columns: list[str] = []

    if symbols and spec.spot_single is not None:
        rows: list[list[Any]] = []
        cache_hits = 0

        async def fetch_one(sym: str) -> tuple[list[str] | None, list[Any] | None, list[str], bool]:
            cache_key = make_key("rt1", market=market, symbol=sym)
            cached = ctx.cache.get(cache_key)
            if cached is not None:
                cols, row, row_notes = cached
                return cols, row, row_notes, True
            try:
                cols, row, row_notes, _source = await spec.spot_single(ctx, sym)
            except Exception as exc:  # noqa: BLE001 - one bad symbol shouldn't fail the whole batch
                return None, None, [f"failed to fetch {sym!r}: {exc}"], False
            if not cols:
                return None, None, [f"no realtime quote found for symbol {sym!r}"], False
            ctx.cache.set(cache_key, (cols, row, row_notes), ctx.settings.cache_ttl_realtime)
            return cols, row, row_notes, False

        for cols, row, row_notes, was_cached in await asyncio.gather(*(fetch_one(s) for s in symbols)):
            notes.extend(row_notes)
            if cols is None:
                continue
            if not columns:
                columns = cols
            rows.append(row)
            if was_cached:
                cache_hits += 1

        source = "akshare:stock_individual_spot_xq (single-symbol fast path)"
        total = len(rows)
        cached = len(symbols) > 0 and cache_hits == len(symbols)
    else:
        symbol_hint = symbols[0] if symbols else None
        hint_for_key = symbol_hint if spec.spot_uses_hint else None
        cache_key = make_key("rt", market=market, hint=hint_for_key)
        cached_payload = ctx.cache.get(cache_key)
        if cached_payload is not None:
            columns, rows, table_notes, source = cached_payload
            cached = True
        else:
            try:
                columns, rows, table_notes, source = await spec.spot_table(ctx, symbol_hint)
            except (UpstreamError, ValueError) as exc:
                raise ToolError(str(exc)) from exc
            ctx.cache.set(cache_key, (columns, rows, table_notes, source), ctx.settings.cache_ttl_realtime)
            cached = False
        notes.extend(table_notes)

        if symbols:
            if "symbol" in columns:
                idx = columns.index("symbol")
                wanted = {s.strip().upper() for s in symbols}
                rows = [r for r in rows if r[idx] is not None and str(r[idx]).strip().upper() in wanted]
            else:
                notes.append("this market's table has no 'symbol' column to filter by; returning it unfiltered")

        total = len(rows)

    rows, sort_note = _sort_rows(columns, rows, sort_by)
    if sort_note:
        notes.append(sort_note)

    page = rows[offset : offset + limit]
    returned = len(page)
    truncated = (offset + returned) < total

    return {
        "market": market,
        "as_of": fetched_at.isoformat(),
        "source": source,
        "columns": columns,
        "rows": page,
        "total": total,
        "returned": returned,
        "truncated": truncated,
        "cached": cached,
        "notes": notes,
    }


@mcp.tool()
async def get_history_bars(
    market: str,
    symbol: str,
    interval: str = "1d",
    start: str | None = None,
    end: str | None = None,
    adjust: str = "qfq",
    limit: int = 500,
    refresh: bool = False,
) -> dict[str, Any]:
    """Multi-frequency OHLCV history bars for one of 16 asset classes.

    interval: one of 1m, 5m, 15m, 30m, 60m, 1d, 1w, 1mo. If the underlying
    market only has a coarser native frequency (see akshare://markets),
    finer requests fail with a clear error, and coarser ones (e.g. weekly
    bars for a daily-only market) are synthesized by resampling.
    start/end: "YYYY-MM-DD"; end defaults to today, start to the earliest
    available data.
    adjust: "qfq" (forward-adjusted, default), "hfq" (backward-adjusted),
    or "none". Ignored (noted in `notes`) for markets without a price-
    adjustment concept (indices, futures, forex, bonds, ...).
    Results are cached: 7 days for a date range that ends before today
    (it can't change anymore), 1 hour for ranges still in progress. Pass
    refresh=true to force a re-fetch.
    """
    ctx = _ctx()
    try:
        spec = get_market(market)
    except ValueError as exc:
        raise ToolError(str(exc)) from exc

    if spec.hist is None:
        raise ToolError(f"market {market!r} has no history data available ({spec.description}); realtime quotes only")

    try:
        canonical_interval = parse_interval(interval)
    except ValueError as exc:
        raise ToolError(str(exc)) from exc

    try:
        source_interval = pick_source_interval(canonical_interval, spec.native_intervals)
    except ValueError as exc:
        raise ToolError(f"{exc} (market={market!r})") from exc

    if adjust not in ("qfq", "hfq", "none"):
        raise ToolError("adjust must be one of 'qfq', 'hfq', 'none'")
    if not (1 <= limit <= 20000):
        raise ToolError("limit must be between 1 and 20000")

    start_eff = start or "1970-01-01"
    end_eff = end or today(ctx.settings).isoformat()
    if start_eff > end_eff:
        raise ToolError(f"start ({start_eff}) is after end ({end_eff})")

    tier, ttl = history_cache_tier(ctx.settings, end)
    cache_key = make_key(
        "hist", market=market, symbol=symbol, source_interval=source_interval,
        start=start_eff, end=end_eff, adjust=adjust,
    )

    cached_payload = None if refresh else ctx.cache.get(cache_key)
    if cached_payload is not None:
        columns = cached_payload["columns"]
        rows = cached_payload["rows"]
        notes = list(cached_payload["notes"])
        source = cached_payload["source"]
        cache_hit = True
    else:
        try:
            columns, rows, notes, source = await spec.hist(ctx, symbol, source_interval, start_eff, end_eff, adjust)
        except (UpstreamError, ValueError) as exc:
            raise ToolError(str(exc)) from exc
        ctx.cache.set(cache_key, {"columns": columns, "rows": rows, "notes": notes, "source": source}, ttl)
        cache_hit = False

    if not columns:
        return {
            "market": market, "symbol": symbol, "interval": canonical_interval,
            "source_interval": source_interval, "adjust": adjust,
            "columns": [], "rows": [], "count": 0, "truncated": False,
            "cache": {"hit": cache_hit, "tier": tier, "ttl": ttl},
            "source": source, "notes": [*notes, "no data returned for this symbol/date range"],
        }
    if "date" not in columns:
        raise ToolError(f"internal error: history adapter for market {market!r} produced no 'date' column")

    rows = filter_by_date_range(columns, rows, start_eff, end_eff)

    if source_interval != canonical_interval:
        columns, rows, resample_notes = resample_ohlcv(columns, rows, source_interval, canonical_interval)
        notes = notes + resample_notes

    rows, truncated = apply_limit(rows, limit)

    return {
        "market": market,
        "symbol": symbol,
        "interval": canonical_interval,
        "source_interval": source_interval,
        "adjust": adjust,
        "columns": columns,
        "rows": rows,
        "count": len(rows),
        "truncated": truncated,
        "cache": {"hit": cache_hit, "tier": tier, "ttl": ttl},
        "source": source,
        "notes": notes,
    }


@mcp.resource("akshare://markets")
def markets_resource() -> dict[str, Any]:
    """Capability matrix: every `market` key this server accepts, its
    symbol format, native frequencies, and adjust/fast-path support."""
    return {
        key: {
            "label": spec.label,
            "description": spec.description,
            "native_intervals": list(spec.native_intervals),
            "adjust_supported": spec.adjust_supported,
            "has_history": spec.hist is not None,
            "supports_single_symbol_fast_path": spec.spot_single is not None,
        }
        for key, spec in sorted(MARKETS.items())
    }


@mcp.custom_route("/healthz", methods=["GET"])
async def healthz(request: Request) -> Response:
    return JSONResponse({"status": "ok", "markets": len(MARKETS)})
