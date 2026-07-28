"""Live network smoke tests -- one realtime + one history call per asset
class family, through the actual MCP tool functions (not mocked). Skipped
by default (see pyproject.toml's `addopts = -m "not live"`); run explicitly
with:

    uv run pytest -m live

These hit real upstream endpoints (East Money, Sina, xueqiu, SGE, jin10) and
are the only place in the test suite that can be flaky due to upstream rate
limiting -- see fetch.py's docstring. A failure here doesn't necessarily
mean the code is wrong; rerun after a minute if it looks like a throttle.
"""

from __future__ import annotations

import pytest

from akshare_mcp.server import get_history_bars, get_realtime_quotes

pytestmark = pytest.mark.live


@pytest.mark.asyncio
async def test_realtime_cn_stock_single_symbol_fast_path() -> None:
    result = await get_realtime_quotes(market="cn_stock", symbols=["600519"])
    assert result["returned"] == 1
    assert "last" in result["columns"]


@pytest.mark.asyncio
async def test_realtime_cn_stock_table() -> None:
    result = await get_realtime_quotes(market="cn_stock", limit=5)
    assert result["returned"] == 5
    assert result["total"] > 1000


@pytest.mark.asyncio
async def test_history_cn_stock_daily() -> None:
    result = await get_history_bars(
        market="cn_stock", symbol="600519", interval="1d", start="2025-01-01", end="2025-01-15"
    )
    assert result["count"] > 0
    assert result["columns"][:5] == ["date", "open", "close", "high", "low"] or "close" in result["columns"]


@pytest.mark.asyncio
async def test_history_resamples_weekly_from_daily_only_source() -> None:
    result = await get_history_bars(
        market="global_index", symbol="美元指数", interval="1w", start="2025-01-01", end="2025-02-01"
    )
    assert result["source_interval"] == "1d"
    assert result["interval"] == "1w"
    assert result["count"] > 0


@pytest.mark.asyncio
async def test_history_bars_are_cached_on_second_call() -> None:
    kwargs = dict(market="cn_stock", symbol="000001", interval="1d", start="2024-01-01", end="2024-01-10")
    first = await get_history_bars(**kwargs)
    second = await get_history_bars(**kwargs)
    assert first["cache"]["hit"] is False
    assert second["cache"]["hit"] is True
    assert second["cache"]["tier"] == "closed"


@pytest.mark.asyncio
async def test_crypto_has_no_history() -> None:
    from mcp.server.fastmcp.exceptions import ToolError

    with pytest.raises(ToolError):
        await get_history_bars(market="crypto", symbol="BTC")
