# minio skill

A shared Claude Code / Codex skill for operating MinIO and S3-compatible
object storage via the `mc` CLI, plus SDK (Python/Go/JS) reference. One
skill source, symlinked into both agents' skill directories - no drift
between two copies.

## Layout

| Path | Installed to | Role |
|---|---|---|
| `skills/minio/SKILL.md` | symlinked as `minio` into `~/.claude/skills/` and `~/.codex/skills/` | routing table + guardrails, ~90 lines |
| `skills/minio/references/*.md` | (part of the symlinked directory) | one file per domain: objects, buckets, replication, IAM, admin ops, notifications, batch jobs, SDKs, alias/config |
| `install.sh` | - | symlinks `skills/minio` into both agents |
| `uninstall.sh` | - | removes those symlinks (only if they still point here) |

## Install

```bash
./install.sh              # both Claude Code and Codex
./install.sh --claude      # just Claude Code
./install.sh --codex       # just Codex
```

Requires the `mc` client to be installed (https://min.io/download) for the
skill to actually be useful; `install.sh` warns but does not block if it's
missing. Restart running Claude Code / Codex sessions afterward to pick up
the new skill.

```bash
./uninstall.sh             # remove the symlink(s)
```

`uninstall.sh` only removes a target that is a symlink pointing back into
this repo - it will never delete a real directory, even if it happens to be
named `minio`.

## Maintaining accuracy

Every command, flag, and example in `skills/minio/references/` was verified
by actually running `mc <command> --help` against an installed `mc` build -
nothing here was written from memory alone, because `mc`'s command surface
differs between community and enterprise (AIStor) builds and across
versions.

When `mc` is upgraded, re-validate before trusting the references still
match:

```bash
mc --version
mc --help | sed -n '/^COMMANDS:/,/^GLOBAL FLAGS:/p' | awk '{print $1}' | grep -E '^[a-z]' | sort -u
```

Diff that command list against the routing table in `SKILL.md` - any new
top-level command needs either a home in an existing reference file or a
callout in the "Out of scope" section. For any reference file you touch,
re-run `mc <command> --help` for every command/flag in it before editing,
the same way this skill was originally built.
