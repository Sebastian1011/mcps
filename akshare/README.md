# akshare-mcp

An MCP server that wraps [akshare](https://akshare.akfamily.xyz/index.html) (1137+ public functions, wildly
inconsistent naming/columns across markets) into **four** tools:

- **`describe_market`** -- symbol format and full field schema (name/type/unit/description) for one or all
  16 markets. Offline: never hits the network, since it's backed by `schemas.py`, a static description
  verified against akshare's source rather than a live pull.
- **`list_instruments`** -- find/validate a tradable instrument (标的) by code or name within a market,
  instead of guessing a symbol or paging through the whole realtime table.
- **`get_realtime_quotes`** -- realtime quotes across 16 asset classes
- **`get_history_bars`** -- multi-frequency OHLCV history (1m/5m/15m/30m/60m/1d/1w/1mo), with disk-backed
  caching (7 days by default for date ranges that can no longer change)

Everything else -- which akshare function backs which market, symbol format translation, Chinese/English
column normalization, rate limiting, retries, and caching -- happens once inside the server so the tool
surface stays small and uniform regardless of which of the 16 markets is being queried.

## Why only four tools

akshare has zero naming consistency: `stock_zh_a_hist(symbol, period, start_date, end_date, adjust)` vs.
`futures_zh_daily_sina(symbol)` vs. `forex_hist_em(symbol)`, with columns in a mix of Chinese and English
that differ per function. Handing an agent 1000+ raw functions means it has to relearn a different call
shape per asset class, and re-discover it by trial and error since there's nowhere to look up a market's
symbol format or field schema up front. This server does that routing once (`registry.py`), normalizes
every market's output to the same English column vocabulary (`normalize.py`), documents that vocabulary
per market (`schemas.py`), and exposes just the four operations an agent actually needs -- two to discover
what's queryable, two to query it.

## Markets

Call `describe_market()` (or the `akshare://markets` resource, same content) for the live capability
matrix -- native/resampled intervals, adjust support, whether the single-symbol fast path is available,
symbol format, and where `list_instruments` gets its instrument list from. Summary:

| `market` | Asset class | Example `symbol` | Native intervals | `adjust` | Instrument source |
|---|---|---|---|---|---|
| `cn_stock` | A-shares (沪深京) | `600519` | 1m..60m, 1d, 1w, 1mo | yes | `stock_info_a_code_name` |
| `hk_stock` | Hong Kong equities | `00700` | 1m..60m, 1d, 1w, 1mo | yes | realtime table (symbol/name) |
| `us_stock` | US equities | `AAPL` | 1m (~5 recent days only), 1d, 1w, 1mo | yes (daily only) | realtime table (symbol/name) |
| `cn_index` | A-share indices | `000300` | 1m..60m, 1d, 1w, 1mo | no | `index_stock_info` |
| `global_index` | Global indices (Chinese name) | `美元指数` | 1d (+resampled 1w/1mo) | no | realtime table (symbol/name) |
| `etf` | Exchange-traded funds | `510300` | 1m..60m, 1d, 1w, 1mo | yes | realtime table (symbol/name) |
| `lof` | Listed open-ended funds | `166009` | 1m..60m, 1d, 1w, 1mo | yes | realtime table (symbol/name) |
| `cn_futures` | CN commodity/financial futures | `RB0` / `RB2610` | 1m..60m, 1d (+resampled 1w/1mo) | no | `futures_symbol_mark` (variety list; expands to a contract chain, optionally with per-contract specs) |
| `global_futures` | International futures | `HG00Y` | 1d (+resampled) | no | realtime table (symbol/name) |
| `forex` | FX pairs | `USDCNH` | 1d (+resampled) | no | realtime table (symbol/name) |
| `crypto` | Major cryptocurrencies | `BTC` | realtime only, **no history** | no | realtime table (symbol/name) |
| `convertible_bond` | CN convertible bonds | `113050` | 1d (+resampled) | no | realtime table (symbol/name) |
| `cn_bond` | CN plain bonds | `010107` | 1d (+resampled) | no | realtime table (symbol/name) |
| `reits` | CN REITs | `508097` | 1d (+resampled) | no | realtime table (symbol/name) |
| `sge_spot` | Shanghai Gold Exchange spot | `Au99.99` | 1d (+resampled) | no | `spot_symbol_table_sge` (17 products, vs. the realtime tool's 6-product default) |
| `open_fund` | Off-exchange open-end funds (NAV) | `710001` | 1d (+resampled) | no | `fund_name_em` (name + pinyin search) |

Coarser intervals a market doesn't natively provide (e.g. weekly bars for a daily-only market) are
synthesized by resampling the finest available data; requesting a *finer* interval than a market supports
fails with a clear error listing what is actually available.

`cn_futures` realtime and history use different symbol vocabularies (a quirk of the underlying sina/East
Money endpoints, not this server): history wants a contract code (`RB0` for the main continuous contract,
`RB2610` for a specific one), realtime accepts either a contract code (the variety is inferred from a
built-in table of standard exchange prefixes) or a Chinese variety name (`螺纹钢`) and returns the whole
contract chain for that variety.

## Response shape

`get_realtime_quotes`/`get_history_bars` return compact, columnar JSON rather than a list of per-row
objects, to keep token cost down and field names consistent across markets:

```json
{
  "market": "cn_stock", "symbol": "600519", "interval": "1d", "adjust": "qfq",
  "columns": ["date", "open", "high", "low", "close", "volume", "amount"],
  "rows": [["2025-01-02", 1444.42, 1444.91, 1400.42, 1408.42, 50029, 7490884000.0]],
  "count": 1, "truncated": false,
  "cache": {"hit": true, "tier": "closed", "ttl": 604800},
  "source": "akshare:stock_zh_a_hist", "notes": []
}
```

`notes` surfaces anything the caller should know about the specific response: an ignored `adjust`, a
resolved/guessed symbol, dropped columns from a resample, or an unmapped source column that fell through to
its raw akshare name.

`list_instruments` returns the same columnar shape (`columns`/`rows`/`total`/`returned`/`truncated`/
`cached`/`source`/`notes`), just for instrument rows instead of quote/bar rows:

```json
{
  "market": "cn_stock", "source": "akshare:stock_info_a_code_name",
  "columns": ["symbol", "name"],
  "rows": [["600519", "贵州茅台"]],
  "total": 1, "returned": 1, "truncated": false, "cached": true, "notes": []
}
```

`describe_market` is not columnar (there's no row data to page through) -- it returns the capability
matrix for one market or all 16, each field described by name/type/unit/description:

```json
{
  "market": "cn_stock",
  "symbol_format": {"pattern": "6-digit code, optionally sh/sz/bj-prefixed", "examples": ["600519", "000001"], "notes": "..."},
  "realtime_fields": [{"name": "last", "type": "number", "unit": "quote_currency", "description": "Most recent traded price."}, "..."],
  "history_fields": ["..."], "history_fields_intraday": ["..."],
  "caveats": ["the single-symbol fast path returns a different, wider field set -- see XQ_SINGLE_QUOTE_FIELDS"]
}
```

## Development

Uses a project-local virtualenv -- never the system/conda Python -- managed by [uv](https://docs.astral.sh/uv/):

```bash
cd akshare
uv venv --python 3.12 .venv
uv sync --group dev
uv run pytest -q                 # offline unit tests (registry/normalize/intervals/cache/schemas/instruments), no network
uv run pytest -q -m live         # live smoke tests against real upstream endpoints, opt-in
```

`test_registry.py` asserts every akshare function this server depends on still has the parameter names it's
called with -- an akshare upgrade that renames something breaks that test immediately instead of silently
breaking a tool at request time.

Run the server directly (streamable-http on `:8000` by default):

```bash
CACHE_DIR=./data/cache uv run python -m akshare_mcp
curl -s localhost:8000/healthz
```

## Docker

```bash
cp .env.example .env    # adjust if needed
docker compose up -d --build
docker compose logs -f akshare-mcp
```

The disk cache is persisted on the named volume `akshare-cache` (mounted at `/data/cache`), so it survives
`docker compose down && docker compose up -d`. To inspect it from the host instead, swap the volume line in
`docker-compose.yml` for a bind mount (e.g. `./data/cache:/data/cache`).

Point an MCP client at it:

```bash
claude mcp add --transport http akshare http://localhost:8000/mcp
```

## Configuration

All configuration is via environment variables -- see `.env.example` for the full list with defaults
(cache TTLs, rate-limit tuning, transport/host/port, timezone, outbound proxy). Nothing needs a config file.

## Known limitations

- **East Money rate limiting.** `push2*.eastmoney.com` (backing `cn_stock`, `hk_stock`, `us_stock`,
  `cn_index`, `etf`, `lof`, `global_index`, `global_futures`, `forex`, `reits`) soft-bans bursty clients:
  after a dozen or so rapid requests it starts resetting connections for roughly a minute, even though the
  same URL via `curl` succeeds throughout. `fetch.py` throttles and retries with backoff, and the realtime/
  history caches absorb most of this in normal use, but a cold cache under heavy burst load can still see
  transient failures -- the tool surfaces a clear "likely rate-limited upstream, retry later" error rather
  than hanging or returning bad data.
- `crypto` is realtime-only; akshare has no matching history function for it.
- `forex`, `global_index`, `global_futures`, `reits`, `cn_bond`, `convertible_bond`, `sge_spot`, `open_fund`
  only have daily bars natively; weekly/monthly are resampled, and there is no minute-level data for these.
- `us_stock` minute bars only cover roughly the last 5 trading days (the same East Money endpoint used for
  intraday tick charts, not an archival kline store) and don't support `adjust`.
- `open_fund` is NAV-based (no open/high/low/volume) -- only `close` (the NAV) and `change_pct` are
  populated in OHLCV terms.
- `cn_bond`/`convertible_bond` symbol resolution tries both the `sh`/`sz` exchange prefixes when a bare
  numeric code is given (there's no reliable rule to derive the exchange from the code alone) and uses
  whichever succeeds; pass an already-prefixed code (e.g. `sh010107`) to skip the guess.
- akshare's column names/signatures can change between releases; `tests/test_registry.py` is a drift
  detector, and `pyproject.toml` pins `akshare>=1.18.80,<1.19`. `tests/test_schemas.py` additionally
  cross-checks `schemas.py`'s declared fields against those same raw column literals, so an upstream
  akshare release that silently renames a column (rather than removing/renaming a function/parameter, which
  `test_registry.py` already catches) fails a test instead of quietly drifting.
- `list_instruments`'s dedicated instrument tables for `cn_stock` (`stock_info_a_code_name`) and `cn_index`
  (`index_stock_info`) hit a separate, less-tested upstream than either market's realtime path; a failure
  falls back to projecting symbol/name out of the realtime table instead of erroring, noted in the response.
- `list_instruments(market='cn_futures', include_spec=True)` joins per-contract trading specs from each
  exchange's own contract-info endpoint, but coverage is exchange-dependent (SHFE/INE lack
  contract_unit/tick_size; CFFEX lacks contract_unit/tick_size/last_delivery_day but has price-limit and
  position-limit fields the others don't; DCE/GFEX/CZCE are the most complete) -- see
  `describe_market(market='cn_futures')`'s `caveats` for the exact breakdown. Contracts whose prefix isn't
  in `symbols._FUTURES_PREFIX_TO_VARIETY` (e.g. INE's `SC`/`LU`/`NR`/`EC`) get a null spec plus a note
  instead of an error.
