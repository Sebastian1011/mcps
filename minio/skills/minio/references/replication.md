# Replication: bucket-level (`mc replicate`) and site-level (`mc admin replicate`)

Two distinct features. `mc replicate` configures replication **rules on one
bucket** to one or more remote targets. `mc admin replicate` configures
**site (cluster-to-cluster) replication**, which mirrors buckets, IAM users,
groups, policies, and (optionally) ILM expiry rules across entire deployments.

## `mc replicate` — bucket replication rules

```bash
mc replicate list ALIAS/BUCKET
mc replicate list --status enabled ALIAS/BUCKET

# Target as an existing alias:
mc replicate add ALIAS/BUCKET --remote-bucket TARGETALIAS/targetbucket --priority 1

# Target as an explicit URL with embedded credentials:
mc replicate add ALIAS/BUCKET \
  --remote-bucket https://ACCESSKEY:SECRETKEY@minio.siteb.example.com/targetbucket \
  --priority 1

mc replicate update ALIAS/BUCKET --id RULE-ID --priority 3
mc replicate update ALIAS/BUCKET --id RULE-ID --state disable
mc replicate remove --id RULE-ID ALIAS/BUCKET
mc replicate remove --all --force ALIAS/BUCKET     # deletes every rule on the bucket — confirm first

mc replicate export ALIAS/BUCKET > replication.json
mc replicate import ALIAS/BUCKET < replication.json   # replaces the ENTIRE config — confirm first
```

Key `replicate add`/`update` flags: `--id`, `--priority` (unique, required),
`--remote-bucket`, `--tags`, `--storage-class` (`STANDARD`|`REDUCED_REDUNDANCY`),
`--replicate` (comma list: `delete-marker,delete,existing-objects,metadata-sync`;
default is all four — pass `""` to clear), `--sync` (synchronous vs default
async), `--bandwidth` (e.g. `2G`), `--disable`/`--state enable|disable`,
`--edge`/`--edge-sync-before-expiry` (edge replication).

**Guardrail**: `--remote-bucket https://ACCESSKEY:SECRETKEY@host/bucket`
embeds a plaintext secret in the command — prefer referencing a pre-configured
alias (`TARGETALIAS/bucket`) instead, and never echo a URL-embedded credential
back in chat or logs.

```bash
mc replicate status ALIAS/BUCKET
mc replicate status --nodes --targets ALIAS/BUCKET
mc replicate backlog ALIAS/BUCKET                     # recent failures
mc replicate backlog --full ALIAS/BUCKET/prefix        # full listing, slower
mc replicate resync start ALIAS/BUCKET                 # re-replicate everything already replicated
mc replicate resync status ALIAS/BUCKET
mc replicate resync-backlog ALIAS/BUCKET               # actively retry backlogged objects
mc replicate resync-backlog --dry-run ALIAS/BUCKET     # preview first
mc replicate resync-backlog --concurrent 5 --rate-limit 20 ALIAS/BUCKET
```

`resync start` and `resync-backlog` (without `--dry-run`) trigger real
transfer/HeadObject work across the whole bucket — confirm scope with the
user on large buckets before running without `--dry-run`.

## `mc admin replicate` — site replication (multi-cluster)

```bash
mc admin replicate add SITE1ALIAS SITE2ALIAS [SITE3ALIAS...]
mc admin replicate add SITE1ALIAS SITE2ALIAS --replicate-ilm-expiry-rules

mc admin replicate info SITE1ALIAS
mc admin replicate status SITE1ALIAS
mc admin replicate status SITE1ALIAS --buckets
mc admin replicate status SITE1ALIAS --bucket mybucket
mc admin replicate status SITE1ALIAS --user someuser

mc admin replicate update SITE1ALIAS --deployment-id DEPLOY-ID --endpoint https://new-endpoint:9000
mc admin replicate update SITE1ALIAS --deployment-id DEPLOY-ID --bucket-bandwidth 2G
mc admin replicate update SITE1ALIAS --enable-ilm-expiry-rules-replication

mc admin replicate remove SITE1ALIAS SITE-NAME-A SITE-NAME-B --force
mc admin replicate remove SITE1ALIAS --all --force     # tears down site replication entirely — confirm first

mc admin replicate resync start SITE1ALIAS
mc admin replicate resync status SITE1ALIAS
mc admin replicate resync cancel SITE1ALIAS
```

Adding sites (`admin replicate add`) is a one-time, effectively irreversible
topology change (undoing it means `remove`, which itself requires `--force`)
— confirm with the user which aliases/deployments are being linked before
running it. Site replication also syncs IAM (users/groups/policies) between
the linked clusters, not just bucket data.
