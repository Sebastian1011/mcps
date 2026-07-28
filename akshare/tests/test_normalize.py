from __future__ import annotations

import datetime as dt
import math

import pandas as pd

from akshare_mcp.normalize import normalize_frame, to_scalar, xq_to_record


def test_to_scalar_handles_nan_and_numpy_and_timestamp() -> None:
    assert to_scalar(float("nan")) is None
    assert to_scalar(None) is None
    assert to_scalar(pd.NaT) is None
    assert to_scalar(pd.Timestamp("2025-01-02 09:30:00")) == "2025-01-02 09:30:00"
    assert to_scalar(pd.Series([1, 2, 3]).iloc[0]) == 1  # numpy int64 -> python int
    assert to_scalar("600519") == "600519"


def test_to_scalar_handles_plain_datetime_date_and_datetime() -> None:
    # Several akshare functions do `.dt.date`, producing plain
    # datetime.date objects rather than pd.Timestamp -- these must
    # normalize to the same ISO string shape, not leak through as an
    # unserializable date object.
    assert to_scalar(dt.date(2025, 1, 2)) == "2025-01-02"
    assert to_scalar(dt.datetime(2025, 1, 2, 9, 30)) == "2025-01-02 09:30:00"


def test_normalize_frame_renames_and_drops() -> None:
    df = pd.DataFrame(
        {
            "序号": [1, 2],
            "代码": ["600519", "000001"],
            "名称": ["贵州茅台", "平安银行"],
            "最新价": [1408.42, 10.5],
            "涨跌幅": [-2.49, 0.5],
        }
    )
    columns, rows, notes = normalize_frame(df)
    assert columns == ["symbol", "name", "last", "change_pct"]
    assert rows == [
        ["600519", "贵州茅台", 1408.42, -2.49],
        ["000001", "平安银行", 10.5, 0.5],
    ]
    assert notes == []  # 序号 is a known drop, not an unmapped column


def test_normalize_frame_overrides_take_priority() -> None:
    # bare "时间" means "date" in a kline row, not the sge-style clock label
    # CN_COLUMN_MAP intentionally has no global entry for it.
    df = pd.DataFrame({"时间": ["2025-01-02 09:30:00"], "开盘": [10.0], "最新价": [10.5]})
    columns, rows, notes = normalize_frame(df, overrides={"时间": "date", "最新价": "close"})
    assert columns == ["date", "open", "close"]
    assert rows == [["2025-01-02 09:30:00", 10.0, 10.5]]


def test_normalize_frame_passes_through_unmapped_columns_with_note() -> None:
    df = pd.DataFrame({"代码": ["RB2510"], "某新奇字段": [42]})
    columns, rows, notes = normalize_frame(df)
    assert columns == ["symbol", "某新奇字段"]
    assert rows == [["RB2510", 42]]
    assert len(notes) == 1
    assert "某新奇字段" in notes[0]


def test_normalize_frame_empty_df() -> None:
    assert normalize_frame(pd.DataFrame()) == ([], [], [])
    assert normalize_frame(None) == ([], [], [])


def test_xq_to_record_pivots_item_value_pairs() -> None:
    df = pd.DataFrame(
        {
            "item": ["代码", "名称", "现价", "涨幅", "一个陌生指标"],
            "value": ["SH600519", "贵州茅台", 1315.01, 1.98, 7],
        }
    )
    columns, row, notes = xq_to_record(df)
    assert columns[:4] == ["symbol", "name", "last", "change_pct"]
    assert row[:4] == ["SH600519", "贵州茅台", 1315.01, 1.98]
    assert "一个陌生指标" in columns
    assert any("一个陌生指标" in n for n in notes)


def test_xq_to_record_empty() -> None:
    assert xq_to_record(pd.DataFrame()) == ([], [], [])
