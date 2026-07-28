from __future__ import annotations

import os
from datetime import date

from akshare_mcp.cache import ResponseCache, history_cache_tier, make_key
from akshare_mcp.config import Settings


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


def test_make_key_is_stable_and_sensitive_to_params() -> None:
    a = make_key("hist", market="cn_stock", symbol="600519", interval="1d")
    b = make_key("hist", market="cn_stock", symbol="600519", interval="1d")
    c = make_key("hist", market="cn_stock", symbol="600519", interval="1w")
    assert a == b
    assert a != c
    assert a.startswith("hist:")


def test_history_cache_tier_closed_for_past_end_date(tmp_path) -> None:
    settings = _settings(tmp_path, tz="Asia/Shanghai")
    past = date(2020, 1, 1).isoformat()
    tier, ttl = history_cache_tier(settings, past)
    assert tier == "closed"
    assert ttl == settings.cache_ttl_closed


def test_history_cache_tier_open_when_end_missing_or_today_or_future(tmp_path) -> None:
    settings = _settings(tmp_path)
    tier, ttl = history_cache_tier(settings, None)
    assert (tier, ttl) == ("open", settings.cache_ttl_open)

    from datetime import datetime

    today_str = datetime.now(tz=settings.tz).date().isoformat()
    tier2, ttl2 = history_cache_tier(settings, today_str)
    assert (tier2, ttl2) == ("open", settings.cache_ttl_open)

    future = date(2999, 1, 1).isoformat()
    tier3, ttl3 = history_cache_tier(settings, future)
    assert (tier3, ttl3) == ("open", settings.cache_ttl_open)


def test_response_cache_roundtrip_and_expiry(tmp_path) -> None:
    settings = _settings(tmp_path)
    cache = ResponseCache(settings)
    try:
        key = make_key("hist", market="cn_stock", symbol="600519")
        assert cache.get(key) is None
        cache.set(key, {"columns": ["date"], "rows": [["2025-01-01"]]}, ttl=60)
        assert cache.get(key) == {"columns": ["date"], "rows": [["2025-01-01"]]}

        expiring_key = make_key("hist", market="cn_stock", symbol="expiring")
        cache.set(expiring_key, "value", ttl=0)
        assert cache.get(expiring_key) is None
    finally:
        cache.close()
