# akshare-mcp

An MCP server that wraps [akshare](https://akshare.akfamily.xyz/index.html) (1137+ public functions, wildly
inconsistent naming/columns across markets) into exactly **two** tools:

- **`get_realtime_quotes`** -- realtime quotes across 16 asset classes
- **`get_history_bars`** -- multi-frequency OHLCV history (1m/5m/15m/30m/60m/1d/1w/1mo), with disk-backed
  caching (7 days by default for date ranges that can no longer change)

Everything else -- which akshare function backs which market, symbol format translation, Chinese/English
column normalization, rate limiting, retries, and caching -- happens once inside the server so the tool
surface stays small and uniform regardless of which of the 16 markets is being queried.

## Why only two tools

akshare has zero naming consistency: `stock_zh_a_hist(symbol, period, start_date, end_date, adjust)` vs.
`futures_zh_daily_sina(symbol)` vs. `forex_hist_em(symbol)`, with columns in a mix of Chinese and English
that differ per function. Handing an agent 1000+ raw functions means it has to relearn a different call
shape per asset class. This server does that routing once (`registry.py`), normalizes every market's output
to the same English column vocabulary (`normalize.py`), and exposes just the two operations an agent
actually needs.

## Markets

Call the `akshare://markets` resource for the live capability matrix (native intervals, adjust support,
whether the single-symbol fast path is available). Summary:

| `market` | Asset class | Example `symbol` | Native intervals | `adjust` |
|---|---|---|---|---|
| `cn_stock` | A-shares (沪深京) | `600519` | 1m..60m, 1d, 1w, 1mo | yes |
| `hk_stock` | Hong Kong equities | `00700` | 1m..60m, 1d, 1w, 1mo | yes |
| `us_stock` | US equities | `AAPL` | 1m (~5 recent days only), 1d, 1w, 1mo | yes (daily only) |
| `cn_index` | A-share indices | `000300` | 1m..60m, 1d, 1w, 1mo | no |
| `global_index` | Global indices (Chinese name) | `美元指数` | 1d (+resampled 1w/1mo) | no |
| `etf` | Exchange-traded funds | `510300` | 1m..60m, 1d, 1w, 1mo | yes |
| `lof` | Listed open-ended funds | `166009` | 1m..60m, 1d, 1w, 1mo | yes |
| `cn_futures` | CN commodity/financial futures | `RB0` / `RB2610` | 1m..60m, 1d (+resampled 1w/1mo) | no |
| `global_futures` | International futures | `HG00Y` | 1d (+resampled) | no |
| `forex` | FX pairs | `USDCNH` | 1d (+resampled) | no |
| `crypto` | Major cryptocurrencies | `BTC` | realtime only, **no history** | no |
| `convertible_bond` | CN convertible bonds | `113050` | 1d (+resampled) | no |
| `cn_bond` | CN plain bonds | `010107` | 1d (+resampled) | no |
| `reits` | CN REITs | `508097` | 1d (+resampled) | no |
| `sge_spot` | Shanghai Gold Exchange spot | `Au99.99` | 1d (+resampled) | no |
| `open_fund` | Off-exchange open-end funds (NAV) | `710001` | 1d (+resampled) | no |

Coarser intervals a market doesn't natively provide (e.g. weekly bars for a daily-only market) are
synthesized by resampling the finest available data; requesting a *finer* interval than a market supports
fails with a clear error listing what is actually available.

`cn_futures` realtime and history use different symbol vocabularies (a quirk of the underlying sina/East
Money endpoints, not this server): history wants a contract code (`RB0` for the main continuous contract,
`RB2610` for a specific one), realtime accepts either a contract code (the variety is inferred from a
built-in table of standard exchange prefixes) or a Chinese variety name (`螺纹钢`) and returns the whole
contract chain for that variety.

## Response shape

Both tools return compact, columnar JSON rather than a list of per-row objects, to keep token cost down and
field names consistent across markets:

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

## Development

Uses a project-local virtualenv -- never the system/conda Python -- managed by [uv](https://docs.astral.sh/uv/):

```bash
cd akshare
uv venv --python 3.12 .venv
uv sync --group dev
uv run pytest -q                 # offline unit tests (registry/normalize/intervals/cache), no network
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
  detector, and `pyproject.toml` pins `akshare>=1.18.80,<1.19`.
