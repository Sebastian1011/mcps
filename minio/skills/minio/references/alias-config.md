# Aliases, global flags, environment variables, JSON output

`mc` talks to a server through a named **alias** (`ALIAS/BUCKET/...` in every
other command). Discover configured aliases before assuming any exist.

## Discovering aliases without printing secrets

```bash
mc --version                                            # confirm mc is installed
mc alias list --json | jq -r '"\(.alias)\t\(.URL)"'      # alias + endpoint, no keys
mc alias list --json | jq -r 'select(.alias=="TARGET")'  # inspect one alias's non-secret fields
```

`mc alias list` (with or without `--json`) prints `accessKey` **and**
`secretKey` in plaintext for every alias. Never run it bare and never pipe its
raw output anywhere it could be logged, echoed, or shared — always project
through `jq` to the fields actually needed.

## `mc alias set` — add or replace an alias

```bash
mc alias set ALIAS https://minio.example.com ACCESSKEY SECRETKEY
mc alias set ALIAS https://minio.example.com ACCESSKEY SECRETKEY --api S3v4 --path off   # DNS-style bucket lookup
mc alias set ALIAS https://s3.amazonaws.com --api S3v4 --path off    # omit keys, mc prompts interactively
```

`--path` is `auto` (default) / `on` (path-style) / `off` (virtual-host/DNS-style).
`--api` is `S3v4` (default) or `S3v2`.

**Guardrail**: never construct a command line containing a real secret key —
that string lands in shell history and process listings. If credentials must
be supplied non-interactively, prefer piping them to stdin
(`printf '%s\n%s\n' "$ACCESS" "$SECRET" | mc alias set ALIAS URL --api S3v4`)
so the secret never appears as a literal argv token, and tell the user to run
`set +o history` / `set -o history` around it if they're typing it directly.

## `mc alias list` / `remove` / `import` / `export`

```bash
mc alias list ALIAS                       # single alias (still includes secretKey — pipe through jq)
mc alias remove ALIAS
mc alias export ALIAS > alias.json        # {url, accessKey, secretKey, api, path} — treat as a secret file
mc alias import ALIAS < alias.json
mc alias export SRC | mc alias import DST # clone an alias under a new name
```

## `mc update` — update the `mc` binary itself

```bash
mc update
```
Exit code `0` = already latest, `1` = updated, `-1` = error checking. This
replaces the `mc` binary on disk; treat it like any other software update
(fine on a workstation, confirm before running on a shared/managed host).

## Ad-hoc aliases via environment variable (no config file write)

```bash
MC_HOST_ALIAS="https://ACCESSKEY:SECRETKEY@minio.example.com" mc ls ALIAS
```
`MC_HOST_<alias>` defines an alias for the lifetime of the process/shell
without touching `~/.mc/config.json` — useful for one-off scripts or CI. It
still contains a plaintext secret; scope it to the single command via a
leading env-var assignment rather than `export`-ing it into a long-lived shell.

## Global flags (available on every `mc` command)

| Flag | Purpose |
|---|---|
| `--json` | JSON-lines output; use for anything you intend to parse |
| `-C, --config-dir` | alternate `~/.mc` location (`$MC_CONFIG_DIR`) |
| `-q, --quiet` | suppress the progress bar |
| `--no-color`, `--disable-pager`/`--dp` | plain output, useful when capturing to a file |
| `--insecure` | skip TLS certificate verification — only when the user explicitly asks for it (self-signed/dev endpoints) |
| `--resolve HOST:PORT=IP` | override DNS resolution for one host |
| `--limit-upload`, `--limit-download` | rate-limit in KiB/MiB/GiB per second |
| `-H, --custom-header 'key:value'` | attach a custom HTTP header to the request |
| `--debug`, `--dtrace` | verbose/OpenTelemetry tracing for troubleshooting |

## Reachability check before doing real work

```bash
mc ping ALIAS                 # liveness
mc ping --count 3 ALIAS
mc ready ALIAS                 # cluster read/write quorum ready
```
See `admin-ops.md` for the full `ping`/`ready` flag set and cluster-level
health commands.
