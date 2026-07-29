"""Offline tests for instruments.py -- list_instruments' per-market fetch
logic. Network-touching akshare functions are monkeypatched (never
called for real; that's tests/test_live.py's job), but everything else
(fetch.call's real throttle/retry wrapper, normalize_frame, caching) runs
for real against a tmp_path-backed cache, same pattern as test_cache.py.
"""

from __future__ import annotations

import os

import pandas as pd
import pytest

from akshare_mcp import instruments as inst
from akshare_mcp.cache import ResponseCache
from akshare_mcp.config import Settings
from akshare_mcp.registry import MARKETS, Ctx


def _settings(tmp_path, **overrides) -> Settings:
    env_keys = [
        "MCP_TRANSPORT", "MCP_HOST", "MCP_PORT", "CACHE_DIR", "CACHE_SIZE_LIMIT",
        "CACHE_TTL_CLOSED", "CACHE_TTL_OPEN", "CACHE_TTL_REALTIME", "SYMBOL_TABLE_TTL",
        "AK_MAX_RETRIES", "AK_SOURCE_CONCURRENCY", "AK_MIN_INTERVAL_EASTMONEY",
        "AK_MIN_INTERVAL_DEFAULT", "AK_REQUEST_TIMEOUT", "TZ", "LOG_LEVEL",
    ]
    saved = {k: os.environ.get(k) for k in env_keys}
    try:
        for k in env_keys:
            os.environ.pop(k, None)
        os.environ["CACHE_DIR"] = str(tmp_path)
        for k, v in overrides.items():
            os.environ[k.upper()] = str(v)
        return Settings()
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


@pytest.fixture
def ctx(tmp_path) -> Ctx:
    # max_retries=1 so a monkeypatched failure raises immediately instead of
    # sleeping through fetch.call's real exponential backoff.
    settings = _settings(tmp_path, ak_max_retries=1)
    cache = ResponseCache(settings)
    try:
        yield Ctx(settings=settings, cache=cache)
    finally:
        cache.close()


# ---------------------------------------------------------------------------
# filter_rows
# ---------------------------------------------------------------------------

def test_filter_rows_matches_symbol_or_name_case_insensitively() -> None:
    columns = ["symbol", "name"]
    rows = [["600519", "贵州茅台"], ["000001", "平安银行"], ["AAPL", "Apple Inc"]]
    assert inst.filter_rows(columns, rows, "贵州") == [["600519", "贵州茅台"]]
    assert inst.filter_rows(columns, rows, "aapl") == [["AAPL", "Apple Inc"]]
    assert inst.filter_rows(columns, rows, "6005") == [["600519", "贵州茅台"]]


def test_filter_rows_returns_everything_for_no_or_blank_query() -> None:
    columns = ["symbol", "name"]
    rows = [["600519", "贵州茅台"]]
    assert inst.filter_rows(columns, rows, None) == rows
    assert inst.filter_rows(columns, rows, "   ") == rows


def test_filter_rows_falls_back_to_variety_and_pinyin_columns() -> None:
    columns = ["symbol", "variety", "pinyin"]
    rows = [["RB2510", "螺纹钢", None], ["AU2512", "沪金", "hj"]]
    assert inst.filter_rows(columns, rows, "螺纹") == [["RB2510", "螺纹钢", None]]
    assert inst.filter_rows(columns, rows, "hj") == [["AU2512", "沪金", "hj"]]


def test_filter_rows_with_no_matching_columns_returns_everything() -> None:
    columns = ["foo", "bar"]
    rows = [["a", "b"]]
    assert inst.filter_rows(columns, rows, "a") == rows


# ---------------------------------------------------------------------------
# list_instruments_table dispatch: unknown market, generic fallback
# ---------------------------------------------------------------------------

async def test_list_instruments_table_rejects_unknown_market(ctx) -> None:
    with pytest.raises(ValueError, match="unknown market"):
        await inst.list_instruments_table(ctx, "bogus", None)


async def test_generic_fallback_projects_symbol_name_exchange(ctx, monkeypatch) -> None:
    async def fake_spot_table(_ctx, _hint):
        return (
            ["symbol", "name", "last", "volume"],
            [["USDCNH", "美元人民币", 7.1, 0]],
            ["some note"],
            "akshare:forex_spot_em",
        )

    monkeypatch.setattr(MARKETS["forex"], "spot_table", fake_spot_table)
    result = await inst.list_instruments_table(ctx, "forex", None)
    assert result.columns == ["symbol", "name"]
    assert result.rows == [["USDCNH", "美元人民币"]]
    assert "some note" in result.notes
    assert result.query_handled is False


async def test_generic_fallback_notes_when_no_symbol_name_columns(ctx, monkeypatch) -> None:
    async def fake_spot_table(_ctx, _hint):
        return (["foo", "bar"], [[1, 2]], [], "akshare:whatever")

    monkeypatch.setattr(MARKETS["forex"], "spot_table", fake_spot_table)
    result = await inst.list_instruments_table(ctx, "forex", None)
    assert result.columns == ["foo", "bar"]
    assert any("no symbol/name columns" in n for n in result.notes)


# ---------------------------------------------------------------------------
# cn_stock: dedicated table, with failure fallback
# ---------------------------------------------------------------------------

async def test_cn_stock_instruments_uses_dedicated_table(ctx, monkeypatch) -> None:
    df = pd.DataFrame({"code": ["600519", "000001"], "name": ["贵州茅台", "平安银行"]})
    monkeypatch.setattr(inst.ak, "stock_info_a_code_name", lambda: df)
    result = await inst._cn_stock_instruments(ctx, None)
    assert result.columns == ["symbol", "name"]
    assert result.rows == [["600519", "贵州茅台"], ["000001", "平安银行"]]
    assert result.source == "akshare:stock_info_a_code_name"


async def test_cn_stock_instruments_falls_back_on_upstream_failure(ctx, monkeypatch) -> None:
    def boom():
        raise ConnectionError("nope")

    async def fake_spot_table(_ctx, _hint):
        return (["symbol", "name", "last"], [["600519", "贵州茅台", 1.0]], [], "akshare:stock_zh_a_spot_em")

    monkeypatch.setattr(inst.ak, "stock_info_a_code_name", boom)
    monkeypatch.setattr(MARKETS["cn_stock"], "spot_table", fake_spot_table)
    result = await inst._cn_stock_instruments(ctx, None)
    assert result.columns == ["symbol", "name"]
    assert result.rows == [["600519", "贵州茅台"]]
    assert any("stock_info_a_code_name failed" in n for n in result.notes)


# ---------------------------------------------------------------------------
# sge_spot: local constant table (no network in the real akshare function
# either, but still routed through fetch.call for consistency)
# ---------------------------------------------------------------------------

async def test_sge_spot_instruments_returns_full_product_table(ctx) -> None:
    result = await inst._sge_spot_instruments(ctx, None)
    assert result.source == "akshare:spot_symbol_table_sge"
    assert result.columns == ["symbol"]
    # the real spot_symbol_table_sge() is a local constant with 17 products --
    # this is the whole point of using it instead of get_realtime_quotes'
    # 6-product default fan-out.
    assert len(result.rows) == 17
    assert ["Au99.99"] in result.rows


# ---------------------------------------------------------------------------
# open_fund: dedicated table
# ---------------------------------------------------------------------------

async def test_open_fund_instruments_uses_fund_name_em(ctx, monkeypatch) -> None:
    df = pd.DataFrame({
        "基金代码": ["710001"], "拼音缩写": ["HTZQ"], "基金简称": ["华泰紫金"],
        "基金类型": ["混合型"], "拼音全称": ["huataizijin"],
    })
    monkeypatch.setattr(inst.ak, "fund_name_em", lambda: df)
    result = await inst._open_fund_instruments(ctx, None)
    assert set(result.columns) == {"symbol", "pinyin", "name", "fund_type", "pinyin_full"}
    assert result.source == "akshare:fund_name_em"


# ---------------------------------------------------------------------------
# cn_futures: variety list vs. contract-chain expansion
# ---------------------------------------------------------------------------

async def test_cn_futures_instruments_without_query_lists_varieties(ctx, monkeypatch) -> None:
    df = pd.DataFrame({"exchange": ["上期所"], "symbol": ["螺纹钢"], "mark": ["lwg_qh"]})
    monkeypatch.setattr(inst.ak, "futures_symbol_mark", lambda: df)
    result = await inst._cn_futures_instruments(ctx, None)
    assert result.columns == ["exchange", "variety", "mark"]
    assert result.query_handled is False


async def test_cn_futures_instruments_with_resolvable_query_expands_chain(ctx, monkeypatch) -> None:
    mark_df = pd.DataFrame({"exchange": ["上期所"], "symbol": ["螺纹钢"], "mark": ["lwg_qh"]})
    monkeypatch.setattr(inst.ak, "futures_symbol_mark", lambda: mark_df)

    async def fake_spot_table(_ctx, hint):
        assert hint == "螺纹钢"
        return (["symbol", "name"], [["RB2510", "螺纹钢2510"]], [], "akshare:futures_zh_realtime")

    monkeypatch.setattr(MARKETS["cn_futures"], "spot_table", fake_spot_table)
    result = await inst._cn_futures_instruments(ctx, "RB2510")
    assert result.query_handled is True
    assert result.rows == [["RB2510", "螺纹钢2510"]]
    assert result.source == "akshare:futures_zh_realtime"


async def test_cn_futures_instruments_with_unresolvable_query_falls_back_to_varieties(ctx, monkeypatch) -> None:
    mark_df = pd.DataFrame({"exchange": ["上期所"], "symbol": ["螺纹钢"], "mark": ["lwg_qh"]})
    monkeypatch.setattr(inst.ak, "futures_symbol_mark", lambda: mark_df)
    result = await inst._cn_futures_instruments(ctx, "ZZZ999")
    assert result.query_handled is False
    assert result.columns == ["exchange", "variety", "mark"]


async def test_cn_futures_instruments_chain_expansion_failure_falls_back(ctx, monkeypatch) -> None:
    mark_df = pd.DataFrame({"exchange": ["上期所"], "symbol": ["螺纹钢"], "mark": ["lwg_qh"]})
    monkeypatch.setattr(inst.ak, "futures_symbol_mark", lambda: mark_df)

    async def boom(_ctx, _hint):
        raise ConnectionError("upstream down")

    monkeypatch.setattr(MARKETS["cn_futures"], "spot_table", boom)
    result = await inst._cn_futures_instruments(ctx, "RB2510")
    assert result.query_handled is False
    assert any("could not expand contract chain" in n for n in result.notes)


# ---------------------------------------------------------------------------
# QUERY_SENSITIVE_MARKETS
# ---------------------------------------------------------------------------

def test_only_cn_futures_is_query_sensitive() -> None:
    assert inst.QUERY_SENSITIVE_MARKETS == {"cn_futures"}


# ---------------------------------------------------------------------------
# fetch_cn_futures_contract_specs
# ---------------------------------------------------------------------------

async def test_contract_specs_notes_unresolved_prefix(ctx) -> None:
    columns, by_symbol, notes = await inst.fetch_cn_futures_contract_specs(ctx, ["ZZZ999"])
    assert by_symbol["ZZZ999"] == [None] * len(columns)
    assert any("no contract-info source known" in n for n in notes)


async def test_contract_specs_joins_dce_by_symbol(ctx, monkeypatch) -> None:
    df = pd.DataFrame({
        "品种名称": ["豆粕"], "合约": ["M2409"], "交易单位": [10], "最小变动价位": [1.0],
        "开始交易日": ["20230101"], "最后交易日": ["20240909"], "最后交割日": ["20240912"],
    })
    monkeypatch.setattr(inst.ak, "futures_contract_info_dce", lambda: df)
    columns, by_symbol, notes = await inst.fetch_cn_futures_contract_specs(ctx, ["M2409"])
    assert "contract_unit" in columns and "tick_size" in columns
    record = dict(zip(columns, by_symbol["M2409"]))
    assert record["variety"] == "豆粕"
    assert record["contract_unit"] == 10
    assert record["exchange"] == "dce"


async def test_contract_specs_one_exchange_failure_does_not_block_others(ctx, monkeypatch) -> None:
    def boom():
        raise ConnectionError("dce down")

    dce_df = pd.DataFrame({
        "品种名称": ["豆粕"], "合约": ["M2409"], "交易单位": [10], "最小变动价位": [1.0],
        "开始交易日": ["20230101"], "最后交易日": ["20240909"], "最后交割日": ["20240912"],
    })

    def dce_ok():
        return dce_df

    monkeypatch.setattr(inst.ak, "futures_contract_info_gfex", boom)
    monkeypatch.setattr(inst.ak, "futures_contract_info_dce", dce_ok)
    columns, by_symbol, notes = await inst.fetch_cn_futures_contract_specs(ctx, ["M2409", "SI2409"])
    assert dict(zip(columns, by_symbol["M2409"]))["variety"] == "豆粕"
    assert by_symbol["SI2409"] == [None] * len(columns)
    assert any("gfex" in n and "failed" in n for n in notes)


async def test_contract_specs_are_cached_across_calls(ctx, monkeypatch) -> None:
    calls = {"n": 0}
    df = pd.DataFrame({
        "品种名称": ["豆粕"], "合约": ["M2409"], "交易单位": [10], "最小变动价位": [1.0],
        "开始交易日": ["20230101"], "最后交易日": ["20240909"], "最后交割日": ["20240912"],
    })

    def counting_fn():
        calls["n"] += 1
        return df

    monkeypatch.setattr(inst.ak, "futures_contract_info_dce", counting_fn)
    await inst.fetch_cn_futures_contract_specs(ctx, ["M2409"])
    await inst.fetch_cn_futures_contract_specs(ctx, ["M2409"])
    assert calls["n"] == 1
