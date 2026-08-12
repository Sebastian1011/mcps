# Privileged execution policy reference

## Why the boundary exists

The skill text is guidance, not security. The actual boundary is:

```
Skill instruction  <  agent permission enforcement  <  root-owned helper  <  polkit / OS authentication
```

Two independent confirmations are always required:

- **Agent approval** - the user confirms *which command* runs.
- **OS authentication** - the desktop polkit dialog confirms *who is asking*.

They are never merged, and authorisation is never cached (`auth_admin`, never
`auth_admin_keep`): every request re-authenticates.

## Chain of custody

```
agent -> agent-privexec -> pkexec --disable-internal-agent
      -> polkitd -> desktop authentication dialog
      -> /usr/local/libexec/agent-privexec-root -> policy validation -> execve
```

The root helper treats everything from the client as untrusted, including the
request ID, agent name and working directory (recorded as *claimed* values in
the audit log). The invoking uid comes from `PKEXEC_UID`, set by pkexec.

## Operations

| Operation | Form | Validation |
|---|---|---|
| `exec` | `exec -- PROGRAM [ARGS...]` | `PROGRAM` canonicalised, must be root-owned, non-world-writable, on the allowlist and not on the denylist |
| `systemctl` | `systemctl VERB [UNIT]` | verb allowlist; unit must match the unit-name pattern |
| `chmod` | `chmod MODE PATH` | octal mode only, no setuid/setgid, no recursion; path not protected |
| `chown` | `chown OWNER PATH` | user/group must exist; path not protected |
| `install-file` | `install-file MODE OWNER SRC DEST` | destination must sit under an allowed prefix and outside protected paths |

Shells and interpreters (`bash`, `sh`, `env`, `python3`, `perl`, `ruby`, `awk`,
`find`, `xargs`, `tee`, `dd`, editors) are denied as privileged targets: one
authentication must not become a general root shell.

Protected paths - sudoers, PAM, polkit, `/etc/agent-privexec`, the broker
binaries themselves, `/etc/ssh`, `/root`, `/boot` - are refused for every
path-taking operation, so the boundary cannot be edited through the boundary.

## Environment

The privileged process starts with a scrubbed environment: `PATH`, `HOME=/root`,
`USER`/`LOGNAME=root`, `SHELL=/usr/sbin/nologin`, `LANG=C.UTF-8`, plus `TERM`
when it matches a safe pattern. `cwd` is `/`, so relative paths never resolve
into the caller's directory. Requests containing NUL bytes, control characters,
invalid UTF-8, or exceeding the size limits are rejected before validation.

## Audit

Every request - allowed, denied or failed - is written to journald under the
`agent-privexec` identifier (facility `authpriv`) as one JSON record:

```bash
journalctl -t agent-privexec -n 20 --output cat
```

Fields: `request_id`, `timestamp`, `uid`, `user`, `agent`, `claimed_cwd`,
`operation`, `argv`, `resolved_argv`, `decision`, `reason`, `exit_code`,
`duration_ms`. Passwords, tokens and stdin payloads are never logged.

## Extending the policy (user action, as root)

Only the user can widen the boundary:

```bash
sudoedit /etc/agent-privexec/policy.toml   # add to [exec] allowed, or the systemctl verbs
```

The file must stay `root:root`, mode `0644`; the helper refuses to run if it is
group- or world-writable. Adding a shell or interpreter to `[exec] allowed` has
no effect while it remains on the denylist - and removing it from the denylist
turns a single authentication into a general root shell, which defeats the whole
design.

An agent must never propose editing this file on the user's behalf.
