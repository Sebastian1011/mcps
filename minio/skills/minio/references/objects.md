# Objects: list, copy, move, remove, sync, inspect, search, share

Paths are `ALIAS/BUCKET[/prefix][/object]` for remote targets, ordinary paths
for local filesystem. Most commands accept `--json` for machine-readable
output — prefer it over parsing human-readable tables.

## `mc ls` — list buckets and objects

```bash
mc ls ALIAS                                  # list buckets
mc ls ALIAS/BUCKET/                           # list top-level of a bucket
mc ls --recursive ALIAS/BUCKET/               # list everything under prefix
mc ls --versions ALIAS/BUCKET/object          # all versions
mc ls --rewind 7d ALIAS/BUCKET                # contents as of 7 days ago
mc ls --summarize ALIAS/BUCKET/               # object count + total size
mc ls --incomplete ALIAS/BUCKET               # unfinished multipart uploads
```

## `mc stat` — object/bucket metadata

```bash
mc stat ALIAS/BUCKET/object
mc stat --versions ALIAS/BUCKET/object
mc stat --verbose ALIAS                       # extended per-bucket stats
mc stat --recursive ALIAS/BUCKET/prefix/
```

## `mc du` / `mc tree` — usage summary / hierarchy view

```bash
mc du ALIAS/BUCKET
mc du --depth 2 ALIAS/BUCKET/prefix/
mc tree ALIAS
mc tree --files --depth 2 ALIAS/BUCKET/
```

## `mc find` — search objects (filters + `--exec`)

```bash
mc find ALIAS/BUCKET --name "*.jpg"
mc find ALIAS/BUCKET --regex '(?i)\.(jpg|png|gif)$'
mc find ALIAS/BUCKET --older-than 90d --ignore "*.tmp"
mc find ALIAS/BUCKET --larger 64MiB --smaller 1GiB --print '{url}'
mc find ALIAS/BUCKET --name "*.jpg" --watch --exec 'mc cp {} ALIAS2/BUCKET'
```

Format tokens for `--print`/`--exec`: `{}` full path, `{base}`, `{dir}`,
`{size}`, `{time}`, `{version}`, and (object storage only) `{url}`.
`--exec` spawns a real process per match — treat it like any other command
execution (confirm with the user if the exec'd command is destructive).

## `mc diff` — compare two trees (metadata only, not content)

```bash
mc diff ~/local/path ALIAS/BUCKET/prefix
```
`<` object only in source, `>` only in destination, `!` source is newer.

## `mc cp` / `mc mv` — copy / move objects

```bash
mc cp LOCALFILE ALIAS/BUCKET/                          # upload
mc cp ALIAS/BUCKET/object ./local/                     # download
mc cp --recursive ALIAS/BUCKET/prefix/ ALIAS2/BUCKET2/  # bucket-to-bucket
mc cp --older-than 7d10h ALIAS/BUCKET/ ALIAS2/BUCKET2/
mc cp --tags "category=prod&type=backup" -r ./data/ ALIAS/BUCKET/
mc cp --retention-mode governance --retention-duration 1d FILE ALIAS/BUCKET/  # locks the object on upload
mc cp --storage-class REDUCED_REDUNDANCY FILE ALIAS/BUCKET/

mc mv --recursive ALIAS/BUCKET/prefix/ ALIAS2/BUCKET2/  # same flags as cp, source is deleted after copy
```

Shared flags: `--recursive/-r`, `--older-than`/`--newer-than`, `--attr`
(custom metadata, `;`-separated `key=value`), `--tags`, `--preserve/-a`
(filesystem attrs), `--disable-multipart`, `--checksum`
(`CRC64NVME|CRC32|CRC32C|SHA1|SHA256`), `--enc-c`/`--enc-kms`/`--enc-s3`
(client/KMS/server-side encryption keys, format `alias/bucket/prefix=key`),
`--rewind`/`--version-id` (copy an older/specific version). `cp` additionally
supports `--legal-hold on|off` and `--zip` (extract from a remote zip,
MinIO-server source only).

## `mc rm` — delete objects (destructive — see guardrails in SKILL.md)

```bash
mc rm ALIAS/BUCKET/object
mc rm --dry-run --recursive --force ALIAS/BUCKET/prefix/    # ALWAYS do this first for recursive deletes
mc rm --recursive --force ALIAS/BUCKET/prefix/
mc rm --recursive --force --older-than 90d ALIAS/BUCKET/prefix/
mc rm --incomplete --recursive --force ALIAS/BUCKET          # drop stuck multipart uploads
mc rm ALIAS/BUCKET/object --version-id VERSIONID
mc rm --recursive --versions --rewind 365d ALIAS/BUCKET/prefix/
mc rm --recursive --force --versions --purge-deleted ALIAS/BUCKET/prefix/  # remove all versions where latest is a delete marker
mc rm --stdin --force                                          # object names/paths piped on stdin
mc rm --bypass ALIAS/BUCKET/object                              # bypass GOVERNANCE retention
```

**Site-wide**: `mc rm --recursive --force --dangerous ALIAS` removes every
object in every bucket on that alias. Never run this, or construct it for a
user, without the user typing the exact command themselves or explicitly
confirming the literal command text first.

## `mc get` / `mc put` — simple single-object download/upload

```bash
mc get ALIAS/BUCKET/object ./local/path
mc put ./local/path ALIAS/BUCKET/object
mc put --part-size 32MiB --parallel 8 ./bigfile ALIAS/BUCKET/bigfile   # tune multipart
mc put --storage-class REDUCED_REDUNDANCY ./file ALIAS/BUCKET/
```
`put` defaults: `--parallel 4`, `--part-size 16MiB`. Prefer `mc cp` for
anything recursive; `get`/`put` are single-object only.

## `mc cat` / `mc head` — read object content

```bash
mc cat ALIAS/BUCKET/object
mc cat --offset 1024 --tail 512 ALIAS/BUCKET/object
mc head -n 20 ALIAS/BUCKET/object.csv.gz        # auto-decompresses gzip/bzip2
```

## `mc pipe` — stream stdin to an object

```bash
tar cvf - ./data | mc pipe ALIAS/BUCKET/backup.tar
mysqldump db | mc pipe --tags "category=prod" ALIAS/BUCKET/dump.sql
```

## `mc od` — measure/exercise multipart upload throughput

```bash
mc od if=file.txt of=ALIAS/BUCKET/file.txt size=40MiB parts=5
```
Diagnostic tool, not a general upload path — use `mc cp`/`mc put` for real
transfers.

## `mc mirror` — one-way (or watched) sync between two trees

```bash
mc mirror --dry-run ALIAS/BUCKET/prefix/ ALIAS2/BUCKET2/    # preview before any --remove run
mc mirror ALIAS/BUCKET/prefix/ ALIAS2/BUCKET2/
mc mirror --overwrite ALIAS/BUCKET ALIAS2/BUCKET2            # overwrite differing objects on target
mc mirror --remove ALIAS/BUCKET ALIAS2/BUCKET2               # also delete extraneous objects on target
mc mirror --remove --watch ALIAS/BUCKET ALIAS2/BUCKET2       # keep syncing continuously (long-running)
mc mirror --exclude "*.tmp" --exclude-bucket 'test*' ALIAS ./local/
mc mirror -a ALIAS/BUCKET ALIAS2/BUCKET2                     # preserve metadata + bucket policy/lock config
```

This is the batch/recursive tool — prefer it over shell-looping `mc cp`.
`--remove` makes target authoritative-to-source and deletes anything extra;
treat `--remove` (especially with `--watch`) as destructive and confirm scope
with the user first. `--dry-run` works with `--remove` too.

## `mc undo` — revert recent PUT/DELETE (requires versioning)

```bash
mc undo ALIAS/BUCKET/object --last 3
mc undo --dry-run --recursive --force ALIAS/BUCKET/prefix/
mc undo --recursive --force ALIAS/BUCKET/prefix/
mc undo --action DELETE ALIAS/BUCKET/object     # only undo if latest change was a delete
```

## `mc sql` — run SQL (S3 Select) against structured objects

```bash
mc sql --query "select * from S3Object" ALIAS/BUCKET/data.csv
mc sql --recursive --query "select count(s.power) from S3Object s" ALIAS/BUCKET/telemetry/
mc sql --compression GZIP --csv-input "rd=\n,fh=USE,fd=;" --query "select * from S3Object" ALIAS/BUCKET/data.csv.gz
```
Object must be CSV/JSON (optionally gzip-compressed); this runs server-side,
it does not download the whole object.

## `mc share` — presigned URLs without exposing credentials

```bash
mc share download ALIAS/BUCKET/object                    # 7-day URL by default
mc share download --expire 10m ALIAS/BUCKET/object
mc share download --recursive --expire 120h ALIAS/BUCKET/prefix/
mc share upload --expire 2h --content-type image/png ALIAS/BUCKET/prefix/   # curl command for anonymous upload
mc share list download
mc share list upload
```
`--expire` accepts `NN[h|m|s]`. Treat generated URLs/curl commands as
sensitive — anyone with the link has the granted access until it expires.

## `mc watch` — stream live bucket events to the terminal

```bash
mc watch ALIAS/BUCKET
mc watch --events put,delete ALIAS/BUCKET/prefix
```
Long-running/foreground; for durable notifications use `mc event add` (see
`events-notify.md`) instead.
