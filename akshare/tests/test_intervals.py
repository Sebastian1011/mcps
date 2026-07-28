from __future__ import annotations

import pytest

from akshare_mcp.intervals import (
    apply_limit,
    filter_by_date_range,
    parse_interval,
    pick_source_interval,
    resample_ohlcv,
)


def test_parse_interval_normalizes_aliases() -> None:
    assert parse_interval("1d") == "1d"
    assert parse_interval("Daily") == "1d"
    assert parse_interval("1MIN") == "1m"
    assert parse_interval("weekly") == "1w"
    assert parse_interval("Monthly") == "1mo"


def test_parse_interval_rejects_unknown() -> None:
    with pytest.raises(ValueError, match="unsupported interval"):
        parse_interval("3d")


def test_pick_source_interval_picks_finest_available_at_or_below_requested() -> None:
    assert pick_source_interval("1d", ("1m", "1d", "1w", "1mo")) == "1d"
    assert pick_source_interval("1w", ("1d",)) == "1d"  # will be resampled up
    assert pick_source_interval("60m", ("1m", "5m", "15m", "30m", "60m", "1d")) == "60m"


def test_pick_source_interval_raises_when_nothing_fine_enough() -> None:
    with pytest.raises(ValueError, match="finer than anything"):
        pick_source_interval("5m", ("1d",))


def test_filter_by_date_range_includes_whole_end_day_for_intraday_rows() -> None:
    columns = ["date", "close"]
    rows = [
        ["2025-01-01 09:30:00", 1.0],
        ["2025-01-02 09:30:00", 2.0],
        ["2025-01-02 14:59:00", 3.0],
        ["2025-01-03 09:30:00", 4.0],
    ]
    out = filter_by_date_range(columns, rows, start="2025-01-02", end="2025-01-02")
    assert [r[1] for r in out] == [2.0, 3.0]


def test_resample_ohlcv_daily_to_weekly() -> None:
    columns = ["date", "open", "high", "low", "close", "volume"]
    rows = [
        ["2025-01-06", 10.0, 12.0, 9.0, 11.0, 100],  # Mon
        ["2025-01-07", 11.0, 13.0, 10.0, 12.0, 200],
        ["2025-01-08", 12.0, 14.0, 11.0, 13.0, 150],
        ["2025-01-09", 13.0, 15.0, 12.0, 14.0, 300],
        ["2025-01-10", 14.0, 16.0, 13.0, 15.0, 250],  # Fri, closes the week
        ["2025-01-13", 15.0, 17.0, 14.0, 16.0, 400],  # next Mon, new week
    ]
    out_columns, out_rows, notes = resample_ohlcv(columns, rows, "1d", "1w")
    assert out_columns == ["date", "open", "high", "low", "close", "volume"]
    assert len(out_rows) == 2
    first = out_rows[0]
    assert first[1] == 10.0  # week open = first day's open
    assert first[2] == 16.0  # week high = max
    assert first[3] == 9.0  # week low = min
    assert first[4] == 15.0  # week close = last day's close
    assert first[5] == 1000  # week volume = sum
    assert notes == []


def test_resample_ohlcv_noop_when_same_interval() -> None:
    columns = ["date", "close"]
    rows = [["2025-01-01", 1.0]]
    out_columns, out_rows, notes = resample_ohlcv(columns, rows, "1d", "1d")
    assert (out_columns, out_rows, notes) == (columns, rows, [])


def test_resample_ohlcv_rejects_upsampling() -> None:
    with pytest.raises(ValueError, match="cannot resample"):
        resample_ohlcv(["date", "close"], [["2025-01-01", 1.0]], "1d", "5m")


def test_resample_ohlcv_drops_non_ohlcv_columns_with_note() -> None:
    columns = ["date", "open", "high", "low", "close", "volume", "turnover_rate"]
    rows = [["2025-01-06", 10.0, 12.0, 9.0, 11.0, 100, 1.5]]
    out_columns, out_rows, notes = resample_ohlcv(columns, rows, "1d", "1mo")
    assert "turnover_rate" not in out_columns
    assert any("turnover_rate" in n for n in notes)


def test_apply_limit_keeps_most_recent_rows() -> None:
    rows = [[i] for i in range(10)]
    limited, truncated = apply_limit(rows, 3)
    assert limited == [[7], [8], [9]]
    assert truncated is True

    unchanged, truncated2 = apply_limit(rows, 100)
    assert unchanged == rows
    assert truncated2 is False
