"""Frequency parsing, native-interval selection, and OHLCV resampling.

Operates on the (columns, rows) shape that normalize.normalize_frame()
produces, once a "date" column (ISO "YYYY-MM-DD" or "YYYY-MM-DD HH:MM:SS")
and canonical OHLCV field names are guaranteed present. Keeping this generic
(rather than per-market) means any market whose adapter can only supply a
finer-than-requested native frequency automatically gets weekly/monthly (or
any coarser bucket) for free via resampling -- not just the daily-only
markets called out in the plan.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

CANONICAL_INTERVALS: tuple[str, ...] = ("1m", "5m", "15m", "30m", "60m", "1d", "1w", "1mo")

_RANK = {code: i for i, code in enumerate(CANONICAL_INTERVALS)}

_ALIASES = {
    "1min": "1m",
    "5min": "5m",
    "15min": "15m",
    "30min": "30m",
    "60min": "60m",
    "1h": "60m",
    "60min1": "60m",
    "day": "1d",
    "daily": "1d",
    "d": "1d",
    "week": "1w",
    "weekly": "1w",
    "w": "1w",
    "month": "1mo",
    "monthly": "1mo",
    "mo": "1mo",
    "1m1": "1mo",
}

_RESAMPLE_RULE = {
    "1m": "1min",
    "5m": "5min",
    "15m": "15min",
    "30m": "30min",
    "60m": "60min",
    "1d": "1D",
    "1w": "W-FRI",
    "1mo": "ME",
}

_INTRADAY = {"1m", "5m", "15m", "30m", "60m"}


def parse_interval(interval: str) -> str:
    """Normalize a user-supplied interval string to a canonical code."""
    key = (interval or "").strip().lower()
    key = _ALIASES.get(key, key)
    if key not in _RANK:
        raise ValueError(f"unsupported interval {interval!r}; choose one of {', '.join(CANONICAL_INTERVALS)}")
    return key


def pick_source_interval(requested: str, available: tuple[str, ...]) -> str:
    """Pick the finest interval in `available` that is <= `requested`.

    That candidate can always be resampled up to `requested`. Raises
    ValueError (with the supported list) if nothing in `available` is fine
    enough -- e.g. a market with only daily bars asked for "5m".
    """
    if not available:
        raise ValueError("this market has no history bars available at any frequency")
    req_rank = _RANK[requested]
    candidates = [a for a in available if _RANK[a] <= req_rank]
    if not candidates:
        finest = min(available, key=lambda a: _RANK[a])
        raise ValueError(
            f"interval {requested!r} is finer than anything this market supports "
            f"(finest available: {finest!r}); supported intervals: {', '.join(available)}"
        )
    return max(candidates, key=lambda a: _RANK[a])


def _end_inclusive_bound(value: str) -> str:
    """Widen a date-only end bound to end-of-day so intraday rows on that
    calendar day aren't excluded by plain string comparison."""
    if len(value) == 10:  # "YYYY-MM-DD"
        return value + " 23:59:59"
    return value


def filter_by_date_range(
    columns: list[str],
    rows: list[list[Any]],
    start: str | None,
    end: str | None,
    date_field: str = "date",
) -> list[list[Any]]:
    """Filter normalized rows to [start, end] (inclusive), string-compared
    against the ISO date/datetime column. ISO-formatted strings sort
    lexicographically the same as chronologically, so no parsing needed.
    """
    if date_field not in columns or (start is None and end is None):
        return rows
    idx = columns.index(date_field)
    lo = start
    hi = _end_inclusive_bound(end) if end is not None else None
    out = []
    for row in rows:
        v = row[idx]
        if v is None:
            continue
        if lo is not None and v < lo:
            continue
        if hi is not None and v > hi:
            continue
        out.append(row)
    return out


_OHLCV_AGG = {
    "open": "first",
    "high": "max",
    "low": "min",
    "close": "last",
    "volume": "sum",
    "amount": "sum",
}


def resample_ohlcv(
    columns: list[str],
    rows: list[list[Any]],
    source_interval: str,
    target_interval: str,
    date_field: str = "date",
) -> tuple[list[str], list[list[Any]], list[str]]:
    """Resample OHLCV rows from `source_interval` up to a coarser
    `target_interval`. Non-OHLCV extra columns (turnover_rate, amplitude,
    change_pct, ...) don't aggregate meaningfully across a resample bucket,
    so they're dropped -- callers are told via the returned notes.
    """
    if source_interval == target_interval:
        return columns, rows, []
    if _RANK[target_interval] <= _RANK[source_interval]:
        raise ValueError(f"cannot resample {source_interval!r} up to finer {target_interval!r}")
    if date_field not in columns:
        raise ValueError(f"cannot resample: no {date_field!r} column in source data")

    agg = {field: how for field, how in _OHLCV_AGG.items() if field in columns}
    if not agg:
        raise ValueError("cannot resample: no OHLCV columns present in source data")

    dropped = sorted(set(columns) - set(agg) - {date_field})

    date_idx = columns.index(date_field)
    field_idx = {c: i for i, c in enumerate(columns)}
    records = [{"__date__": row[date_idx], **{f: row[field_idx[f]] for f in agg}} for row in rows]
    df = pd.DataFrame.from_records(records)
    df["__date__"] = pd.to_datetime(df["__date__"])
    df = df.set_index("__date__").sort_index()

    rule = _RESAMPLE_RULE[target_interval]
    resampled = df.resample(rule).agg(agg).dropna(how="all").reset_index()

    date_fmt = "%Y-%m-%d %H:%M:%S" if target_interval in _INTRADAY else "%Y-%m-%d"
    out_columns = [date_field, *agg.keys()]
    out_rows = [
        [row["__date__"].strftime(date_fmt), *(row[f] for f in agg.keys())]
        for row in resampled.to_dict("records")
    ]
    notes = [f"dropped non-OHLCV column during resample: {c!r}" for c in dropped]
    return out_columns, out_rows, notes


def apply_limit(rows: list[list[Any]], limit: int) -> tuple[list[list[Any]], bool]:
    """Keep only the most recent `limit` rows (rows assumed chronologically
    ascending, which every market adapter in this server returns)."""
    if limit is None or limit <= 0 or len(rows) <= limit:
        return rows, False
    return rows[-limit:], True
