"""schemas.py vs. reality -- offline drift detection.

schemas.MARKET_SCHEMAS' realtime_fields/history_fields were derived from the
literal `.columns = [...]`/`.rename(columns={...})` assignments inside each
wrapped akshare function (see schemas.py's module docstring and the plan
doc's trace). These tests replay those exact raw column lists through
normalize_frame() -- the same function registry.py's adapters actually
call -- and assert the result matches what schemas.py declares, so a
mismatch is caught here instead of silently drifting from what the tools
actually return.
"""

from __future__ import annotations

import pandas as pd
import pytest

from akshare_mcp import schemas
from akshare_mcp.intervals import CANONICAL_INTERVALS
from akshare_mcp.normalize import normalize_frame
from akshare_mcp.registry import MARKETS


def _fields(columns_and_overrides: tuple[list[str], dict[str, str | None]]) -> set[str]:
    columns, overrides = columns_and_overrides
    df = pd.DataFrame([[1] * len(columns)], columns=columns)
    out_columns, _rows, _notes = normalize_frame(df, overrides=overrides)
    return set(out_columns)


def test_every_market_has_a_schema() -> None:
    assert set(schemas.MARKET_SCHEMAS) == set(MARKETS)


def test_all_declared_fields_are_in_the_field_dictionary() -> None:
    missing: set[tuple[str, str]] = set()
    for market, schema in schemas.MARKET_SCHEMAS.items():
        for field_name in (*schema.realtime_fields, *schema.history_fields, *schema.history_fields_intraday):
            if field_name not in schemas.FIELDS:
                missing.add((market, field_name))
    assert not missing


def test_xq_single_quote_fields_are_in_the_field_dictionary() -> None:
    assert all(f in schemas.FIELDS for f in schemas.XQ_SINGLE_QUOTE_FIELDS)


def test_resampled_intervals_excludes_native_and_finer() -> None:
    assert schemas.resampled_intervals(()) == ()
    assert schemas.resampled_intervals(("1d",)) == ("1w", "1mo")
    assert schemas.resampled_intervals(("1d", "1w", "1mo")) == ()
    assert schemas.resampled_intervals(CANONICAL_INTERVALS) == ()


def test_resampled_intervals_are_disjoint_from_native_for_every_market() -> None:
    for market, spec in MARKETS.items():
        resampled = schemas.resampled_intervals(spec.native_intervals)
        assert not (set(resampled) & set(spec.native_intervals)), market


# (market, (raw source columns, overrides)) -- raw columns/overrides verified
# against akshare 1.18.80's actual `.columns =`/`.rename(columns=)` literals
# for the realtime function each market's spot_table calls.
_REALTIME_CASES: dict[str, tuple[list[str], dict[str, str | None]]] = {
    "cn_stock": (
        ["代码", "名称", "最新价", "涨跌额", "涨跌幅", "今开", "最高", "最低", "昨收",
         "成交量", "成交额", "换手率", "量比", "市盈率-动态", "市净率", "总市值", "流通市值"], {},
    ),
    "hk_stock": (
        ["代码", "名称", "最新价", "涨跌额", "涨跌幅", "今开", "最高", "最低", "昨收", "成交量", "成交额"], {},
    ),
    "us_stock": (
        ["代码", "名称", "最新价", "涨跌额", "涨跌幅", "开盘价", "最高价", "最低价", "昨收价",
         "成交量", "成交额", "总市值", "市盈率"], {},
    ),
    "cn_index": (
        ["代码", "名称", "最新价", "涨跌幅", "涨跌额", "成交量", "成交额", "振幅", "最高", "最低", "今开", "昨收", "量比"], {},
    ),
    "global_index": (
        ["代码", "名称", "最新价", "涨跌额", "涨跌幅", "开盘价", "最高价", "最低价", "昨收价", "振幅", "最新行情时间"], {},
    ),
    "etf": (
        ["代码", "名称", "最新价", "涨跌额", "涨跌幅", "开盘价", "最高价", "最低价", "昨收",
         "成交量", "成交额", "换手率", "IOPV实时估值", "基金折价率", "流通市值", "总市值"], {},
    ),
    "lof": (
        ["代码", "名称", "最新价", "涨跌额", "涨跌幅", "成交量", "成交额", "开盘价", "最高价", "最低价",
         "昨收", "换手率", "流通市值", "总市值"], {},
    ),
    "cn_futures": (
        ["symbol", "exchange", "name", "trade", "open", "high", "low", "preclose", "volume",
         "position", "changepercent", "settlement", "ticktime"],
        {"trade": "last", "preclose": "prev_close", "changepercent": "change_pct",
         "position": "open_interest", "ticktime": "updated_at"},
    ),
    "global_futures": (
        ["代码", "名称", "最新价", "涨跌额", "涨跌幅", "今开", "最高", "最低", "昨结", "成交量", "持仓量"], {},
    ),
    "forex": (
        ["代码", "名称", "最新价", "涨跌额", "涨跌幅", "今开", "最高", "最低", "昨收"], {},
    ),
    "crypto": (
        ["市场", "交易品种", "最近报价", "涨跌额", "涨跌幅", "24小时最高", "24小时最低", "24小时成交量", "更新时间"], {},
    ),
    "convertible_bond": (
        ["symbol", "name", "trade", "pricechange", "changepercent", "open", "high", "low",
         "settlement", "volume", "amount", "buy", "sell", "ticktime"],
        {"trade": "last", "pricechange": "change", "changepercent": "change_pct",
         "settlement": "prev_close", "ticktime": "updated_at"},
    ),
    "cn_bond": (
        ["代码", "名称", "最新价", "涨跌额", "涨跌幅", "买入", "卖出", "昨收", "今开", "最高", "最低", "成交量", "成交额"], {},
    ),
    "reits": (
        ["代码", "名称", "最新价", "涨跌额", "涨跌幅", "成交量", "成交额", "开盘价", "最高价", "最低价", "昨收"], {},
    ),
    "sge_spot": (["品种", "时间", "现价", "更新时间"], {"时间": "time"}),
    "open_fund": None,  # bespoke normalizer (registry._normalize_open_fund_table), not normalize_frame -- skip
}


@pytest.mark.parametrize("market", sorted(k for k, v in _REALTIME_CASES.items() if v is not None))
def test_realtime_fields_match_the_actual_wrapped_akshare_function(market: str) -> None:
    actual = _fields(_REALTIME_CASES[market])
    declared = set(schemas.MARKET_SCHEMAS[market].realtime_fields)
    assert actual == declared


# (market, (raw history columns, overrides)) for the *daily* (1d/1w/1mo)
# history function each market's `hist` adapter calls.
_HISTORY_DAILY_CASES: dict[str, tuple[list[str], dict[str, str | None]]] = {
    "cn_stock": (
        ["日期", "开盘", "收盘", "最高", "最低", "成交量", "成交额", "振幅", "涨跌幅", "涨跌额", "换手率", "股票代码"], {},
    ),
    "hk_stock": (
        ["日期", "开盘", "收盘", "最高", "最低", "成交量", "成交额", "振幅", "涨跌幅", "涨跌额", "换手率"], {},
    ),
    "us_stock": (
        ["日期", "开盘", "收盘", "最高", "最低", "成交量", "成交额", "振幅", "涨跌幅", "涨跌额", "换手率"], {},
    ),
    "cn_index": (
        ["日期", "开盘", "收盘", "最高", "最低", "成交量", "成交额", "振幅", "涨跌幅", "涨跌额", "换手率"], {},
    ),
    "etf": (
        ["日期", "开盘", "收盘", "最高", "最低", "成交量", "成交额", "振幅", "涨跌幅", "涨跌额", "换手率"], {},
    ),
    "lof": (
        ["日期", "开盘", "收盘", "最高", "最低", "成交量", "成交额", "振幅", "涨跌幅", "涨跌额", "换手率"], {},
    ),
    "global_index": (
        ["日期", "今开", "最新价", "最高", "最低", "-", "-", "振幅", "-", "-", "-", "-", "-", "-", "代码", "名称"],
        {"最新价": "close"},
    ),
    "forex": (
        ["日期", "今开", "最新价", "最高", "最低", "-", "-", "振幅", "-", "-", "-", "-", "-", "-", "代码", "名称"],
        {"最新价": "close"},
    ),
    "cn_futures": (["date", "open", "high", "low", "close", "volume", "hold", "settle"], {}),
    "reits": (
        ["日期", "今开", "最新价", "最高", "最低", "成交量", "成交额", "振幅", "-", "-", "换手", "-", "-", "-"],
        {"最新价": "close"},
    ),
    "sge_spot": (["date", "open", "close", "low", "high"], {}),
    "open_fund": (["净值日期", "单位净值", "日增长率"], {"净值日期": "date", "单位净值": "close", "日增长率": "change_pct"}),
    # global_futures's hist adapter applies registry._select() before
    # normalize_frame(); reproduce that pre-selection here too.
    "global_futures": (["日期", "代码", "名称", "开盘", "最新价", "最高", "最低", "总量", "涨幅", "持仓", "日增"], {"最新价": "close"}),
}


@pytest.mark.parametrize("market", sorted(_HISTORY_DAILY_CASES))
def test_history_fields_match_the_actual_wrapped_akshare_function(market: str) -> None:
    actual = _fields(_HISTORY_DAILY_CASES[market])
    declared = set(schemas.MARKET_SCHEMAS[market].history_fields)
    assert actual == declared


# (market, (raw minute-bar columns, overrides)) for markets with intraday
# native intervals.
_HISTORY_INTRADAY_CASES: dict[str, tuple[list[str], dict[str, str | None]]] = {
    "cn_stock": (["时间", "开盘", "收盘", "最高", "最低", "成交量", "成交额", "均价"], {"时间": "date"}),
    "cn_index": (["时间", "开盘", "收盘", "最高", "最低", "成交量", "成交额", "均价"], {"时间": "date"}),
    "etf": (["时间", "开盘", "收盘", "最高", "最低", "成交量", "成交额", "均价"], {"时间": "date"}),
    "lof": (["时间", "开盘", "收盘", "最高", "最低", "成交量", "成交额", "均价"], {"时间": "date"}),
    "hk_stock": (["时间", "开盘", "收盘", "最高", "最低", "成交量", "成交额", "最新价"], {"时间": "date"}),
    "us_stock": (["时间", "开盘", "收盘", "最高", "最低", "成交量", "成交额", "最新价"], {"时间": "date"}),
    "cn_futures": (["datetime", "open", "high", "low", "close", "volume", "hold"], {"datetime": "date"}),
}


@pytest.mark.parametrize("market", sorted(_HISTORY_INTRADAY_CASES))
def test_intraday_history_fields_match_the_actual_wrapped_akshare_function(market: str) -> None:
    actual = _fields(_HISTORY_INTRADAY_CASES[market])
    declared = set(schemas.MARKET_SCHEMAS[market].history_fields_intraday)
    assert actual == declared
