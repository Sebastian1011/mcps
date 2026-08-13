# Buckets: versioning, lifecycle/tiering, encryption, retention, quota, CORS, anonymous access

All commands take `ALIAS/BUCKET` (or `ALIAS/BUCKET/prefix` where noted). Run
`mc <command> --help` to confirm flags before using an unfamiliar one — this
file only lists flags verified against the installed `mc` build.

## `mc mb` / `mc rb` — create / remove a bucket

```bash
mc mb ALIAS/BUCKET
mc mb --with-versioning ALIAS/BUCKET          # versioning enabled at creation
mc mb --with-lock --region us-west-2 ALIAS/BUCKET   # object lock needs a region-aware backend
mc mb --ignore-existing ALIAS/BUCKET          # no error if it already exists

mc rb ALIAS/BUCKET                            # only works if the bucket is empty
mc rb --force ALIAS/BUCKET                    # remove bucket AND all its contents/versions
mc rb --force --dangerous ALIAS               # remove EVERY bucket on the alias — guardrail: never run without explicit user confirmation of the exact command
```

`--with-lock` permanently enables Object Lock for the bucket (cannot be
undone later) and requires `--with-versioning` semantics under the hood.

## `mc version` — bucket versioning

```bash
mc version info ALIAS/BUCKET
mc version enable ALIAS/BUCKET
mc version enable ALIAS/BUCKET --excluded-prefixes "tmp/*/_staging/" --exclude-folders
mc version suspend ALIAS/BUCKET
```

`--purge-on-delete [on|spark|off]` on `version enable` makes every DELETE a
hard delete instead of leaving a delete marker — this is destructive and
site-wide for the bucket; confirm with the user before setting it.

## `mc ilm rule` — lifecycle (expiration / transition)

```bash
mc ilm rule list ALIAS/BUCKET
mc ilm rule list --json ALIAS/BUCKET

# Expire objects under a prefix after 200 days
mc ilm rule add --prefix "logs/" --expire-days 200 ALIAS/BUCKET

# Expire noncurrent versions after 100 days, keep the 3 newest noncurrent versions
mc ilm rule add --noncurrent-expire-days 100 --noncurrent-expire-newer 3 ALIAS/BUCKET

# Transition objects >1MiB to a configured remote tier after 90 days
mc ilm rule add --prefix "doc/" --size-gt 1MiB --transition-days 90 --transition-tier MINIOTIER-1 ALIAS/BUCKET

mc ilm rule edit --id RULEID --disable ALIAS/BUCKET     # disable without deleting
mc ilm rule remove --id RULEID ALIAS/BUCKET
mc ilm rule remove --all --force ALIAS/BUCKET           # deletes every rule on the bucket — confirm first

mc ilm rule export ALIAS/BUCKET > lifecycle.json
mc ilm rule import ALIAS/BUCKET < lifecycle.json        # replaces the ENTIRE lifecycle config — confirm first
```

Key flags for `ilm rule add`/`edit`: `--prefix`, `--tags`, `--size-lt`/`--size-gt`,
`--expire-days`, `--expire-delete-marker`, `--transition-days`/`--transition-tier`,
`--noncurrent-expire-days`/`--noncurrent-expire-newer`,
`--noncurrent-transition-days`/`--noncurrent-transition-tier`,
`--purge-all-object-versions-days`.

## `mc ilm tier` — remote tier targets (for lifecycle transition)

```bash
mc ilm tier list ALIAS
mc ilm tier info ALIAS [TIERNAME]
mc ilm tier check ALIAS TIERNAME

mc ilm tier add minio ALIAS WARM-TIER --endpoint https://warm.example.com \
  --access-key ACCESSKEY --secret-key SECRETKEY --bucket warmbucket --prefix warmprefix/

mc ilm tier add s3 ALIAS S3TIER --endpoint https://s3.amazonaws.com \
  --access-key ACCESSKEY --secret-key SECRETKEY --bucket mys3bucket \
  --storage-class INTELLIGENT_TIERING --region us-west-2

mc ilm tier add azure ALIAS AZTIER --account-name NAME --account-key KEY --bucket container
mc ilm tier add gcs ALIAS GCSTIER --credentials-file /path/creds.json --bucket bucket

mc ilm tier update ALIAS TIERNAME --access-key NEWKEY --secret-key NEWSECRET
mc ilm tier remove ALIAS TIERNAME     # only works if the tier holds no transitioned objects
```

`TYPE` is one of `minio`, `s3`, `azure`, `gcs`. Never print `--access-key`/
`--secret-key`/`--account-key` values back verbatim in a way that lands in
logs or shared output.

## `mc ilm restore` — restore transitioned/archived objects

```bash
mc ilm restore ALIAS/BUCKET/path/to/object                       # default: 1 day
mc ilm restore --days 7 ALIAS/BUCKET/path/to/object
mc ilm restore --recursive ALIAS/BUCKET/prefix/
mc ilm restore --recursive --versions ALIAS/BUCKET/prefix/
```

## `mc encrypt` — bucket-level auto server-side encryption

```bash
mc encrypt info ALIAS/BUCKET
mc encrypt set sse-s3 ALIAS/BUCKET                    # SSE-S3, MinIO-managed key
mc encrypt set sse-kms KEY-NAME-OR-ARN ALIAS/BUCKET   # SSE-KMS with a named/ARN KMS key
mc encrypt clear ALIAS/BUCKET
mc encrypt update --kms-key KEY-NAME ALIAS/BUCKET/OBJECT   # rotate an object's key envelope in place
```

`encrypt update` re-wraps the encryption key without re-reading/re-writing
object data. It targets one object (optionally `--version-id`), not a bucket.

## `mc retention` — Object Lock retention (WORM)

Requires the bucket to have Object Lock enabled (`mc mb --with-lock`, or a
default bucket lock configured with `--default`).

```bash
mc retention info --default ALIAS/BUCKET/                         # bucket default mode
mc retention set --default governance 30d ALIAS/BUCKET/

mc retention set compliance 30d ALIAS/BUCKET/prefix/obj.csv
mc retention set governance 30d ALIAS/BUCKET/prefix --recursive
mc retention info ALIAS/BUCKET/prefix/obj.csv
mc retention clear ALIAS/BUCKET/prefix/obj.csv                    # requires --bypass rights under governance
```

`VALIDITY` is `Nd` (days) or `Ny` (years). Mode is `governance` (can be
shortened/bypassed by a user with `s3:BypassGovernanceRetention`) or
`compliance` (cannot be shortened or removed by anyone, including root, until
it expires) — confirm with the user which mode before setting `compliance`,
it is not reversible.

## `mc legalhold` — legal hold (independent of retention)

```bash
mc legalhold info ALIAS/BUCKET/prefix/obj.csv
mc legalhold set ALIAS/BUCKET/prefix/obj.csv
mc legalhold set --recursive ALIAS/BUCKET/prefix
mc legalhold clear ALIAS/BUCKET/prefix/obj.csv
```

While legal hold is `on`, the object cannot be deleted or overwritten
regardless of retention/versioning settings.

## `mc quota` — bucket hard quota

```bash
mc quota info ALIAS/BUCKET
mc quota set ALIAS/BUCKET --size 1GB
mc quota clear ALIAS/BUCKET
```

Enforcement depends on the periodic object scanner noticing usage has
crossed the limit — it is not instantaneous.

## `mc cors` — bucket CORS configuration

```bash
mc cors get ALIAS/BUCKET
mc cors set ALIAS/BUCKET /path/to/cors.xml
mc cors set ALIAS/BUCKET -                     # read XML from stdin
mc cors remove ALIAS/BUCKET
```

CORSFILE is an S3-style CORS XML document (`<CORSConfiguration>`), not JSON.

## `mc anonymous` — anonymous (unauthenticated) bucket/object access

```bash
mc anonymous get ALIAS/BUCKET
mc anonymous get-json ALIAS/BUCKET
mc anonymous list ALIAS/BUCKET

mc anonymous set private ALIAS/BUCKET          # default: no public access
mc anonymous set download ALIAS/BUCKET         # public read
mc anonymous set upload ALIAS/BUCKET           # public write
mc anonymous set public ALIAS/BUCKET           # public read+write
mc anonymous set public ALIAS/BUCKET/prefix    # scoped to a prefix

mc anonymous set-json /path/to/anonymous.json ALIAS/BUCKET/prefix   # custom S3 policy JSON
mc anonymous --recursive list ALIAS/BUCKET/    # list public object URLs recursively
```

**Guardrail**: `download`/`upload`/`public` expose bucket contents to anyone
with the endpoint URL — always confirm the exact bucket/prefix and permission
level with the user before applying, and prefer scoping to a prefix over a
whole bucket.

## `mc tag` — bucket and object tags

```bash
mc tag list ALIAS/BUCKET/OBJECT
mc tag list --recursive ALIAS/BUCKET
mc tag set ALIAS/BUCKET/OBJECT "key1=value1&key2=value2"
mc tag set --recursive ALIAS/BUCKET "project=demo"
mc tag remove ALIAS/BUCKET/OBJECT
```

Tags use `key=value` pairs joined with `&`. `--version-id`/`--versions`/
`--rewind` work the same way as on `mc retention`/`mc legalhold`.
