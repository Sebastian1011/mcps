"""Per-market instrument (标的) listings, backing the `list_instruments` tool.

Prefers a dedicated, lightweight akshare "symbol table" function per market
where one exists (cn_stock, cn_index, sge_spot, open_fund, cn_futures) --
these are cheaper and more complete than scraping symbol/name pairs out of
the full realtime quote table, and (for sge_spot in particular) actually
*more correct*: get_realtime_quotes only fans out over a 6-product default
list (see registry._SGE_DEFAULT_SYMBOLS), while spot_symbol_table_sge()
returns the real 17-product table. Every other market falls back to
projecting symbol/name(/exchange) out of its existing spot_table adapter in
registry.py.

Two markets intentionally do NOT use an akshare table that looks more
"dedicated" at first glance -- see their instrument functions' docstrings:
  - convertible_bond: ak.bond_zh_cov() pages through East Money's datacenter
    dozens of times; the existing bond_zh_hs_cov_spot (sina) spot_table is a
    single request and already covers symbol/name.
  - global_index: ak.index_global_name_table() is a *Sina* name/code table
    using a different symbol vocabulary than the *East Money*
    index_global_*_em endpoints this market's spot/hist actually call --
    mixing them would surface symbols that don't resolve to real data.

Caching (which akshare call to skip on a repeat request) is the caller's
(server.py's) job, same as get_realtime_quotes/get_history_bars -- this
module only knows how to fetch and normalize.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

import akshare as ak
import pandas as pd

from akshare_mcp import fetch, symbols
from akshare_mcp.cache import make_key, today
from akshare_mcp.normalize import FUTURES_SPEC_OVERRIDES, normalize_frame
from akshare_mcp.registry import MARKETS, Ctx


@dataclass
class InstrumentTableResult:
    columns: list[str]
    rows: list[list[Any]]
    notes: list[str]
    source: str
    # True when `query` already narrowed *what was fetched* (cn_futures
    # variety -> contract-chain expansion) -- server.py should skip its
    # generic post-hoc substring filter in that case, since re-filtering a
    # variety's own contract chain by the variety name that produced it
    # would otherwise depend on that name also appearing in each contract's
    # "name" column, which is true today but not a contract we want to lean on.
    query_handled: bool = False


# Markets whose *contents* (not just presence) depend on `query` -- only
# cn_futures today. Everything else always fetches/returns its full table
# and lets server.py's generic substring filter narrow it, so the cache key
# for those never needs to vary by query.
QUERY_SENSITIVE_MARKETS: frozenset[str] = frozenset({"cn_futures"})


async def _fallback_from_spot_table(ctx: Ctx, market: str, extra_notes: list[str]) -> InstrumentTableResult:
    """Project symbol/name(/exchange) out of a market's existing realtime
    spot_table -- used both by the 11 markets with no dedicated instrument
    table, and as the error fallback for the 2 dedicated tables (cn_stock,
    cn_index) that hit a separate, less reliable upstream than their
    realtime path.
    """
    spec = MARKETS[market]
    columns, rows, table_notes, source = await spec.spot_table(ctx, None)
    keep = [c for c in ("symbol", "name", "exchange") if c in columns]
    notes = extra_notes + table_notes
    if not keep:
        notes.append("this market's realtime table has no symbol/name columns to project into an instrument listing")
        return InstrumentTableResult(columns, rows, notes, source)
    idxs = [columns.index(c) for c in keep]
    proj_rows = [[row[i] for i in idxs] for row in rows]
    return InstrumentTableResult(keep, proj_rows, notes, source)


async def _cn_stock_instruments(ctx: Ctx, query: str | None) -> InstrumentTableResult:
    try:
        df = await fetch.call(ctx.settings, "exchange_info", ak.stock_info_a_code_name)
    except Exception as exc:  # noqa: BLE001 - fall back rather than fail the whole tool
        return await _fallback_from_spot_table(
            ctx, "cn_stock", [f"stock_info_a_code_name failed ({exc}); showing symbol/name from the realtime table instead"]
        )
    columns, rows, notes = normalize_frame(df)
    return InstrumentTableResult(columns, rows, notes, "akshare:stock_info_a_code_name")


async def _cn_index_instruments(ctx: Ctx, query: str | None) -> InstrumentTableResult:
    try:
        df = await fetch.call(ctx.settings, "joinquant", ak.index_stock_info)
    except Exception as exc:  # noqa: BLE001 - fall back rather than fail the whole tool
        return await _fallback_from_spot_table(
            ctx, "cn_index", [f"index_stock_info failed ({exc}); showing symbol/name from the realtime table instead"]
        )
    columns, rows, notes = normalize_frame(df)
    return InstrumentTableResult(columns, rows, notes, "akshare:index_stock_info")


async def _sge_spot_instruments(ctx: Ctx, query: str | None) -> InstrumentTableResult:
    df = await fetch.call(ctx.settings, "sge", ak.spot_symbol_table_sge)
    columns, rows, notes = normalize_frame(df)
    return InstrumentTableResult(columns, rows, notes, "akshare:spot_symbol_table_sge")


async def _open_fund_instruments(ctx: Ctx, query: str | None) -> InstrumentTableResult:
    df = await fetch.call(ctx.settings, "eastmoney", ak.fund_name_em)
    columns, rows, notes = normalize_frame(df)
    return InstrumentTableResult(columns, rows, notes, "akshare:fund_name_em")


async def _cn_futures_instruments(ctx: Ctx, query: str | None) -> InstrumentTableResult:
    df = await fetch.call(ctx.settings, "sina", ak.futures_symbol_mark)
    # futures_symbol_mark()'s own "symbol" column is actually the Chinese
    # variety name (e.g. "螺纹钢"), not a contract code -- rename explicitly
    # so it doesn't get confused with a real per-contract symbol.
    columns, rows, notes = normalize_frame(df, overrides={"symbol": "variety"})
    notes = notes + [
        "each row is a tradable variety, not a specific contract; pass `query` matching a variety's Chinese "
        "name or a known contract-code prefix (e.g. 'RB2510', 'rb0') to expand its live contract chain instead"
    ]
    source = "akshare:futures_symbol_mark"
    if not query:
        return InstrumentTableResult(columns, rows, notes, source)

    try:
        variety = symbols.resolve_futures_variety(query)
    except ValueError:
        # not a recognized prefix and not a Chinese name either -- fall back
        # to the variety list; server.py's generic substring filter (which
        # also checks the "variety" column) still has a shot at it.
        return InstrumentTableResult(columns, rows, notes, source)

    spec = MARKETS["cn_futures"]
    try:
        chain_cols, chain_rows, chain_notes, chain_src = await spec.spot_table(ctx, variety)
    except Exception as exc:  # noqa: BLE001 - degrade to the variety list rather than fail the tool
        notes.append(f"could not expand contract chain for variety {variety!r}: {exc}; showing the variety list instead")
        return InstrumentTableResult(columns, rows, notes, source)
    return InstrumentTableResult(chain_cols, chain_rows, chain_notes, chain_src, query_handled=True)


_DEDICATED: dict[str, Callable[[Ctx, "str | None"], Awaitable[InstrumentTableResult]]] = {
    "cn_stock": _cn_stock_instruments,
    "cn_index": _cn_index_instruments,
    "sge_spot": _sge_spot_instruments,
    "open_fund": _open_fund_instruments,
    "cn_futures": _cn_futures_instruments,
}

# Static (no network call) description of each market's instrument-listing
# source, for describe_market()/the akshare://markets resource -- the
# dedicated tables above may still fall back at request time (cn_stock,
# cn_index), which is noted in the actual response's `notes`, not here.
INSTRUMENT_SOURCE_LABEL: dict[str, str] = {
    "cn_stock": "akshare:stock_info_a_code_name (falls back to the realtime spot table on failure)",
    "cn_index": "akshare:index_stock_info (falls back to the realtime spot table on failure)",
    "sge_spot": "akshare:spot_symbol_table_sge",
    "open_fund": "akshare:fund_name_em",
    "cn_futures": "akshare:futures_symbol_mark (variety list; expands to a contract chain when `query` matches one)",
    **{
        key: "projected from the realtime spot table (symbol/name only)"
        for key in MARKETS
        if key not in ("cn_stock", "cn_index", "sge_spot", "open_fund", "cn_futures")
    },
}


async def list_instruments_table(ctx: Ctx, market: str, query: str | None) -> InstrumentTableResult:
    """Dispatch to the dedicated fetcher for `market` if one exists,
    otherwise project symbol/name(/exchange) out of its spot_table."""
    if market not in MARKETS:
        raise ValueError(f"unknown market {market!r}; choose one of {', '.join(sorted(MARKETS))}")
    dedicated = _DEDICATED.get(market)
    if dedicated is not None:
        return await dedicated(ctx, query)
    return await _fallback_from_spot_table(ctx, market, [])


def filter_rows(columns: list[str], rows: list[list[Any]], query: str | None) -> list[list[Any]]:
    """Case-insensitive substring match against symbol/name/variety (and
    open_fund's pinyin/pinyin_full), used by server.py after fetching a
    market's instrument table -- unless the fetch already narrowed itself to
    `query` (see InstrumentTableResult.query_handled).
    """
    q = (query or "").strip().lower()
    if not q:
        return rows
    candidate_idxs = [columns.index(c) for c in ("symbol", "name", "variety", "pinyin", "pinyin_full") if c in columns]
    if not candidate_idxs:
        return rows
    out = []
    for row in rows:
        if any(row[i] is not None and q in str(row[i]).lower() for i in candidate_idxs):
            out.append(row)
    return out


# ---------------------------------------------------------------------------
# cn_futures contract specs (list_instruments(..., include_spec=True))
# ---------------------------------------------------------------------------

# Each exchange's contract-info endpoint (see FUTURES_SPEC_OVERRIDES in
# normalize.py) and whether it requires a `date` (trading day) parameter.
# Stored by *name* rather than a direct function reference and resolved via
# getattr(ak, ...) at call time (same idiom test_registry.py's drift check
# uses) -- binding `ak.futures_contract_info_dce` etc. directly here would
# capture the function object at import time, which real akshare upgrades
# don't invalidate but monkeypatching `ak.<name>` in a test can't reach.
_EXCHANGE_FNS: dict[str, tuple[str, bool]] = {
    "shfe": ("futures_contract_info_shfe", True),
    "ine": ("futures_contract_info_ine", True),
    "czce": ("futures_contract_info_czce", True),
    "cffex": ("futures_contract_info_cffex", True),
    "dce": ("futures_contract_info_dce", False),
    "gfex": ("futures_contract_info_gfex", False),
}

# Contract-code prefix -> exchange. Mirrors the same standard exchange
# prefix grouping documented in symbols._FUTURES_PREFIX_TO_VARIETY (SHFE/
# DCE/CZCE/CFFEX/GFEX); INE isn't covered here either, for the same reason
# that constant gives -- see its docstring.
_PREFIX_TO_EXCHANGE: dict[str, str] = {
    **{p: "shfe" for p in ("RB", "HC", "CU", "AL", "ZN", "PB", "NI", "SN", "AU", "AG", "RU", "BU", "FU", "SP", "SS", "WR", "BC")},
    **{p: "dce" for p in ("M", "Y", "A", "B", "C", "CS", "I", "J", "JM", "L", "V", "PP", "EG", "EB", "PG", "JD", "RR", "LH")},
    **{p: "czce" for p in ("SR", "CF", "TA", "MA", "FG", "SA", "OI", "RM", "RS", "JR", "WH", "PM", "SF", "SM", "UR", "PK", "PF", "AP", "CJ", "ZC")},
    **{p: "cffex" for p in ("IF", "IH", "IC", "IM", "T", "TF", "TS", "TL")},
    **{p: "gfex" for p in ("SI", "LC")},
}


async def _recent_trade_dates(ctx: Ctx, count: int = 4) -> list[str]:
    """Most recent `count` trade dates (YYYYMMDD, most-recent-first, not
    after today) from ak.tool_trade_date_hist_sina(), 24h-cached. Several
    exchange contract-info endpoints require an exact past trading day and
    return empty/error for a non-trading day.
    """
    key = make_key("trade_dates", kind="sina_calendar")
    dates = ctx.cache.get(key)
    if dates is None:
        df = await fetch.call(ctx.settings, "sina", ak.tool_trade_date_hist_sina)
        dates = [d.strftime("%Y%m%d") for d in df["trade_date"]]
        ctx.cache.set(key, dates, ctx.settings.symbol_table_ttl)
    today_str = today(ctx.settings).strftime("%Y%m%d")
    past = [d for d in dates if d <= today_str]
    return list(reversed(past[-count:]))


async def _fetch_exchange_contract_info_raw(ctx: Ctx, exchange: str) -> tuple[pd.DataFrame | None, list[str]]:
    fn_name, needs_date = _EXCHANGE_FNS[exchange]
    fn = getattr(ak, fn_name)
    notes: list[str] = []
    if not needs_date:
        try:
            df = await fetch.call(ctx.settings, "exchange_info", fn)
        except Exception as exc:  # noqa: BLE001 - one exchange's failure shouldn't block the others
            return None, [f"{exchange}: {fn_name} failed: {exc}"]
        return df, notes

    for date_str in await _recent_trade_dates(ctx):
        try:
            df = await fetch.call(ctx.settings, "exchange_info", fn, date=date_str)
        except Exception as exc:  # noqa: BLE001 - try the next trading day
            notes.append(f"{exchange}: {fn_name}(date={date_str!r}) failed: {exc}")
            continue
        if df is not None and not df.empty:
            return df, []
    return None, notes + [f"{exchange}: {fn_name} returned no data for any recent trading day"]


async def _normalized_exchange_contract_info(ctx: Ctx, exchange: str) -> tuple[list[str], list[list[Any]], list[str]]:
    """Fetch + normalize one exchange's contract-info table, 24h-cached (like
    symbols.resolve_us_stock's symbol table) -- we cache the already-
    normalized (columns, rows), never the raw DataFrame, matching cache.py's
    "never pickle a DataFrame" rule.
    """
    cache_key = make_key("futures_spec", exchange=exchange)
    cached = ctx.cache.get(cache_key)
    if cached is not None:
        return cached

    df, notes = await _fetch_exchange_contract_info_raw(ctx, exchange)
    if df is None:
        return [], [], notes

    overrides = dict(FUTURES_SPEC_OVERRIDES[exchange])
    if exchange == "czce":
        # akshare bakes a temporary caveat into this column's literal name
        # (see FUTURES_SPEC_OVERRIDES's czce comment) -- locate it by prefix
        # instead of depending on the exact string.
        last_trading_col = next((c for c in df.columns if str(c).startswith("最后交易日")), None)
        if last_trading_col:
            overrides[last_trading_col] = "last_trading_day"
        else:
            notes.append("czce: could not find a '最后交易日*' column in contract info output")

    columns, rows, col_notes = normalize_frame(df, overrides=overrides)
    notes = notes + col_notes
    ctx.cache.set(cache_key, (columns, rows, notes), ctx.settings.symbol_table_ttl)
    return columns, rows, notes


async def fetch_cn_futures_contract_specs(
    ctx: Ctx, contract_symbols: list[str]
) -> tuple[list[str], dict[str, list[Any]], list[str]]:
    """Fetch and merge contract trading specs for `contract_symbols` from
    each relevant exchange's contract-info endpoint. Best-effort per
    exchange, same pattern as registry._sge_spot_table's per-product fetch:
    one exchange failing doesn't block the others, and a contract whose
    prefix isn't in _PREFIX_TO_EXCHANGE gets a null spec plus a note instead
    of an error. Returns (columns, {contract_symbol: spec_row}, notes).
    """
    wanted = {s.strip().upper() for s in contract_symbols if s and s.strip()}
    needed_exchanges: dict[str, str] = {}  # exchange -> one example unresolved prefix, for logging only
    unresolved: list[str] = []
    for sym in wanted:
        prefix = "".join(ch for ch in sym if not ch.isdigit())
        exchange = _PREFIX_TO_EXCHANGE.get(prefix)
        if exchange:
            needed_exchanges[exchange] = prefix
        else:
            unresolved.append(sym)

    notes: list[str] = []
    if unresolved:
        notes.append(f"no contract-info source known for {sorted(unresolved)}; spec left null for these")

    columns: list[str] = []
    seen_cols: set[str] = set()
    by_symbol: dict[str, dict[str, Any]] = {}

    for exchange in sorted(needed_exchanges):
        cols, rows, ex_notes = await _normalized_exchange_contract_info(ctx, exchange)
        notes.extend(ex_notes)
        if "symbol" not in cols:
            if cols:
                notes.append(f"{exchange}: contract-info output has no contract-code column after normalization")
            continue

        sym_idx = cols.index("symbol")
        for c in cols:
            if c not in seen_cols:
                seen_cols.add(c)
                columns.append(c)
        for row in rows:
            sym = row[sym_idx]
            if sym is None:
                continue
            record = dict(zip(cols, row))
            record["exchange"] = exchange
            by_symbol[str(sym).strip().upper()] = record

    if "exchange" not in seen_cols:
        columns.append("exchange")
        seen_cols.add("exchange")

    spec_by_symbol: dict[str, list[Any]] = {}
    for sym in wanted:
        record = by_symbol.get(sym)
        spec_by_symbol[sym] = [record.get(c) if record else None for c in columns]

    return columns, spec_by_symbol, notes
