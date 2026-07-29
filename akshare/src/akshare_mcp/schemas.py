"""Structured, offline metadata describing every market's symbol format and
data schema -- the single source of truth backing the `describe_market` tool
(and, by delegation, the `akshare://markets` resource).

Field names/sets here were derived from the actual akshare 1.18.80 source --
the literal `.columns = [...]` assignments and `.rename(columns={...})`
dicts inside each wrapped function -- cross-referenced against
`registry.py`'s `_select()` projections and `normalize.CN_COLUMN_MAP` /
`normalize.XQ_ITEM_MAP`, not a live pull. That means `describe_market` never
makes a network request. `tests/test_schemas.py` cross-checks `realtime_fields`
against `registry.py`'s `_select()` lists wherever a market curates one, so
drift between this file and the adapters it describes is caught offline.

A few history field sets (the bond markets' sina-JS-decoded payloads) can't
be pinned down from a static column literal the way the rest can; those are
marked "best-effort" in their market's `caveats` and cross-checked live in
`tests/test_live.py` instead.
"""

from __future__ import annotations

from dataclasses import dataclass

from akshare_mcp.intervals import CANONICAL_INTERVALS, _RANK


@dataclass(frozen=True)
class FieldSpec:
    type: str  # "string" | "number" | "date" | "date_or_datetime" | "datetime"
    unit: str  # "-" when not applicable/dimensionless
    description: str


# Canonical field name -> type/unit/description. Keys match whatever
# normalize_frame()/xq_to_record()/the bespoke open_fund normalizer actually
# emit; see each MarketSchema's `realtime_fields`/`history_fields` below for
# which of these apply to which market.
FIELDS: dict[str, FieldSpec] = {
    "symbol": FieldSpec(
        "string", "-",
        "Exchange/instrument code in this market's native format. list_instruments() normalizes akshare's "
        "own instrument-table column names ('code', 'index_code', ...) to this same field for consistency.",
    ),
    "name": FieldSpec(
        "string", "-",
        "Display name (usually Chinese). list_instruments() normalizes akshare's own 'display_name' etc. to this.",
    ),
    "publish_date": FieldSpec("string", "-", "Index base/publish date (cn_index instrument listing)."),
    "exchange": FieldSpec("string", "-", "Exchange or market segment label."),
    "variety": FieldSpec("string", "-", "Chinese futures variety name, e.g. '螺纹钢' (cn_futures instrument listing / contract spec)."),
    "last": FieldSpec("number", "quote_currency", "Most recent traded price."),
    "open": FieldSpec("number", "quote_currency", "Session/period open price."),
    "high": FieldSpec("number", "quote_currency", "Session/period high price."),
    "low": FieldSpec("number", "quote_currency", "Session/period low price."),
    "close": FieldSpec("number", "quote_currency", "Session/period close price (history bars)."),
    "prev_close": FieldSpec("number", "quote_currency", "Previous session's close."),
    "prev_settle": FieldSpec("number", "quote_currency", "Previous session's settlement price (futures)."),
    "settlement": FieldSpec("number", "quote_currency", "Current/estimated settlement price (cn_futures realtime)."),
    "settle": FieldSpec(
        "number", "quote_currency",
        "Settlement price. cn_futures history leaves akshare's bare 'settle' column name as-is instead of "
        "renaming it -- see that market's caveats.",
    ),
    "change": FieldSpec("number", "quote_currency", "Absolute change vs. previous close/settle."),
    "change_pct": FieldSpec("number", "percent", "Percentage change vs. previous close/settle."),
    "amplitude": FieldSpec("number", "percent", "(high-low)/prev_close swing over the session/period."),
    "volume": FieldSpec("number", "shares_or_lots", "Traded volume; unit is shares/lots/contracts depending on market -- see caveats."),
    "amount": FieldSpec("number", "quote_currency", "Traded turnover value."),
    "turnover_rate": FieldSpec("number", "percent", "Turnover rate (volume / free float)."),
    "volume_ratio": FieldSpec("number", "ratio", "Volume ratio vs. a recent average."),
    "pe_ttm": FieldSpec("number", "ratio", "Price/earnings (trailing twelve months, or dynamic -- market-dependent)."),
    "pe_dynamic": FieldSpec("number", "ratio", "Price/earnings, dynamic (xq single-symbol fast path only)."),
    "pe_static": FieldSpec("number", "ratio", "Price/earnings, static/most recent annual report (xq single-symbol fast path only)."),
    "pb": FieldSpec("number", "ratio", "Price/book ratio."),
    "market_cap": FieldSpec("number", "quote_currency", "Total market capitalization."),
    "circulating_market_cap": FieldSpec("number", "quote_currency", "Free-float/circulating market capitalization."),
    "iopv": FieldSpec("number", "quote_currency", "Indicative optimized portfolio value (ETF real-time NAV estimate)."),
    "discount_rate": FieldSpec("number", "percent", "ETF premium/discount rate vs. IOPV."),
    "open_interest": FieldSpec("number", "contracts", "Open interest (cn_futures realtime / global_futures)."),
    "oi_change": FieldSpec("number", "contracts", "Day-over-day change in open interest."),
    "hold": FieldSpec(
        "number", "contracts",
        "Open interest. cn_futures history keeps akshare's bare 'hold' column name instead of renaming it to "
        "open_interest like the realtime path -- see that market's caveats.",
    ),
    "bid": FieldSpec("number", "quote_currency", "Best bid price."),
    "ask": FieldSpec("number", "quote_currency", "Best ask price."),
    "buy": FieldSpec(
        "number", "quote_currency",
        "Best bid price. convertible_bond's realtime source uses bare 'buy'/'sell' (unlike cn_bond's "
        "'买入'/'卖出', which map to bid/ask) -- see that market's caveats.",
    ),
    "sell": FieldSpec("number", "quote_currency", "Best ask price (see 'buy')."),
    "avg_price": FieldSpec("number", "quote_currency", "Volume-weighted average price over the bar (intraday history)."),
    "eps": FieldSpec("number", "quote_currency", "Earnings per share (xq single-symbol fast path only)."),
    "bvps": FieldSpec("number", "quote_currency", "Book value per share (xq single-symbol fast path only)."),
    "dividend_ttm": FieldSpec("number", "quote_currency", "Dividend per share, trailing twelve months (xq single-symbol fast path only)."),
    "dividend_yield_ttm": FieldSpec("number", "percent", "Dividend yield, trailing twelve months (xq single-symbol fast path only)."),
    "week52_high": FieldSpec("number", "quote_currency", "52-week high (xq single-symbol fast path only)."),
    "week52_low": FieldSpec("number", "quote_currency", "52-week low (xq single-symbol fast path only)."),
    "limit_up": FieldSpec("number", "quote_currency", "Today's price-limit ceiling (xq single-symbol fast path only)."),
    "limit_down": FieldSpec("number", "quote_currency", "Today's price-limit floor (xq single-symbol fast path only)."),
    "ytd_change_pct": FieldSpec("number", "percent", "Year-to-date change (xq single-symbol fast path only)."),
    "shares_circulating": FieldSpec("number", "shares", "Free-float share count (xq single-symbol fast path only)."),
    "currency": FieldSpec("string", "-", "Quote currency code, e.g. 'USD' (xq single-symbol fast path only)."),
    "updated_at": FieldSpec("datetime", "-", "Timestamp of this quote/row."),
    "data_date": FieldSpec("date", "-", "As-of date for a data snapshot."),
    "trade_date": FieldSpec("date", "-", "Trade date."),
    "date": FieldSpec(
        "date_or_datetime", "-",
        "Bar timestamp: 'YYYY-MM-DD' for 1d/1w/1mo bars, 'YYYY-MM-DD HH:MM:SS' for intraday (1m..60m).",
    ),
    "time": FieldSpec("string", "-", "Intraday tick clock, 'HH:MM' (sge_spot realtime only)."),
    "nav": FieldSpec("number", "quote_currency", "Unit net asset value (open_fund)."),
    "nav_date": FieldSpec("date", "-", "NAV as-of date (open_fund)."),
    "cumulative_nav": FieldSpec("number", "quote_currency", "Cumulative NAV including historical distributions (open_fund)."),
    "subscription_status": FieldSpec("string", "-", "Fund subscription status, e.g. '开放申购' (open_fund)."),
    "redemption_status": FieldSpec("string", "-", "Fund redemption status (open_fund)."),
    "fee": FieldSpec("string", "-", "Subscription fee, as text (e.g. '0.15%') (open_fund)."),
    "fund_type": FieldSpec("string", "-", "Fund category (open_fund instrument listing)."),
    "pinyin": FieldSpec("string", "-", "Pinyin abbreviation, for search (open_fund instrument listing)."),
    "pinyin_full": FieldSpec("string", "-", "Full pinyin spelling, for search (open_fund instrument listing)."),
    "contract_unit": FieldSpec("string", "-", "Trading unit per contract, e.g. '10吨/手' (cn_futures contract spec)."),
    "tick_size": FieldSpec("number", "quote_currency", "Minimum price movement (cn_futures contract spec)."),
    "price_limit_pct": FieldSpec(
        "string", "-",
        "Daily price-limit band as published by the exchange, as one combined text value (cn_futures "
        "contract spec; CZCE only -- CFFEX publishes separate limit_up_pct/limit_down_pct instead).",
    ),
    "limit_up_pct": FieldSpec("number", "percent", "Daily up-limit band (cn_futures contract spec; CFFEX only)."),
    "limit_down_pct": FieldSpec("number", "percent", "Daily down-limit band (cn_futures contract spec; CFFEX only)."),
    "limit_up_price": FieldSpec("number", "quote_currency", "Today's absolute up-limit price (cn_futures contract spec; CFFEX only)."),
    "limit_down_price": FieldSpec("number", "quote_currency", "Today's absolute down-limit price (cn_futures contract spec; CFFEX only)."),
    "contract_month": FieldSpec("string", "-", "Contract delivery month, e.g. '2410' (cn_futures contract spec; CFFEX only)."),
    "position_limit": FieldSpec("number", "contracts", "Position limit (cn_futures contract spec; CFFEX only)."),
    "listing_date": FieldSpec("date", "-", "Contract listing date (cn_futures contract spec, where published)."),
    "last_trading_day": FieldSpec(
        "date", "-",
        "Last trading day (cn_futures contract spec). SHFE/INE don't publish this field directly -- "
        "'expiry_date' is used in its place there and may not always coincide with the actual last trading day.",
    ),
    "last_delivery_day": FieldSpec("date", "-", "Last delivery day (cn_futures contract spec)."),
    "expiry_date": FieldSpec("date", "-", "Contract expiry date (cn_futures contract spec; SHFE/INE only)."),
    "delivery_start_date": FieldSpec("date", "-", "First delivery date (cn_futures contract spec; SHFE/INE only)."),
    "listing_base_price": FieldSpec(
        "number", "quote_currency", "Reference price used when the contract was first listed (cn_futures contract spec; SHFE/INE only).",
    ),
}

# The single-symbol realtime fast path (ak.stock_individual_spot_xq, used by
# cn_stock/hk_stock/us_stock's spot_single) pivots a completely different,
# wider field set via normalize.XQ_ITEM_MAP -- listed once here and
# referenced from each of those three markets' caveats instead of repeating
# a copy of XQ_ITEM_MAP's values three times.
XQ_SINGLE_QUOTE_FIELDS: tuple[str, ...] = (
    "symbol", "name", "exchange", "last", "change", "change_pct", "open", "high", "low", "prev_close",
    "volume", "amount", "updated_at", "avg_price", "amplitude", "turnover_rate", "volume_ratio", "pb",
    "pe_ttm", "pe_dynamic", "pe_static", "eps", "bvps", "dividend_ttm", "dividend_yield_ttm",
    "week52_high", "week52_low", "limit_up", "limit_down", "ytd_change_pct", "shares_circulating",
    "circulating_market_cap", "market_cap", "currency",
)

# Generic daily/weekly/monthly OHLCV field set shared by the four markets on
# the East Money kline endpoint family (_std_em_kline: cn_stock, hk_stock,
# etf, lof, cn_index) -- cn_stock's history additionally appends "symbol"
# (its underlying stock_zh_a_hist call is the only one of the family whose
# raw output includes a 股票代码 column).
_EM_DAILY_FIELDS: tuple[str, ...] = (
    "date", "open", "close", "high", "low", "volume", "amount", "amplitude", "change_pct", "change", "turnover_rate",
)
# Intraday minute fields for the same family, EXCEPT hk_stock/us_stock whose
# minute endpoint reports "last" instead of a bar "avg_price" -- see those
# two markets' caveats.
_EM_INTRADAY_FIELDS: tuple[str, ...] = ("date", "open", "close", "high", "low", "volume", "amount", "avg_price")
_EM_INTRADAY_FIELDS_LAST: tuple[str, ...] = ("date", "open", "close", "high", "low", "volume", "amount", "last")


@dataclass(frozen=True)
class SymbolFormat:
    pattern: str
    examples: tuple[str, ...]
    notes: str = ""


@dataclass(frozen=True)
class MarketSchema:
    symbol_format: SymbolFormat
    realtime_fields: tuple[str, ...]
    history_fields: tuple[str, ...] = ()
    history_fields_intraday: tuple[str, ...] = ()
    caveats: tuple[str, ...] = ()


MARKET_SCHEMAS: dict[str, MarketSchema] = {
    "cn_stock": MarketSchema(
        symbol_format=SymbolFormat(
            "6-digit code, optionally sh/sz/bj-prefixed", ("600519", "000001", "sh600519"),
            "An sh/sz/bj prefix is stripped automatically for history lookups.",
        ),
        realtime_fields=(
            "symbol", "name", "last", "change", "change_pct", "open", "high", "low", "prev_close",
            "volume", "amount", "turnover_rate", "volume_ratio", "pe_ttm", "pb", "market_cap", "circulating_market_cap",
        ),
        history_fields=_EM_DAILY_FIELDS + ("symbol",),
        history_fields_intraday=_EM_INTRADAY_FIELDS,
        caveats=(
            "the single-symbol fast path (get_realtime_quotes with `symbols=[...]`) returns a different, "
            "wider field set -- see XQ_SINGLE_QUOTE_FIELDS -- because it hits the xueqiu single-quote "
            "endpoint instead of the whole-market table",
        ),
    ),
    "hk_stock": MarketSchema(
        symbol_format=SymbolFormat(
            "5-digit code, zero-padded", ("00700", "700"),
            "Bare digits are zero-padded to 5 for the single-symbol fast path; an sh/sz/bj prefix (rare for "
            "this market) is stripped for history lookups.",
        ),
        realtime_fields=("symbol", "name", "last", "change", "change_pct", "open", "high", "low", "prev_close", "volume", "amount"),
        history_fields=_EM_DAILY_FIELDS,
        history_fields_intraday=_EM_INTRADAY_FIELDS_LAST,
        caveats=(
            "the single-symbol fast path returns a different, wider field set -- see XQ_SINGLE_QUOTE_FIELDS",
            "intraday minute bars report 'last' (not 'avg_price' like cn_stock/etf/lof/cn_index minute bars)",
        ),
    ),
    "us_stock": MarketSchema(
        symbol_format=SymbolFormat(
            "ticker", ("AAPL", "MSFT"),
            "Resolved internally to East Money's market-prefixed code (e.g. '105.AAPL') via a 24h-cached "
            "symbol table; an already-prefixed input passes through untouched.",
        ),
        realtime_fields=("symbol", "name", "last", "change", "change_pct", "open", "high", "low", "prev_close", "volume", "amount", "market_cap", "pe_ttm"),
        history_fields=_EM_DAILY_FIELDS,
        history_fields_intraday=_EM_INTRADAY_FIELDS_LAST,
        caveats=(
            "the single-symbol fast path returns a different, wider field set -- see XQ_SINGLE_QUOTE_FIELDS",
            "minute bars (interval='1m') only cover roughly the last 5 trading days and ignore `adjust` "
            "(upstream limitation, not this server's)",
        ),
    ),
    "cn_index": MarketSchema(
        symbol_format=SymbolFormat(
            "6-digit index code", ("000300", "000001"),
            "No single-symbol realtime fast path exists for indices; an sh/sz/bj prefix is stripped for history.",
        ),
        realtime_fields=("symbol", "name", "last", "change_pct", "change", "volume", "amount", "amplitude", "high", "low", "open", "prev_close", "volume_ratio"),
        history_fields=_EM_DAILY_FIELDS,
        history_fields_intraday=_EM_INTRADAY_FIELDS,
        caveats=("adjust is not applicable to indices and is always ignored",),
    ),
    "global_index": MarketSchema(
        symbol_format=SymbolFormat(
            "East Money Chinese display name", ("美元指数", "道琼斯"),
            "Not a ticker -- must match a name as listed by list_instruments(market='global_index'). akshare "
            "also has an `index_global_name_table` (Sina) name/code table, but it uses an incompatible "
            "symbol vocabulary from the East Money endpoints this market's spot/history actually call, so "
            "it is intentionally not used for instrument lookups here.",
        ),
        realtime_fields=("symbol", "name", "last", "change", "change_pct", "open", "high", "low", "prev_close", "amplitude", "updated_at"),
        history_fields=("date", "open", "close", "high", "low", "amplitude", "symbol", "name"),
        caveats=(
            "daily-only at the source; weekly/monthly are resampled and drop the non-OHLCV columns "
            "(amplitude, symbol, name)",
            "the history endpoint has no date-range parameters -- full history is fetched and filtered client-side",
            "adjust is not applicable and is always ignored",
        ),
    ),
    "etf": MarketSchema(
        symbol_format=SymbolFormat("6-digit fund code, optionally sh/sz-prefixed", ("510300",)),
        realtime_fields=(
            "symbol", "name", "last", "change", "change_pct", "open", "high", "low", "prev_close",
            "volume", "amount", "turnover_rate", "iopv", "discount_rate", "circulating_market_cap", "market_cap",
        ),
        history_fields=_EM_DAILY_FIELDS,
        history_fields_intraday=_EM_INTRADAY_FIELDS,
    ),
    "lof": MarketSchema(
        symbol_format=SymbolFormat("6-digit fund code, optionally sh/sz-prefixed", ("166009",)),
        realtime_fields=(
            "symbol", "name", "last", "change", "change_pct", "volume", "amount", "open", "high", "low",
            "prev_close", "turnover_rate", "circulating_market_cap", "market_cap",
        ),
        history_fields=_EM_DAILY_FIELDS,
        history_fields_intraday=_EM_INTRADAY_FIELDS,
    ),
    "cn_futures": MarketSchema(
        symbol_format=SymbolFormat(
            "contract code for history ('RB0' main continuous, 'RB2510' specific); contract code or Chinese "
            "variety name for realtime", ("RB0", "RB2510", "螺纹钢"),
            "Realtime and history use different symbol vocabularies -- see this market's description.",
        ),
        realtime_fields=("symbol", "exchange", "name", "last", "open", "high", "low", "prev_close", "volume", "open_interest", "change_pct", "settlement", "updated_at"),
        history_fields=("date", "open", "high", "low", "close", "volume", "hold", "settle"),
        history_fields_intraday=("date", "open", "high", "low", "close", "volume", "hold"),
        caveats=(
            "history's 'hold'/'settle' column names are left as-is rather than renamed to "
            "open_interest/settlement like the realtime path -- see FIELDS['hold']/FIELDS['settle']",
            "adjust is not applicable to futures and is always ignored",
            "the realtime table always returns the whole contract chain for one variety, not a single instrument",
            "list_instruments(market='cn_futures', include_spec=True) adds per-contract trading specs from "
            "each exchange's own contract-info endpoint, but coverage is exchange-dependent: SHFE/INE give "
            "listing/expiry/delivery dates and a listing base price but no contract_unit/tick_size; "
            "DCE/GFEX give contract_unit/tick_size/listing_date/last_trading_day/last_delivery_day but no "
            "price-limit band; CFFEX gives limit_up_pct/limit_down_pct/limit_up_price/limit_down_price/ "
            "contract_month/position_limit but no contract_unit/tick_size/last_delivery_day; CZCE gives "
            "contract_unit/tick_size/listing_date/last_trading_day/last_delivery_day plus a combined "
            "price_limit_pct text; contracts whose prefix isn't in symbols._FUTURES_PREFIX_TO_VARIETY "
            "(e.g. INE's SC/LU/NR/EC) get a note instead of a spec",
        ),
    ),
    "global_futures": MarketSchema(
        symbol_format=SymbolFormat(
            "East Money quote code", ("HG00Y",),
            "As listed by list_instruments(market='global_futures'); 'HG00Y' is COMEX copper.",
        ),
        realtime_fields=("symbol", "name", "last", "change", "change_pct", "open", "high", "low", "prev_settle", "volume", "open_interest"),
        history_fields=("date", "symbol", "name", "open", "close", "high", "low", "volume", "change_pct", "open_interest", "oi_change"),
        caveats=(
            "daily-only; the history endpoint has no date-range parameters -- full history is fetched and "
            "filtered client-side",
            "adjust is not applicable and is always ignored",
        ),
    ),
    "forex": MarketSchema(
        symbol_format=SymbolFormat("currency pair", ("USDCNH",)),
        realtime_fields=("symbol", "name", "last", "change", "change_pct", "open", "high", "low", "prev_close"),
        history_fields=("date", "open", "close", "high", "low", "amplitude", "symbol", "name"),
        caveats=(
            "daily-only; the history endpoint has no date-range parameters -- full history is fetched and "
            "filtered client-side",
            "adjust is not applicable and is always ignored",
        ),
    ),
    "crypto": MarketSchema(
        symbol_format=SymbolFormat("major cryptocurrency ticker", ("BTC", "ETH")),
        realtime_fields=("exchange", "symbol", "last", "change", "change_pct", "high", "low", "volume", "updated_at"),
        caveats=("no history: akshare has no matching history function for this market",),
    ),
    "convertible_bond": MarketSchema(
        symbol_format=SymbolFormat(
            "6-digit code, optionally sh/sz-prefixed", ("113050", "sh113050"),
            "When unprefixed, both sh/sz prefixes are tried in turn and whichever succeeds is used.",
        ),
        realtime_fields=("symbol", "name", "last", "change", "change_pct", "open", "high", "low", "prev_close", "volume", "amount", "buy", "sell", "updated_at"),
        history_fields=("date", "open", "high", "low", "close", "volume"),
        caveats=(
            "realtime 'buy'/'sell' are the best bid/ask, left un-renamed -- see FIELDS['buy']",
            "daily-only; adjust is not applicable and is always ignored",
            "history field set is inferred from the upstream sina JS-decoded payload rather than a static "
            "column literal (best-effort; cross-checked live in tests/test_live.py)",
        ),
    ),
    "cn_bond": MarketSchema(
        symbol_format=SymbolFormat(
            "6-digit code, optionally sh/sz-prefixed", ("010107", "sh010107"),
            "When unprefixed, both sh/sz prefixes are tried in turn and whichever succeeds is used.",
        ),
        realtime_fields=("symbol", "name", "last", "change", "change_pct", "bid", "ask", "prev_close", "open", "high", "low", "volume", "amount"),
        history_fields=("date", "open", "high", "low", "close", "volume"),
        caveats=(
            "daily-only; adjust is not applicable and is always ignored",
            "history field set is inferred from the upstream sina JS-decoded payload rather than a static "
            "column literal (best-effort; cross-checked live in tests/test_live.py)",
        ),
    ),
    "reits": MarketSchema(
        symbol_format=SymbolFormat("6-digit code", ("508097",)),
        realtime_fields=("symbol", "name", "last", "change", "change_pct", "volume", "amount", "open", "high", "low", "prev_close"),
        history_fields=("date", "open", "close", "high", "low", "volume", "amount", "amplitude", "turnover_rate"),
        caveats=("daily-only; adjust is not applicable and is always ignored",),
    ),
    "sge_spot": MarketSchema(
        symbol_format=SymbolFormat("SGE product code", ("Au99.99", "Ag(T+D)")),
        realtime_fields=("symbol", "time", "last", "updated_at"),
        history_fields=("date", "open", "close", "low", "high"),
        caveats=(
            "no market-wide realtime endpoint exists upstream -- get_realtime_quotes only fans out over a "
            "6-product default list; list_instruments(market='sge_spot') returns the full 17-product table "
            "via ak.spot_symbol_table_sge() (a local constant, no network call)",
            "daily-only; adjust is not applicable and is always ignored",
        ),
    ),
    "open_fund": MarketSchema(
        symbol_format=SymbolFormat("6-digit fund code", ("710001",)),
        realtime_fields=("symbol", "name", "nav", "nav_date", "cumulative_nav", "change", "change_pct", "subscription_status", "redemption_status", "fee"),
        history_fields=("date", "close", "change_pct"),
        caveats=(
            "NAV-based: no open/high/low/volume; 'close' is the unit NAV",
            "realtime column names are dynamically dated in the raw source (e.g. '2026-07-27-单位净值') and "
            "parsed by a bespoke normalizer instead of CN_COLUMN_MAP",
            "adjust is not applicable and is always ignored",
        ),
    ),
}


def resampled_intervals(native_intervals: tuple[str, ...]) -> tuple[str, ...]:
    """Canonical intervals NOT natively available for a market but obtainable
    by resampling its finest native interval (see intervals.pick_source_interval()
    / intervals.resample_ohlcv()). Resampling keeps only "date" plus whatever
    OHLCV columns are present (intervals._OHLCV_AGG) -- every other column
    (turnover_rate, amplitude, change_pct, symbol, name, ...) is dropped, which
    callers should expect regardless of which market they're resampling.
    """
    if not native_intervals:
        return ()
    finest_rank = min(_RANK[i] for i in native_intervals)
    return tuple(i for i in CANONICAL_INTERVALS if _RANK[i] > finest_rank and i not in native_intervals)
