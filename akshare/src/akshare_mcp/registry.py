"""Market registry: which akshare functions back each of the 16 asset
classes this server exposes, and how to call them.

Every (spot, history) function pair here was verified against the actual
akshare 1.18.80 source and/or a live pull during the design phase -- column
names, parameter names, and quirks (e.g. some functions take no date range
at all and must be filtered client-side; us_stock minute bars only cover
~5 trading days; futures history/realtime use different symbol vocabularies
entirely). See the plan doc for the trace. Where akshare itself has no
function for something (crypto history), the market is registered with
hist=None and the tool raises a clear error instead of silently returning
nothing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

import akshare as ak
import pandas as pd

from akshare_mcp import fetch, symbols
from akshare_mcp.cache import ResponseCache
from akshare_mcp.config import Settings
from akshare_mcp.normalize import normalize_frame, to_scalar, xq_to_record


@dataclass
class Ctx:
    settings: Settings
    cache: ResponseCache


# (columns, rows, notes, source_label)
SpotTableResult = tuple[list[str], list[list[Any]], list[str], str]
# (columns, row, notes, source_label)
SpotSingleResult = tuple[list[str], list[Any], list[str], str]
# (columns, rows, notes, source_label)
HistResult = tuple[list[str], list[list[Any]], list[str], str]

SpotTableFn = Callable[[Ctx, "str | None"], Awaitable[SpotTableResult]]
SpotSingleFn = Callable[[Ctx, str], Awaitable[SpotSingleResult]]
# (ctx, raw_symbol, native_interval, start "YYYY-MM-DD", end "YYYY-MM-DD", adjust) -> result
HistFn = Callable[[Ctx, str, str, str, str, str], Awaitable[HistResult]]


@dataclass
class MarketSpec:
    key: str
    label: str
    # Interval codes natively available from the underlying source, finest
    # first is not required -- intervals.pick_source_interval() sorts by
    # CANONICAL_INTERVALS rank. Anything coarser than the finest native
    # interval is synthesized by resampling (see intervals.resample_ohlcv).
    native_intervals: tuple[str, ...]
    adjust_supported: bool
    spot_table: SpotTableFn
    spot_single: SpotSingleFn | None
    hist: HistFn | None
    description: str = ""
    # Whether spot_table's symbol_hint actually changes what gets fetched
    # (cn_futures picks a variety, sge_spot picks a product). For every other
    # market the hint is ignored, so the realtime cache key must NOT include
    # it -- otherwise every distinct symbol filter would bypass the cache
    # and refetch the whole market table.
    spot_uses_hint: bool = False


def _select(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Keep only `cols` that actually exist, in the given order. Lets each
    market curate a compact realtime payload out of akshare's wider (and
    sometimes 30+ column) raw tables instead of shipping every field.
    """
    return df[[c for c in cols if c in df.columns]]


_DAILY_PERIOD = {"1d": "daily", "1w": "weekly", "1mo": "monthly"}
_MINUTE_PERIOD = {"1m": "1", "5m": "5", "15m": "15", "30m": "30", "60m": "60"}
_ADJUST_ARG = {"qfq": "qfq", "hfq": "hfq", "none": ""}


def _ymd(s: str) -> str:
    return s.replace("-", "")


def _dt_start(s: str) -> str:
    return f"{s} 00:00:00"


def _dt_end(s: str) -> str:
    return f"{s} 23:59:59"


def _adjust_note(adjust: str, supported: bool) -> list[str]:
    if not supported and adjust != "none":
        return ["adjust is not supported for this market; request ignored"]
    return []


# ---------------------------------------------------------------------------
# Shared East Money kline helper -- covers cn_stock, hk_stock, cn_index, etf,
# lof: all four expose a `<x>_hist(symbol, period, start_date, end_date[,
# adjust])` daily/weekly/monthly function plus a matching
# `<x>_hist_min_em(symbol, start_date, end_date, period[, adjust])` minute
# function, verified to share the same column layout across all of them.
# ---------------------------------------------------------------------------
async def _std_em_kline(
    ctx: Ctx,
    daily_fn,
    minute_fn,
    symbol: str,
    interval: str,
    start: str,
    end: str,
    adjust: str,
    supports_adjust: bool = True,
) -> HistResult:
    notes = _adjust_note(adjust, supports_adjust)
    if interval in _DAILY_PERIOD:
        kwargs: dict[str, Any] = dict(
            symbol=symbol, period=_DAILY_PERIOD[interval], start_date=_ymd(start), end_date=_ymd(end)
        )
        if supports_adjust:
            kwargs["adjust"] = _ADJUST_ARG[adjust]
        df = await fetch.call(ctx.settings, "eastmoney", daily_fn, **kwargs)
        columns, rows, n2 = normalize_frame(df)
        src = f"akshare:{daily_fn.__name__}"
    else:
        kwargs = dict(symbol=symbol, start_date=_dt_start(start), end_date=_dt_end(end), period=_MINUTE_PERIOD[interval])
        if supports_adjust:
            kwargs["adjust"] = _ADJUST_ARG[adjust]
        df = await fetch.call(ctx.settings, "eastmoney", minute_fn, **kwargs)
        columns, rows, n2 = normalize_frame(df, overrides={"时间": "date"})
        src = f"akshare:{minute_fn.__name__}"
    return columns, rows, notes + n2, src


async def _xq_single(ctx: Ctx, xq_symbol: str) -> SpotSingleResult:
    df = await fetch.call(ctx.settings, "xueqiu", ak.stock_individual_spot_xq, symbol=xq_symbol)
    columns, row, notes = xq_to_record(df)
    return columns, row, notes, "akshare:stock_individual_spot_xq"


# ---------------------------------------------------------------------------
# cn_stock
# ---------------------------------------------------------------------------
async def _cn_stock_spot_table(ctx: Ctx, symbol_hint: str | None) -> SpotTableResult:
    df = await fetch.call(ctx.settings, "eastmoney", ak.stock_zh_a_spot_em)
    df = _select(
        df,
        ["代码", "名称", "最新价", "涨跌额", "涨跌幅", "今开", "最高", "最低", "昨收",
         "成交量", "成交额", "换手率", "量比", "市盈率-动态", "市净率", "总市值", "流通市值"],
    )
    columns, rows, notes = normalize_frame(df)
    return columns, rows, notes, "akshare:stock_zh_a_spot_em"


async def _cn_stock_spot_single(ctx: Ctx, symbol: str) -> SpotSingleResult:
    code = symbols.strip_exchange_prefix(symbol).strip().upper()
    xq_symbol = symbols.guess_cn_exchange_prefix(code) + code
    return await _xq_single(ctx, xq_symbol)


async def _cn_stock_hist(ctx: Ctx, symbol: str, interval: str, start: str, end: str, adjust: str) -> HistResult:
    return await _std_em_kline(
        ctx, ak.stock_zh_a_hist, ak.stock_zh_a_hist_min_em,
        symbols.strip_exchange_prefix(symbol), interval, start, end, adjust,
    )


# ---------------------------------------------------------------------------
# hk_stock
# ---------------------------------------------------------------------------
async def _hk_stock_spot_table(ctx: Ctx, symbol_hint: str | None) -> SpotTableResult:
    df = await fetch.call(ctx.settings, "eastmoney", ak.stock_hk_spot_em)
    columns, rows, notes = normalize_frame(df)
    return columns, rows, notes, "akshare:stock_hk_spot_em"


async def _hk_stock_spot_single(ctx: Ctx, symbol: str) -> SpotSingleResult:
    code = symbol.strip()
    if code.isdigit():
        code = code.zfill(5)
    return await _xq_single(ctx, code)


async def _hk_stock_hist(ctx: Ctx, symbol: str, interval: str, start: str, end: str, adjust: str) -> HistResult:
    return await _std_em_kline(
        ctx, ak.stock_hk_hist, ak.stock_hk_hist_min_em,
        symbols.strip_exchange_prefix(symbol), interval, start, end, adjust,
    )


# ---------------------------------------------------------------------------
# us_stock -- minute history has no `period`/`adjust` param and only covers
# roughly the last 5 trading days (it's the same "trends2" endpoint East
# Money uses for intraday tick charts, not a proper archival kline store).
# ---------------------------------------------------------------------------
async def _us_stock_spot_table(ctx: Ctx, symbol_hint: str | None) -> SpotTableResult:
    df = await fetch.call(ctx.settings, "eastmoney", ak.stock_us_spot_em)
    df = _select(
        df,
        ["代码", "名称", "最新价", "涨跌额", "涨跌幅", "开盘价", "最高价", "最低价", "昨收价",
         "成交量", "成交额", "总市值", "市盈率"],
    )
    columns, rows, notes = normalize_frame(df)
    return columns, rows, notes, "akshare:stock_us_spot_em"


async def _us_stock_spot_single(ctx: Ctx, symbol: str) -> SpotSingleResult:
    return await _xq_single(ctx, symbol.strip().upper())


async def _us_stock_hist(ctx: Ctx, symbol: str, interval: str, start: str, end: str, adjust: str) -> HistResult:
    resolved = await symbols.resolve_us_stock(symbol, ctx.settings, ctx.cache)
    if interval in _DAILY_PERIOD:
        df = await fetch.call(
            ctx.settings, "eastmoney", ak.stock_us_hist,
            symbol=resolved, period=_DAILY_PERIOD[interval],
            start_date=_ymd(start), end_date=_ymd(end), adjust=_ADJUST_ARG[adjust],
        )
        columns, rows, notes = normalize_frame(df)
        if resolved != symbol.strip():
            notes.append(f"resolved symbol {symbol!r} to {resolved!r}")
        return columns, rows, notes, "akshare:stock_us_hist"

    df = await fetch.call(
        ctx.settings, "eastmoney", ak.stock_us_hist_min_em,
        symbol=resolved, start_date=_dt_start(start), end_date=_dt_end(end),
    )
    columns, rows, notes = normalize_frame(df, overrides={"时间": "date"})
    notes = notes + ["us_stock minute bars only cover roughly the last 5 trading days (upstream limitation)"]
    notes += _adjust_note(adjust, supported=False)
    if resolved != symbol.strip():
        notes.append(f"resolved symbol {symbol!r} to {resolved!r}")
    return columns, rows, notes, "akshare:stock_us_hist_min_em"


# ---------------------------------------------------------------------------
# cn_index
# ---------------------------------------------------------------------------
async def _cn_index_spot_table(ctx: Ctx, symbol_hint: str | None) -> SpotTableResult:
    df = await fetch.call(ctx.settings, "eastmoney", ak.stock_zh_index_spot_em, symbol="沪深重要指数")
    columns, rows, notes = normalize_frame(df)
    return columns, rows, notes, "akshare:stock_zh_index_spot_em"


async def _cn_index_hist(ctx: Ctx, symbol: str, interval: str, start: str, end: str, adjust: str) -> HistResult:
    return await _std_em_kline(
        ctx, ak.index_zh_a_hist, ak.index_zh_a_hist_min_em,
        symbols.strip_exchange_prefix(symbol), interval, start, end, adjust,
        supports_adjust=False,
    )


# ---------------------------------------------------------------------------
# global_index -- daily-only, and index_global_hist_em has no date-range
# params at all (returns full history; filtered client-side downstream).
# ---------------------------------------------------------------------------
async def _global_index_spot_table(ctx: Ctx, symbol_hint: str | None) -> SpotTableResult:
    df = await fetch.call(ctx.settings, "eastmoney", ak.index_global_spot_em)
    df = _select(
        df, ["代码", "名称", "最新价", "涨跌额", "涨跌幅", "开盘价", "最高价", "最低价", "昨收价", "振幅", "最新行情时间"]
    )
    columns, rows, notes = normalize_frame(df)
    return columns, rows, notes, "akshare:index_global_spot_em"


async def _global_index_hist(ctx: Ctx, symbol: str, interval: str, start: str, end: str, adjust: str) -> HistResult:
    df = await fetch.call(ctx.settings, "eastmoney", ak.index_global_hist_em, symbol=symbol.strip())
    columns, rows, notes = normalize_frame(df, overrides={"最新价": "close"})
    notes += _adjust_note(adjust, supported=False)
    return columns, rows, notes, "akshare:index_global_hist_em"


# ---------------------------------------------------------------------------
# etf / lof
# ---------------------------------------------------------------------------
async def _etf_spot_table(ctx: Ctx, symbol_hint: str | None) -> SpotTableResult:
    df = await fetch.call(ctx.settings, "eastmoney", ak.fund_etf_spot_em)
    df = _select(
        df,
        ["代码", "名称", "最新价", "涨跌额", "涨跌幅", "开盘价", "最高价", "最低价", "昨收",
         "成交量", "成交额", "换手率", "IOPV实时估值", "基金折价率", "流通市值", "总市值"],
    )
    columns, rows, notes = normalize_frame(df)
    return columns, rows, notes, "akshare:fund_etf_spot_em"


async def _etf_hist(ctx: Ctx, symbol: str, interval: str, start: str, end: str, adjust: str) -> HistResult:
    return await _std_em_kline(
        ctx, ak.fund_etf_hist_em, ak.fund_etf_hist_min_em,
        symbols.strip_exchange_prefix(symbol), interval, start, end, adjust,
    )


async def _lof_spot_table(ctx: Ctx, symbol_hint: str | None) -> SpotTableResult:
    df = await fetch.call(ctx.settings, "eastmoney", ak.fund_lof_spot_em)
    columns, rows, notes = normalize_frame(df)
    return columns, rows, notes, "akshare:fund_lof_spot_em"


async def _lof_hist(ctx: Ctx, symbol: str, interval: str, start: str, end: str, adjust: str) -> HistResult:
    return await _std_em_kline(
        ctx, ak.fund_lof_hist_em, ak.fund_lof_hist_min_em,
        symbols.strip_exchange_prefix(symbol), interval, start, end, adjust,
    )


# ---------------------------------------------------------------------------
# cn_futures -- realtime and history use *different* symbol vocabularies:
# futures_zh_realtime wants a Chinese variety name ("螺纹钢") and returns the
# whole contract chain for that variety; futures_zh_daily_sina /
# futures_zh_minute_sina want an actual contract code ("RB0", "RB2510").
# symbols.resolve_futures_variety() bridges contract-code-looking input to
# the variety name for the realtime path only.
# ---------------------------------------------------------------------------
async def _cn_futures_spot_table(ctx: Ctx, symbol_hint: str | None) -> SpotTableResult:
    variety = symbols.resolve_futures_variety(symbol_hint or "螺纹钢")
    df = await fetch.call(ctx.settings, "sina", ak.futures_zh_realtime, symbol=variety)
    df = _select(
        df,
        ["symbol", "exchange", "name", "trade", "open", "high", "low", "preclose",
         "volume", "position", "changepercent", "settlement", "ticktime"],
    )
    columns, rows, notes = normalize_frame(
        df,
        overrides={
            "trade": "last", "preclose": "prev_close", "changepercent": "change_pct",
            "position": "open_interest", "ticktime": "updated_at",
        },
    )
    notes = notes + [
        f"showing all tradable contracts for variety {variety!r}; "
        "pass symbols=['<contract code>'] (e.g. 'RB2510') to pick one"
    ]
    return columns, rows, notes, "akshare:futures_zh_realtime"


async def _cn_futures_hist(ctx: Ctx, symbol: str, interval: str, start: str, end: str, adjust: str) -> HistResult:
    sym = symbol.strip().upper()
    notes = _adjust_note(adjust, supported=False)
    if interval == "1d":
        df = await fetch.call(ctx.settings, "sina", ak.futures_zh_daily_sina, symbol=sym)
        columns, rows, n2 = normalize_frame(df)
        return columns, rows, notes + n2, "akshare:futures_zh_daily_sina"
    df = await fetch.call(ctx.settings, "sina", ak.futures_zh_minute_sina, symbol=sym, period=_MINUTE_PERIOD[interval])
    columns, rows, n2 = normalize_frame(df, overrides={"datetime": "date"})
    return columns, rows, notes + n2, "akshare:futures_zh_minute_sina"


# ---------------------------------------------------------------------------
# global_futures -- daily-only, no date-range params on the history endpoint.
# ---------------------------------------------------------------------------
async def _global_futures_spot_table(ctx: Ctx, symbol_hint: str | None) -> SpotTableResult:
    df = await fetch.call(ctx.settings, "eastmoney", ak.futures_global_spot_em)
    df = _select(df, ["代码", "名称", "最新价", "涨跌额", "涨跌幅", "今开", "最高", "最低", "昨结", "成交量", "持仓量"])
    columns, rows, notes = normalize_frame(df)
    return columns, rows, notes, "akshare:futures_global_spot_em"


async def _global_futures_hist(ctx: Ctx, symbol: str, interval: str, start: str, end: str, adjust: str) -> HistResult:
    df = await fetch.call(ctx.settings, "eastmoney", ak.futures_global_hist_em, symbol=symbol.strip())
    df = _select(df, ["日期", "代码", "名称", "开盘", "最新价", "最高", "最低", "总量", "涨幅", "持仓", "日增"])
    columns, rows, notes = normalize_frame(df, overrides={"最新价": "close"})
    notes += _adjust_note(adjust, supported=False)
    return columns, rows, notes, "akshare:futures_global_hist_em"


# ---------------------------------------------------------------------------
# forex -- daily-only, no date-range params.
# ---------------------------------------------------------------------------
async def _forex_spot_table(ctx: Ctx, symbol_hint: str | None) -> SpotTableResult:
    df = await fetch.call(ctx.settings, "eastmoney", ak.forex_spot_em)
    columns, rows, notes = normalize_frame(df)
    return columns, rows, notes, "akshare:forex_spot_em"


async def _forex_hist(ctx: Ctx, symbol: str, interval: str, start: str, end: str, adjust: str) -> HistResult:
    df = await fetch.call(ctx.settings, "eastmoney", ak.forex_hist_em, symbol=symbol.strip().upper())
    columns, rows, notes = normalize_frame(df, overrides={"最新价": "close"})
    notes += _adjust_note(adjust, supported=False)
    return columns, rows, notes, "akshare:forex_hist_em"


# ---------------------------------------------------------------------------
# crypto -- realtime only; akshare has no matching history function.
# ---------------------------------------------------------------------------
async def _crypto_spot_table(ctx: Ctx, symbol_hint: str | None) -> SpotTableResult:
    df = await fetch.call(ctx.settings, "jin10", ak.crypto_js_spot)
    columns, rows, notes = normalize_frame(df)
    return columns, rows, notes, "akshare:crypto_js_spot"


# ---------------------------------------------------------------------------
# convertible_bond / cn_bond -- akshare wants an sh/sz-prefixed code but
# there's no reliable rule to derive the exchange from a bare numeric code,
# so we try both prefixes in turn (symbols.bond_symbol_candidates) and use
# whichever succeeds.
# ---------------------------------------------------------------------------
async def _convertible_bond_spot_table(ctx: Ctx, symbol_hint: str | None) -> SpotTableResult:
    df = await fetch.call(ctx.settings, "sina", ak.bond_zh_hs_cov_spot)
    df = _select(
        df,
        ["symbol", "name", "trade", "pricechange", "changepercent", "open", "high", "low",
         "settlement", "volume", "amount", "buy", "sell", "ticktime"],
    )
    columns, rows, notes = normalize_frame(
        df,
        overrides={
            "trade": "last", "pricechange": "change", "changepercent": "change_pct",
            "settlement": "prev_close", "ticktime": "updated_at",
        },
    )
    return columns, rows, notes, "akshare:bond_zh_hs_cov_spot"


async def _bond_hist_with_fallback(ctx: Ctx, symbol: str, fn, source_label: str) -> HistResult:
    last_exc: Exception | None = None
    for candidate in symbols.bond_symbol_candidates(symbol):
        try:
            df = await fetch.call(ctx.settings, "sina", fn, symbol=candidate)
        except Exception as exc:  # noqa: BLE001 - try the other exchange prefix next
            last_exc = exc
            continue
        if df is not None and not df.empty:
            columns, rows, notes = normalize_frame(df)
            if candidate != symbol.strip().lower():
                notes = notes + [f"resolved {symbol!r} to exchange-prefixed code {candidate!r}"]
            return columns, rows, notes, source_label
    raise ValueError(
        f"could not find bond symbol {symbol!r} on either exchange (tried "
        f"{symbols.bond_symbol_candidates(symbol)}); pass an sh-/sz-prefixed code if known"
    ) from last_exc


async def _convertible_bond_hist(ctx: Ctx, symbol: str, interval: str, start: str, end: str, adjust: str) -> HistResult:
    columns, rows, notes, src = await _bond_hist_with_fallback(ctx, symbol, ak.bond_zh_hs_cov_daily, "akshare:bond_zh_hs_cov_daily")
    return columns, rows, notes + _adjust_note(adjust, supported=False), src


async def _cn_bond_spot_table(ctx: Ctx, symbol_hint: str | None) -> SpotTableResult:
    df = await fetch.call(ctx.settings, "sina", ak.bond_zh_hs_spot)
    columns, rows, notes = normalize_frame(df)
    return columns, rows, notes, "akshare:bond_zh_hs_spot"


async def _cn_bond_hist(ctx: Ctx, symbol: str, interval: str, start: str, end: str, adjust: str) -> HistResult:
    columns, rows, notes, src = await _bond_hist_with_fallback(ctx, symbol, ak.bond_zh_hs_daily, "akshare:bond_zh_hs_daily")
    return columns, rows, notes + _adjust_note(adjust, supported=False), src


# ---------------------------------------------------------------------------
# reits
# ---------------------------------------------------------------------------
async def _reits_spot_table(ctx: Ctx, symbol_hint: str | None) -> SpotTableResult:
    df = await fetch.call(ctx.settings, "eastmoney", ak.reits_realtime_em)
    df = _select(df, ["代码", "名称", "最新价", "涨跌额", "涨跌幅", "成交量", "成交额", "开盘价", "最高价", "最低价", "昨收"])
    columns, rows, notes = normalize_frame(df)
    return columns, rows, notes, "akshare:reits_realtime_em"


async def _reits_hist(ctx: Ctx, symbol: str, interval: str, start: str, end: str, adjust: str) -> HistResult:
    df = await fetch.call(ctx.settings, "eastmoney", ak.reits_hist_em, symbol=symbols.strip_exchange_prefix(symbol))
    columns, rows, notes = normalize_frame(df, overrides={"最新价": "close"})
    notes += _adjust_note(adjust, supported=False)
    return columns, rows, notes, "akshare:reits_hist_em"


# ---------------------------------------------------------------------------
# sge_spot -- Shanghai Gold Exchange. spot_quotations_sge(symbol) returns
# today's intraday ticks for *one* product, not a market-wide snapshot, so
# there's no single "list everything" call; we fan out over a small default
# product list (or the caller's requested symbol) and take the latest tick
# from each.
# ---------------------------------------------------------------------------
_SGE_DEFAULT_SYMBOLS = ["Au99.99", "Au99.95", "Ag99.99", "Au(T+D)", "Ag(T+D)", "Pt99.95"]


async def _sge_spot_table(ctx: Ctx, symbol_hint: str | None) -> SpotTableResult:
    wanted = [symbol_hint] if symbol_hint else _SGE_DEFAULT_SYMBOLS
    columns: list[str] = []
    rows: list[list[Any]] = []
    notes: list[str] = []
    for sym in wanted:
        try:
            df = await fetch.call(ctx.settings, "sge", ak.spot_quotations_sge, symbol=sym)
        except Exception as exc:  # noqa: BLE001 - one bad product shouldn't fail the whole listing
            notes.append(f"failed to fetch sge_spot symbol {sym!r}: {exc}")
            continue
        if df is None or df.empty:
            continue
        cols, one_row, n2 = normalize_frame(df.tail(1), overrides={"时间": "time"})
        if not columns:
            columns = cols
        rows.append(one_row[0])
        notes.extend(n2)
    if not symbol_hint:
        notes.append(
            f"sge_spot has no market-wide realtime endpoint; showing default products {_SGE_DEFAULT_SYMBOLS}. "
            "Pass symbols=[...] for others (see ak.spot_symbol_table_sge() for the full product list)."
        )
    return columns, rows, notes, "akshare:spot_quotations_sge"


async def _sge_spot_hist(ctx: Ctx, symbol: str, interval: str, start: str, end: str, adjust: str) -> HistResult:
    df = await fetch.call(ctx.settings, "sge", ak.spot_hist_sge, symbol=symbol.strip())
    columns, rows, notes = normalize_frame(df)
    notes += _adjust_note(adjust, supported=False)
    return columns, rows, notes, "akshare:spot_hist_sge"


# ---------------------------------------------------------------------------
# open_fund -- fund_open_fund_daily_em's columns are dynamically dated
# ("2026-07-27-单位净值", ...), so it gets a bespoke normalizer instead of the
# generic CN_COLUMN_MAP path.
# ---------------------------------------------------------------------------
def _normalize_open_fund_table(df: pd.DataFrame) -> tuple[list[str], list[list[Any]], list[str]]:
    nav_cols = [c for c in df.columns if str(c).endswith("-单位净值")]
    cum_cols = [c for c in df.columns if str(c).endswith("-累计净值")]
    notes: list[str] = []
    if not nav_cols:
        notes.append("could not find a dated '*-单位净值' column in fund_open_fund_daily_em output")

    latest_nav_col = nav_cols[0] if nav_cols else None
    latest_cum_col = cum_cols[0] if cum_cols else None
    nav_date = latest_nav_col.rsplit("-", 1)[0] if latest_nav_col else None

    columns = [
        "symbol", "name", "nav", "nav_date", "cumulative_nav",
        "change", "change_pct", "subscription_status", "redemption_status", "fee",
    ]
    rows = []
    for _, r in df.iterrows():
        rows.append(
            [
                to_scalar(r.get("基金代码")),
                to_scalar(r.get("基金简称")),
                to_scalar(r.get(latest_nav_col)) if latest_nav_col else None,
                nav_date,
                to_scalar(r.get(latest_cum_col)) if latest_cum_col else None,
                to_scalar(r.get("日增长值")),
                to_scalar(r.get("日增长率")),
                to_scalar(r.get("申购状态")),
                to_scalar(r.get("赎回状态")),
                to_scalar(r.get("手续费")),
            ]
        )
    return columns, rows, notes


async def _open_fund_spot_table(ctx: Ctx, symbol_hint: str | None) -> SpotTableResult:
    df = await fetch.call(ctx.settings, "eastmoney", ak.fund_open_fund_daily_em)
    if symbol_hint:
        df = df[df["基金代码"].astype(str) == symbol_hint.strip()]
    columns, rows, notes = _normalize_open_fund_table(df)
    return columns, rows, notes, "akshare:fund_open_fund_daily_em"


async def _open_fund_hist(ctx: Ctx, symbol: str, interval: str, start: str, end: str, adjust: str) -> HistResult:
    df = await fetch.call(
        ctx.settings, "eastmoney", ak.fund_open_fund_info_em,
        symbol=symbol.strip(), indicator="单位净值走势", period="成立来",
    )
    columns, rows, notes = normalize_frame(
        df, overrides={"净值日期": "date", "单位净值": "close", "日增长率": "change_pct"}
    )
    notes += _adjust_note(adjust, supported=False)
    return columns, rows, notes, "akshare:fund_open_fund_info_em"


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
_ALL_FREQ = ("1m", "5m", "15m", "30m", "60m", "1d", "1w", "1mo")

MARKETS: dict[str, MarketSpec] = {
    "cn_stock": MarketSpec(
        key="cn_stock", label="A股 (沪深京)", native_intervals=_ALL_FREQ, adjust_supported=True,
        spot_table=_cn_stock_spot_table, spot_single=_cn_stock_spot_single, hist=_cn_stock_hist,
        description="Shanghai/Shenzhen/Beijing A-shares, e.g. symbol='600519' or '000001'.",
    ),
    "hk_stock": MarketSpec(
        key="hk_stock", label="港股", native_intervals=_ALL_FREQ, adjust_supported=True,
        spot_table=_hk_stock_spot_table, spot_single=_hk_stock_spot_single, hist=_hk_stock_hist,
        description="Hong Kong equities, e.g. symbol='00700'.",
    ),
    "us_stock": MarketSpec(
        key="us_stock", label="美股", native_intervals=("1m", "1d", "1w", "1mo"), adjust_supported=True,
        spot_table=_us_stock_spot_table, spot_single=_us_stock_spot_single, hist=_us_stock_hist,
        description="US equities, e.g. symbol='AAPL'. Minute bars only cover ~5 recent trading days.",
    ),
    "cn_index": MarketSpec(
        key="cn_index", label="A股指数", native_intervals=_ALL_FREQ, adjust_supported=False,
        spot_table=_cn_index_spot_table, spot_single=None, hist=_cn_index_hist,
        description="Shanghai/Shenzhen indices, e.g. symbol='000300' (CSI 300).",
    ),
    "global_index": MarketSpec(
        key="global_index", label="全球指数", native_intervals=("1d",), adjust_supported=False,
        spot_table=_global_index_spot_table, spot_single=None, hist=_global_index_hist,
        description="Global indices by Chinese name, e.g. symbol='美元指数' (US Dollar Index), '道琼斯'.",
    ),
    "etf": MarketSpec(
        key="etf", label="ETF基金", native_intervals=_ALL_FREQ, adjust_supported=True,
        spot_table=_etf_spot_table, spot_single=None, hist=_etf_hist,
        description="Exchange-traded funds, e.g. symbol='510300'.",
    ),
    "lof": MarketSpec(
        key="lof", label="LOF基金", native_intervals=_ALL_FREQ, adjust_supported=True,
        spot_table=_lof_spot_table, spot_single=None, hist=_lof_hist,
        description="Listed open-ended funds, e.g. symbol='166009'.",
    ),
    "cn_futures": MarketSpec(
        key="cn_futures", label="国内期货", native_intervals=("1m", "5m", "15m", "30m", "60m", "1d"),
        adjust_supported=False, spot_uses_hint=True,
        spot_table=_cn_futures_spot_table, spot_single=None, hist=_cn_futures_hist,
        description=(
            "Chinese commodity/financial futures. History wants a contract code (symbol='RB0' for the "
            "main continuous contract, or 'RB2510' for a specific one); realtime accepts either a contract "
            "code (variety is inferred) or a Chinese variety name ('螺纹钢') and returns the whole chain."
        ),
    ),
    "global_futures": MarketSpec(
        key="global_futures", label="外盘期货", native_intervals=("1d",), adjust_supported=False,
        spot_table=_global_futures_spot_table, spot_single=None, hist=_global_futures_hist,
        description="International futures, e.g. symbol='HG00Y' (COMEX copper) as listed by the spot table.",
    ),
    "forex": MarketSpec(
        key="forex", label="外汇", native_intervals=("1d",), adjust_supported=False,
        spot_table=_forex_spot_table, spot_single=None, hist=_forex_hist,
        description="FX pairs, e.g. symbol='USDCNH'.",
    ),
    "crypto": MarketSpec(
        key="crypto", label="加密货币", native_intervals=(), adjust_supported=False,
        spot_table=_crypto_spot_table, spot_single=None, hist=None,
        description="Major cryptocurrencies (~10 symbols), realtime only -- akshare has no history function for this.",
    ),
    "convertible_bond": MarketSpec(
        key="convertible_bond", label="可转债", native_intervals=("1d",), adjust_supported=False,
        spot_table=_convertible_bond_spot_table, spot_single=None, hist=_convertible_bond_hist,
        description="Shanghai/Shenzhen convertible bonds, e.g. symbol='113050' or 'sh113050'.",
    ),
    "cn_bond": MarketSpec(
        key="cn_bond", label="沪深债券", native_intervals=("1d",), adjust_supported=False,
        spot_table=_cn_bond_spot_table, spot_single=None, hist=_cn_bond_hist,
        description="Shanghai/Shenzhen plain bonds, e.g. symbol='010107' or 'sh010107'.",
    ),
    "reits": MarketSpec(
        key="reits", label="REITs", native_intervals=("1d",), adjust_supported=False,
        spot_table=_reits_spot_table, spot_single=None, hist=_reits_hist,
        description="Shanghai/Shenzhen REITs, e.g. symbol='508097'.",
    ),
    "sge_spot": MarketSpec(
        key="sge_spot", label="上海黄金交易所现货", native_intervals=("1d",), adjust_supported=False,
        spot_uses_hint=True,
        spot_table=_sge_spot_table, spot_single=None, hist=_sge_spot_hist,
        description="Shanghai Gold Exchange spot products, e.g. symbol='Au99.99'.",
    ),
    "open_fund": MarketSpec(
        key="open_fund", label="场外开放式基金", native_intervals=("1d",), adjust_supported=False,
        spot_table=_open_fund_spot_table, spot_single=None, hist=_open_fund_hist,
        description="Off-exchange open-ended mutual funds (NAV-based, no OHLC/volume), e.g. symbol='710001'.",
    ),
}


def get_market(key: str) -> MarketSpec:
    try:
        return MARKETS[key]
    except KeyError:
        raise ValueError(f"unknown market {key!r}; choose one of {', '.join(sorted(MARKETS))}") from None
