---
name: minio
description: Operate MinIO and S3-compatible object storage with the mc client - buckets, object upload/download/sync, versioning, lifecycle and tiering, replication, encryption, object lock/retention, quotas, CORS, anonymous access, event notifications, batch jobs, IAM users/groups/policies/access keys, STS, external IDP, cluster admin (info, config, healing, trace, decommission, rebalance, site replication), KMS, licensing, presigned URLs, and SDK access (Python minio/boto3, Go, JavaScript). Use whenever a task touches minio, mc, buckets, object storage, or S3-compatible endpoints.
metadata:
  short-description: Operate MinIO / S3-compatible storage via mc
---

# MinIO

Root tool is the `mc` CLI. Every reference file below was written against a
real, installed `mc` build by running `mc <command> --help` — if you need a
flag not shown here, run `mc <command> --help` yourself rather than guessing;
`mc`'s command surface differs across community and enterprise (AIStor)
builds and across versions.

## Preflight

```bash
mc --version                                              # confirm mc is installed
mc alias list --json | jq -r '"\(.alias)\t\(.URL)"'        # discover aliases without printing secrets
mc ping ALIAS && mc ready ALIAS                            # confirm the target is reachable before real work
```

## Routing table

| Task | Read |
|---|---|
| Alias setup, global flags, env vars, `--json` contract | `references/alias-config.md` |
| Upload/download/sync/search/inspect objects, presigned URLs | `references/objects.md` |
| Bucket config: versioning, lifecycle/tiering, encryption, retention/legal hold, quota, CORS, anonymous access, tags | `references/buckets.md` |
| Bucket replication and site (cluster-to-cluster) replication | `references/replication.md` |
| Users, groups, policies, access keys, STS, external IDP (OpenID/LDAP) | `references/iam.md` |
| Cluster info/config, healing, trace, topology (decommission/rebalance), diagnostics, KMS, licensing | `references/admin-ops.md` |
| Bucket event notifications and live event watching | `references/events-notify.md` |
| Batch jobs (replicate/keyrotate/expire) | `references/batch-jobs.md` |
| Programmatic access: Python (minio/boto3), Go, JavaScript | `references/sdk.md` |

## Guardrails

1. **Read before you write.** Before any write/delete, confirm the target
   with `mc ls`/`mc stat`/`mc du` — don't act on an assumed bucket/prefix.
2. **Dry-run first.** `mc rm`, `mc mirror`, and `mc replicate resync-backlog`
   support `--dry-run` — use it before the real run whenever the operation
   is recursive or `--force`d, and show the user the dry-run result first.
3. **Confirm destructive commands explicitly.** Before running any of these,
   state the exact command and get the user's confirmation: `mc rm` with
   `--recursive`/`--force`/`--dangerous`/`--versions`/`--purge-deleted`;
   `mc rb`; `mc mirror --remove`; `mc undo`; `mc batch start` for an `expire`
   job; `mc admin service restart`/`mc admin update`; `mc admin decommission
   start`/`mc admin rebalance start`; `mc admin user remove`/`group remove`/
   `policy remove`/`accesskey remove`; `mc replicate remove --all`/`mc ilm
   rule remove --all`; `mc admin config reset|import`; `mc admin cluster
   bucket import`/`mc admin cluster iam import`; `mc admin replicate remove`.
4. **No unscoped deletes.** A delete/remove path must name at least a bucket.
   Never construct or run `mc rm -r --force --dangerous ALIAS` (removes every
   object on the whole alias) unless the user types that exact command
   themselves and confirms it.
5. **Credentials never touch disk/logs/history.** Don't `cat ~/.mc/config.json`.
   Don't run bare `mc alias list` (it prints `secretKey`) — always project
   through `jq` per the preflight command above. Don't put a real secret key
   as a literal argv token (use stdin/prompt instead, per `alias-config.md`
   and `iam.md`). Hand newly created secrets to the user directly; don't
   persist them into a file, commit, or log you control.
6. **Config changes are recoverable.** Before `mc admin config set/reset`,
   run `mc admin config get ALIAS <subsystem>` first and keep the output.
   Mention when a change needs `mc admin service restart` to take effect.
7. **Least privilege for new policies.** Write explicit `Resource` ARNs and
   the minimum `Action` list the task needs; don't default to `s3:*` /
   `arn:aws:s3:::*` unless the user asks for full access.
8. **On error, stop and report.** Pass the server's `error.message` back to
   the user verbatim; don't retry with a different flag hoping it works.

## Conventions

- Prefer `--json` for anything you intend to parse; pipe through `jq`.
- Paths are `ALIAS/BUCKET[/prefix][/object]`; `--recursive` extends most
  object commands to a prefix.
- For bulk copy/sync, prefer `mc mirror` over looping `mc cp`.
- `--insecure` (skip TLS verification) only when the user explicitly asks
  for it, e.g. a self-signed dev endpoint.

## Out of scope

This `mc` build is MinIO AIStor Enterprise. Commands not covered by the
references above — `table` (Iceberg catalog), `qos`, `inventory`, `log
api|error|audit`, `admin maintenance`, `admin cordon`/`uncordon` — are
enterprise-specific; run `mc <command> --help` before using them rather than
guessing syntax. Also out of scope: server deployment/ops (`minio server`
startup, erasure-set layout, systemd units, Kubernetes operator) — this skill
covers the client and admin API surface, not standing up the server itself.
