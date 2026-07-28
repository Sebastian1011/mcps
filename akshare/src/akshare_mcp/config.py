"""Environment-driven configuration.

Plain dataclass instead of pydantic-settings: the surface area here is a
couple dozen scalar env vars, not worth a second settings framework on top
of the one FastMCP already pulls in.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from zoneinfo import ZoneInfo


def _env_str(name: str, default: str) -> str:
    return os.environ.get(name, default)


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return int(raw)


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return float(raw)


@dataclass(frozen=True)
class Settings:
    # transport
    transport: str = field(default_factory=lambda: _env_str("MCP_TRANSPORT", "streamable-http"))
    host: str = field(default_factory=lambda: _env_str("MCP_HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: _env_int("MCP_PORT", 8000))

    # cache
    cache_dir: str = field(default_factory=lambda: _env_str("CACHE_DIR", "/data/cache"))
    cache_size_limit: int = field(default_factory=lambda: _env_int("CACHE_SIZE_LIMIT", 2 * 1024 * 1024 * 1024))
    cache_ttl_closed: int = field(default_factory=lambda: _env_int("CACHE_TTL_CLOSED", 7 * 24 * 3600))
    cache_ttl_open: int = field(default_factory=lambda: _env_int("CACHE_TTL_OPEN", 3600))
    cache_ttl_realtime: int = field(default_factory=lambda: _env_int("CACHE_TTL_REALTIME", 10))
    symbol_table_ttl: int = field(default_factory=lambda: _env_int("SYMBOL_TABLE_TTL", 24 * 3600))

    # source rate limiting / retry
    max_retries: int = field(default_factory=lambda: _env_int("AK_MAX_RETRIES", 3))
    source_concurrency: int = field(default_factory=lambda: _env_int("AK_SOURCE_CONCURRENCY", 2))
    min_interval_eastmoney: float = field(default_factory=lambda: _env_float("AK_MIN_INTERVAL_EASTMONEY", 0.35))
    min_interval_default: float = field(default_factory=lambda: _env_float("AK_MIN_INTERVAL_DEFAULT", 0.15))
    request_timeout: float = field(default_factory=lambda: _env_float("AK_REQUEST_TIMEOUT", 20.0))

    # misc
    tz_name: str = field(default_factory=lambda: _env_str("TZ", "Asia/Shanghai"))
    log_level: str = field(default_factory=lambda: _env_str("LOG_LEVEL", "INFO"))

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.tz_name)


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
