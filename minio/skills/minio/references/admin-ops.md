# Cluster administration: info, config, healing, trace, topology changes, diagnostics, KMS, licensing

All commands take `ALIAS` (a server/cluster), not a bucket. Several here are
irreversible cluster-topology or config changes — read the guardrail note on
each before running it for a user.

## Health and reachability

```bash
mc ping ALIAS                            # basic liveness
mc ping --count 5 ALIAS
mc ready ALIAS                            # is the cluster ready to serve
mc ready ALIAS --cluster-read             # has read quorum
mc admin info ALIAS                       # server/node/drive summary
mc admin info --watch --interval 5s ALIAS # live-refreshing view
```

## `mc admin config` — server configuration subsystems

```bash
mc admin config get ALIAS --tree                 # list every subsystem
mc admin config get ALIAS region
mc admin config get ALIAS notify webhook
mc admin config get --string ALIAS compression   # one-liner, good for piping

mc admin config set ALIAS region name=us-west-1
mc admin config set ALIAS notify_webhook endpoint="http://localhost:8080/minio/events"
mc admin config set ALIAS heal max_delay=300ms max_io=50

mc admin config history ALIAS                    # last 10 changes
mc admin config history --count 50 ALIAS
mc admin config restore ALIAS RESTORE-ID          # roll back to a prior history entry

mc admin config reset ALIAS notify_mqtt:name1     # reset one subsystem instance to defaults
mc admin config reset ALIAS compression extensions

mc admin config export ALIAS > config.txt         # includes env-var-sourced values (informational only, not settable from client)
mc admin config import ALIAS < config.txt          # REPLACES matching keys — confirm before running
```

**Guardrail**: run `mc admin config get ALIAS <subsystem>` and save the
output before any `set`/`reset`/`import` on that subsystem, so the prior
value is recoverable. Many config changes require `mc admin service restart`
to take effect — tell the user which ones do before they ask why nothing
changed.

## `mc admin cluster` — cluster-wide info, bucket/IAM metadata backup

```bash
mc admin cluster info ALIAS
mc admin cluster info ALIAS --metrics
mc admin cluster bucket export ALIAS                    # zip of all bucket metadata
mc admin cluster bucket export ALIAS/BUCKET
mc admin cluster bucket import ALIAS /path/to/backup.zip   # REPLACES bucket metadata — confirm first
mc admin cluster iam export ALIAS --output /tmp/iam.zip
mc admin cluster iam import ALIAS /tmp/iam.zip              # REPLACES cluster IAM state — confirm first
```

## `mc admin heal` — data healing

```bash
mc admin heal ALIAS                              # monitor healing status
mc admin heal --dry-run --recursive ALIAS/BUCKET  # inspect only, no mutation
mc admin heal --recursive --force ALIAS/BUCKET
mc admin heal --scan deep --recursive ALIAS/BUCKET/prefix
```
`--scan` is `normal` (default), `deep`, or `uncommitted`. `--remove` drops
dangling objects during heal — destructive, confirm scope first.

## `mc admin scanner` / `mc admin trace` — live diagnostics (foreground/streaming)

```bash
mc admin scanner status ALIAS
mc admin scanner status ALIAS --bucket mybucket
mc admin scanner trace ALIAS
mc admin scanner trace --funcname scanner.ScanObject ALIAS

mc admin trace ALIAS                              # S3 API calls (default --call s3)
mc admin trace -v -a ALIAS                         # verbose, all call types
mc admin trace -v -e ALIAS                         # errors only
mc admin trace --status-code 503 ALIAS
mc admin trace --call healing,rebalance ALIAS      # see CALL TYPES below
```
`--call` types: `s3` (default), `internal`, `storage`, `os`, `healing`,
`rebalance`, `decommission`, `bootstrap`, `formatting`, `ftp`, `ilm`, `scanner`,
`replication-resync`, `batch-replication`, `batch-keyrotation`,
`batch-expiration`, `tables`, `tables-scan`. These stream continuously —
run in the background or with a count/timeout expectation set with the user.

## `mc admin logs` — server logs

```bash
mc admin logs ALIAS
mc admin logs --last 50 ALIAS
mc admin logs --type application ALIAS NODENAME
```

## `mc admin prometheus` — metrics config/scrape

```bash
mc admin prometheus generate ALIAS --api-version v3           # scrape config, default all metric groups
mc admin prometheus generate ALIAS api --api-version v3
mc admin prometheus metrics ALIAS cluster --api-version v3    # one-shot metrics dump
mc admin prometheus metrics ALIAS replication --bucket mybucket --api-version v3
```
v3 metric groups: `api`, `system`, `debug`, `cluster`, `ilm`, `audit`,
`logger`, `replication`, `notification`, `scanner`, `batch`, `kms`. v2 (legacy):
`cluster`, `node`, `bucket`, `resource`.

## Topology: decommission / rebalance / pool / node / drive / set

```bash
mc admin pool info ALIAS                                       # or: mc admin pool top ALIAS
mc admin node info ALIAS
mc admin drive top ALIAS
mc admin set info ALIAS

mc admin decommission start ALIAS http://server{5...8}/disk{1...4}   # begin removing a pool — long-running, irreversible once objects have moved
mc admin decommission status ALIAS
mc admin decommission cancel ALIAS

mc admin rebalance start ALIAS
mc admin rebalance status ALIAS
mc admin rebalance stop ALIAS
```
**Guardrail**: `decommission start` and `rebalance start` are cluster-topology
operations that run for a long time and reshuffle real data across drives —
always show the user the exact target/pool and get explicit confirmation
before starting either, and check `status` first if one might already be
running.

```bash
mc admin name get ALIAS                # cluster/site name (or "#NAME ..." if env-var-defined)
mc admin name set ALIAS my-site-name

mc admin object info ALIAS/BUCKET/OBJECT
mc admin object unlock ALIAS/BUCKET/OBJECT     # force-clear stale locks — confirm before running on a live object
```

## `mc admin service` / `mc admin update` — cluster lifecycle

```bash
mc admin service restart --dry-run ALIAS       # verify peer status without restarting
mc admin service restart ALIAS                  # restarts every node — brief API downtime, confirm first
mc admin service restart --rolling 30s ALIAS    # graceful rolling restart
mc admin service unfreeze ALIAS                 # resume S3 API calls after a freeze

mc admin update ALIAS --dry-run
mc admin update ALIAS -y                        # updates the MinIO binary on every node — confirm first
mc admin update ALIAS --status
```

## `mc kms` / `mc admin kms` — encryption key management

```bash
mc kms enable ALIAS                              # enable internal KMS
mc kms key create ALIAS my-key
mc kms key list ALIAS
mc kms key status ALIAS [KEY_NAME]
```
`mc admin kms key ...` is the equivalent form (`create`/`list`/`status`) —
both exist; prefer whichever the user's existing scripts already use.

## `mc license` — MinIO Subscription Network (SUBNET)

```bash
mc license info ALIAS
mc license register ALIAS --license /path/to/license-file    # first registration
mc license register ALIAS                                     # re-register if already installed
mc license update ALIAS license.key
mc license update ALIAS                                       # renew an already-registered license
```

## `mc support` — SUBNET-integrated diagnostics (uploads data off-cluster unless `--airgap`)

```bash
mc support diag ALIAS                            # full health diagnostics, uploads to SUBNET
mc support diag ALIAS --airgap                    # save locally instead of uploading
mc support diag ALIAS --check sys.drive,sys.mem   # run a subset of checks
mc support perf ALIAS --airgap                    # object/network/drive perf test
mc support profile --type cpu,mem --duration 30 ALIAS --airgap
mc support inspect ALIAS/BUCKET/object/xl.meta --airgap
mc support top api ALIAS                          # live top-like stats: api|drive|locks|net|rpc
mc support callhome status ALIAS
mc support callhome enable ALIAS
mc support proxy show ALIAS
mc support upload --issue 1234 ALIAS ./trace.log  # attach a file to a SUBNET support ticket
```
**Guardrail**: every `support` subcommand talks to MinIO's SUBNET service and
uploads cluster data by default. Use `--airgap` (saves locally instead) unless
the user explicitly wants it sent to SUBNET, and confirm before running
`support upload`, `support diag`, or `support perf` without `--airgap` on a
cluster that may hold sensitive data — `--anonymize strict` on `support diag`
reduces but does not eliminate what leaves the cluster.
