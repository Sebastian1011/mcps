"""Registry vs. installed akshare drift detector.

registry.py's adapters call specific akshare functions with specific
keyword arguments, verified against akshare 1.18.80's source during
development (see the plan doc for the trace). This test doesn't re-import
registry.py's internals (they're closures, not introspectable) -- instead
it mirrors that same call surface as a flat table and asserts every
function still exists with the parameter names we depend on. If a future
akshare upgrade renames/removes one of these, this test fails immediately
instead of registry.py silently breaking at request time.
"""

from __future__ import annotations

import inspect

import akshare as ak
import pytest

# (function name, required parameter names)
CALLS: list[tuple[str, list[str]]] = [
    ("stock_zh_a_spot_em", []),
    ("stock_individual_spot_xq", ["symbol"]),
    ("stock_zh_a_hist", ["symbol", "period", "start_date", "end_date", "adjust"]),
    ("stock_zh_a_hist_min_em", ["symbol", "start_date", "end_date", "period", "adjust"]),
    ("stock_hk_spot_em", []),
    ("stock_hk_hist", ["symbol", "period", "start_date", "end_date", "adjust"]),
    ("stock_hk_hist_min_em", ["symbol", "period", "adjust", "start_date", "end_date"]),
    ("stock_us_spot_em", []),
    ("stock_us_hist", ["symbol", "period", "start_date", "end_date", "adjust"]),
    ("stock_us_hist_min_em", ["symbol", "start_date", "end_date"]),
    ("stock_zh_index_spot_em", ["symbol"]),
    ("index_zh_a_hist", ["symbol", "period", "start_date", "end_date"]),
    ("index_zh_a_hist_min_em", ["symbol", "period", "start_date", "end_date"]),
    ("index_global_spot_em", []),
    ("index_global_hist_em", ["symbol"]),
    ("fund_etf_spot_em", []),
    ("fund_etf_hist_em", ["symbol", "period", "start_date", "end_date", "adjust"]),
    ("fund_etf_hist_min_em", ["symbol", "start_date", "end_date", "period", "adjust"]),
    ("fund_lof_spot_em", []),
    ("fund_lof_hist_em", ["symbol", "period", "start_date", "end_date", "adjust"]),
    ("fund_lof_hist_min_em", ["symbol", "start_date", "end_date", "period", "adjust"]),
    ("futures_zh_realtime", ["symbol"]),
    ("futures_symbol_mark", []),
    ("futures_zh_daily_sina", ["symbol"]),
    ("futures_zh_minute_sina", ["symbol", "period"]),
    ("futures_global_spot_em", []),
    ("futures_global_hist_em", ["symbol"]),
    ("forex_spot_em", []),
    ("forex_hist_em", ["symbol"]),
    ("crypto_js_spot", []),
    ("bond_zh_hs_cov_spot", []),
    ("bond_zh_hs_cov_daily", ["symbol"]),
    ("bond_zh_hs_spot", []),
    ("bond_zh_hs_daily", ["symbol"]),
    ("reits_realtime_em", []),
    ("reits_hist_em", ["symbol"]),
    ("spot_quotations_sge", ["symbol"]),
    ("spot_hist_sge", ["symbol"]),
    ("fund_open_fund_daily_em", []),
    ("fund_open_fund_info_em", ["symbol", "indicator", "period"]),
]


@pytest.mark.parametrize("name,required_params", CALLS, ids=[c[0] for c in CALLS])
def test_akshare_function_signature(name: str, required_params: list[str]) -> None:
    fn = getattr(ak, name, None)
    assert fn is not None, f"akshare no longer exposes ak.{name} -- registry.py needs an update"
    sig = inspect.signature(fn)
    missing = [p for p in required_params if p not in sig.parameters]
    assert not missing, f"ak.{name} signature changed: missing params {missing} (has {list(sig.parameters)})"


def test_all_markets_have_a_spot_table() -> None:
    from akshare_mcp.registry import MARKETS

    assert len(MARKETS) == 16, f"expected 16 markets, found {len(MARKETS)}: {sorted(MARKETS)}"
    for key, spec in MARKETS.items():
        assert spec.spot_table is not None, f"{key} has no spot_table"
        assert spec.key == key


def test_native_intervals_are_canonical() -> None:
    from akshare_mcp.intervals import CANONICAL_INTERVALS
    from akshare_mcp.registry import MARKETS

    for key, spec in MARKETS.items():
        for interval in spec.native_intervals:
            assert interval in CANONICAL_INTERVALS, f"{key} declares non-canonical interval {interval!r}"
