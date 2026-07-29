"""DataFrame -> compact columnar payload.

akshare has no consistent column-naming convention across its 1000+ public
functions (Chinese vs English, `最新价` vs `现价` vs `trade`, ...). Rather than
hand-writing a bespoke renamer per market, we centralize the recurring
Chinese financial vocabulary in CN_COLUMN_MAP -- verified against the actual
akshare 1.18.80 source (see plan doc) for every market this server wires up
-- and apply it uniformly. Anything not covered passes through under its
original name instead of raising: a missing mapping should degrade
gracefully (visible in `notes`), not break the tool.
"""

from __future__ import annotations

import datetime as dt
import math
from typing import Any

import pandas as pd

# Chinese/legacy column name -> canonical English field name.
# A value of None means "drop this column" (it's an internal row-index/
# placeholder column, not data).
CN_COLUMN_MAP: dict[str, str | None] = {
    # identity
    "代码": "symbol",
    "股票代码": "symbol",
    "基金代码": "symbol",
    "品种": "symbol",
    "交易品种": "symbol",
    # already-English identity columns from akshare's own instrument-table
    # functions (stock_info_a_code_name / index_stock_info), normalized to
    # the same symbol/name pair every other market uses so
    # list_instruments() has one consistent column shape.
    "code": "symbol",
    "index_code": "symbol",
    "名称": "name",
    "基金简称": "name",
    "display_name": "name",
    "交易所": "exchange",
    "市场": "exchange",
    # price
    "最新价": "last",
    "最近报价": "last",
    "现价": "last",
    "开盘": "open",
    "今开": "open",
    "开盘价": "open",
    "收盘": "close",
    "最高": "high",
    "最高价": "high",
    "24小时最高": "high",
    "最低": "low",
    "最低价": "low",
    "24小时最低": "low",
    "昨收": "prev_close",
    "昨收价": "prev_close",
    "昨结": "prev_settle",
    "涨跌额": "change",
    "涨跌": "change",
    "日增长值": "change",
    "涨跌幅": "change_pct",
    "涨幅": "change_pct",
    "日增长率": "change_pct",
    # volume / turnover
    "成交量": "volume",
    "24小时成交量": "volume",
    "成交额": "amount",
    "振幅": "amplitude",
    "换手率": "turnover_rate",
    "量比": "volume_ratio",
    "持仓量": "open_interest",
    # global_futures_hist_em's raw output uses the shorter "持仓" (not
    # "持仓量") for the same open-interest concept -- previously unmapped,
    # so get_history_bars(market='global_futures') was silently emitting
    # the raw Chinese column name instead of 'open_interest'.
    "持仓": "open_interest",
    "买盘": "bid_volume",
    "卖盘": "ask_volume",
    "买入": "bid",
    "卖出": "ask",
    # valuation
    "市盈率-动态": "pe_ttm",
    "市盈率": "pe_ttm",
    "市净率": "pb",
    "总市值": "market_cap",
    "流通市值": "circulating_market_cap",
    "IOPV实时估值": "iopv",
    "基金折价率": "discount_rate",
    "换手": "turnover_rate",
    "总量": "volume",
    "均价": "avg_price",
    "日增": "oi_change",
    # time (note: bare "时间" is context-dependent -- kline date column vs.
    # sge intraday tick clock -- so callers pass it via `overrides` instead
    # of relying on a global mapping here)
    "日期": "date",
    "净值日期": "date",
    "更新时间": "updated_at",
    "最新行情时间": "updated_at",
    "数据日期": "data_date",
    "ticktime": "updated_at",
    "tradedate": "trade_date",
    # fund flags
    "申购状态": "subscription_status",
    "赎回状态": "redemption_status",
    "手续费": "fee",
    # fund instrument listing (fund_name_em, used by list_instruments for open_fund)
    "拼音缩写": "pinyin",
    "拼音全称": "pinyin_full",
    "基金类型": "fund_type",
    # internal / row-index artifacts, always dropped
    "序号": None,
    "index": None,
}

# Columns that are pure row-index artifacts regardless of language.
_ALWAYS_DROP = {"_", "-"}


def to_scalar(value: Any) -> Any:
    """Convert one pandas/numpy cell into a JSON-safe Python scalar."""
    if value is None:
        return None
    try:
        # Catches NaN, NaT, and any other pandas missing-value sentinel.
        # Must run before the datetime/date checks below: pd.NaT is itself
        # a (degenerate) datetime.datetime instance, so checking isinstance
        # first would stringify it to the literal "NaT" instead of None.
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass  # value isn't NA-checkable (e.g. a list/array) -- fall through
    if isinstance(value, pd.Timestamp):
        return value.isoformat(sep=" ")
    if isinstance(value, dt.datetime):
        return value.isoformat(sep=" ")
    if isinstance(value, dt.date):
        # Several akshare functions do `.dt.date`, producing plain
        # datetime.date objects rather than Timestamps -- normalize both to
        # the same ISO string shape so downstream date-range filtering and
        # resampling (which compare/parse the "date" column as a string)
        # never see a mix of types.
        return value.isoformat()
    if hasattr(value, "item"):
        # numpy scalar (int64, float64, bool_, ...)
        try:
            value = value.item()
        except (ValueError, TypeError):
            pass
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def normalize_frame(
    df: pd.DataFrame,
    overrides: dict[str, str | None] | None = None,
    drop: set[str] | None = None,
) -> tuple[list[str], list[list[Any]], list[str]]:
    """Rename a raw akshare DataFrame's columns to the canonical vocabulary.

    `overrides` take priority over CN_COLUMN_MAP (used for context-dependent
    source columns, e.g. a bare "时间" meaning "date" in kline output but
    "time" in an intraday tick table). Columns with no mapping at all pass
    through under their original name; that fact is surfaced in the
    returned `notes` list so gaps in CN_COLUMN_MAP are discoverable instead
    of silently dropped.

    Returns (columns, rows, notes) where rows is a list of plain-Python-
    scalar lists in the same order as columns.
    """
    if df is None or df.empty:
        return [], [], []

    overrides = overrides or {}
    drop = (drop or set()) | _ALWAYS_DROP

    out_columns: list[str] = []
    seen: set[str] = set()
    notes: list[str] = []
    keep_source_cols: list[str] = []

    for col in df.columns:
        col_str = str(col)
        if col_str in drop:
            continue
        if col_str in overrides:
            mapped = overrides[col_str]
        elif col_str in CN_COLUMN_MAP:
            mapped = CN_COLUMN_MAP[col_str]
        else:
            mapped = col_str
            if not col_str.isascii():
                notes.append(f"unmapped source column passed through as-is: {col_str!r}")
        if mapped is None:
            continue
        if mapped in seen:
            # duplicate canonical name (rare) -- keep first occurrence only
            continue
        seen.add(mapped)
        out_columns.append(mapped)
        keep_source_cols.append(col_str)

    subset = df[keep_source_cols]
    rows = [[to_scalar(v) for v in row] for row in subset.itertuples(index=False, name=None)]
    return out_columns, rows, notes


# Item-name map for the "item"/"value" long-format single-quote endpoint
# (ak.stock_individual_spot_xq), verified against a live SH600519 pull.
XQ_ITEM_MAP: dict[str, str] = {
    "代码": "symbol",
    "名称": "name",
    "交易所": "exchange",
    "现价": "last",
    "涨跌": "change",
    "涨幅": "change_pct",
    "今开": "open",
    "最高": "high",
    "最低": "low",
    "昨收": "prev_close",
    "成交量": "volume",
    "成交额": "amount",
    "时间": "updated_at",
    "均价": "avg_price",
    "振幅": "amplitude",
    "换手率": "turnover_rate",
    "量比": "volume_ratio",
    "市净率": "pb",
    "市盈率(TTM)": "pe_ttm",
    "市盈率(动)": "pe_dynamic",
    "市盈率(静)": "pe_static",
    "每股收益": "eps",
    "每股净资产": "bvps",
    "股息(TTM)": "dividend_ttm",
    "股息率(TTM)": "dividend_yield_ttm",
    "52周最高": "week52_high",
    "52周最低": "week52_low",
    "涨停": "limit_up",
    "跌停": "limit_down",
    "今年以来涨幅": "ytd_change_pct",
    "流通股": "shares_circulating",
    "流通值": "circulating_market_cap",
    "资产净值/总市值": "market_cap",
    "货币": "currency",
}


def xq_to_record(df: pd.DataFrame) -> tuple[list[str], list[Any], list[str]]:
    """Pivot the item/value long-format single-quote endpoint into one row.

    ak.stock_individual_spot_xq() returns a two-column (item, value)
    DataFrame describing a single symbol at a point in time. We flatten it
    into the same (columns, row) shape normalize_frame() produces so the
    realtime tool can treat the single-symbol fast path and the full-market
    table path uniformly.
    """
    if df is None or df.empty:
        return [], [], []

    columns: list[str] = []
    row: list[Any] = []
    notes: list[str] = []
    seen: set[str] = set()

    for item, value in zip(df["item"], df["value"]):
        item_str = str(item)
        mapped = XQ_ITEM_MAP.get(item_str)
        if mapped is None:
            if not item_str.isascii():
                notes.append(f"unmapped xq item passed through as-is: {item_str!r}")
            mapped = item_str
        if mapped in seen:
            continue
        seen.add(mapped)
        columns.append(mapped)
        row.append(to_scalar(value))

    return columns, row, notes


# cn_futures contract-spec lookups (list_instruments(..., include_spec=True))
# -- verified against each exchange's futures_contract_info_* source in
# akshare 1.18.80. Each exchange uses a completely different column
# vocabulary, so unlike the rest of this module these need per-exchange
# `overrides` passed to normalize_frame() rather than one shared global
# mapping: e.g. GFEX/CFFEX's raw "品种" here means "variety name", which
# would otherwise collide with CN_COLUMN_MAP's "品种" -> "symbol" (used by
# cn_futures' own realtime table) and silently drop the real contract-code
# column under normalize_frame()'s first-occurrence-wins dedup. A value of
# None drops that column (same convention as CN_COLUMN_MAP). See
# akshare_mcp.instruments for how these are used and what each exchange
# does/doesn't publish.
FUTURES_SPEC_OVERRIDES: dict[str, dict[str, str | None]] = {
    "shfe": {
        "合约代码": "symbol", "上市日": "listing_date", "到期日": "expiry_date",
        "开始交割日": "delivery_start_date", "最后交割日": "last_delivery_day",
        "挂牌基准价": "listing_base_price", "交易日": "trade_date", "更新时间": "updated_at",
    },
    "ine": {
        "合约代码": "symbol", "上市日": "listing_date", "到期日": "expiry_date",
        "开始交割日": "delivery_start_date", "最后交割日": "last_delivery_day",
        "挂牌基准价": "listing_base_price", "交易日": "trade_date",
    },
    "dce": {
        "品种名称": "variety", "合约": "symbol", "交易单位": "contract_unit",
        "最小变动价位": "tick_size", "开始交易日": "listing_date",
        "最后交易日": "last_trading_day", "最后交割日": "last_delivery_day",
    },
    "gfex": {
        "品种": "variety", "合约代码": "symbol", "交易单位": "contract_unit",
        "最小变动单位": "tick_size", "开始交易日": "listing_date",
        "最后交易日": "last_trading_day", "最后交割日": "last_delivery_day",
    },
    "cffex": {
        "合约代码": "symbol", "品种": "variety", "合约月份": "contract_month",
        "上市日": "listing_date", "最后交易日": "last_trading_day",
        "涨停板幅度": "limit_up_pct", "跌停板幅度": "limit_down_pct",
        "涨停板价位": "limit_up_price", "跌停板价位": "limit_down_price",
        "持仓限额": "position_limit", "查询交易日": "trade_date",
    },
    "czce": {
        "合约代码": "symbol", "产品名称": "variety", "最小变动价位": "tick_size",
        "交易单位": "contract_unit", "第一交易日": "listing_date",
        "最后交割日": "last_delivery_day", "涨跌停板": "price_limit_pct",
        # CZCE's "last trading day" column name embeds a temporary caveat
        # about a pending holiday-schedule announcement baked in by akshare
        # itself (e.g. "最后交易日待国家公布2025年节假日安排后进行调整") -- not a
        # stable key, so akshare_mcp.instruments locates it by a "最后交易日"
        # prefix match at call time instead of listing it here.
    },
}
