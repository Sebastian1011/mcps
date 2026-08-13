# agent-privexec

A privileged execution boundary for AI coding agents on a Linux desktop
workstation. Codex and Claude Code can perform the root operations a dev
machine actually needs, without ever seeing a password, without `NOPASSWD`,
and without a long-lived root shell.

Implementation of [agent_privileged_execution_design.md](agent_privileged_execution_design.md).

```
agent -> agent-privexec -> pkexec --disable-internal-agent -> polkitd
      -> GNOME/KDE authentication dialog (the human authenticates)
      -> /usr/local/libexec/agent-privexec-root (root, policy validation)
      -> execve(target) + journald audit record
```

Two independent confirmations, never merged:

- **agent approval** - the user confirms *which command* runs (Codex execpolicy / Claude permissions);
- **OS authentication** - the desktop polkit dialog shows the requested broker command and confirms *who is asking* (`auth_admin`, no caching).

The skill is guidance; the boundary is the root-owned helper plus polkit.

## Layout

| Path | Installed to | Role |
|---|---|---|
| `system/bin/agent-privexec` | `/usr/local/bin/agent-privexec` | thin client: normalises the request, calls pkexec |
| `system/libexec/agent-privexec-root` | `/usr/local/libexec/agent-privexec-root` | root helper: validates against policy, execs, audits |
| `system/polkit/com.local.agent-privexec.policy` | `/usr/share/polkit-1/actions/` | polkit action (`allow_active = auth_admin`) |
| `system/etc/policy.toml` | `/etc/agent-privexec/policy.toml` | root-owned allowlist - the real policy |
| `agents/codex/privileged.rules` | `~/.codex/rules/privileged.rules` | Codex ExecPolicy enforcement |
| `agents/claude/hooks/agent-privexec-guard.py` | `~/.claude/hooks/` | Claude `PreToolUse` bypass guard |
| `skills/privileged-exec/` | symlinked into `~/.claude/skills/`, `~/.codex/skills/` | the shared skill |

## Install

Order matters: the OS boundary first, agent configuration second, skill last.

```bash
sudo ./install.sh          # phase 1: client, root helper, polkit action, policy
./install-agents.sh        # phases 2-4: codex rules, claude rules + hook, skill
```

`install-agents.sh` accepts `--codex`, `--claude`, `--skill` to install a single
layer. It backs up `~/.claude/settings.json` to
`~/.claude/settings.json.agent-privexec.bak` before merging. Restart running
Codex / Claude Code sessions afterwards.

Requirements: polkit + `pkexec`, a graphical session with a polkit
authentication agent (GNOME shell, KDE, `lxpolkit`, ...), Python 3.11+.
`install.sh` rejects a `pkexec` binary that is not root-owned and setuid.

Removal: `sudo ./uninstall.sh [--purge]` (agent-side files are listed by the
script; they are not removed automatically).

## Usage

```bash
agent-privexec exec -- /usr/bin/apt install -y linux-tools-common
agent-privexec systemctl restart chrony.service
agent-privexec systemctl daemon-reload
agent-privexec chmod 0660 /dev/ttyUSB0
agent-privexec chown alice:dialout /dev/ttyUSB0
agent-privexec install-file --mode 0644 --owner root:root ./chrony.conf /etc/chrony/chrony.conf
agent-privexec --dry-run exec -- /usr/bin/apt update    # validate only, still authenticates
```

When Codex runs the broker, that one command must be approved to execute outside
the agent sandbox. The sandbox intentionally prevents setuid from taking effect;
running the broker inside it produces a false-looking `pkexec` ownership error.
This sandbox approval is separate from the desktop Polkit authentication and
does not grant root by itself.

Exit codes: `0` success, `2` usage, `3` denied by policy, `4` no graphical
authentication agent, `5` authentication dismissed/failed, otherwise the target
program's exit code.

Audit trail:

```bash
journalctl -t agent-privexec -n 20 --output cat
```

Each record is one JSON object: `request_id`, `uid`, `user`, `agent`,
`claimed_cwd`, `operation`, `argv`, `resolved_argv`, `decision`, `reason`,
`exit_code`, `duration_ms`. Passwords and stdin payloads are never logged.

## Policy

`/etc/agent-privexec/policy.toml` is the only place that grants anything, and
only root can edit it. It defines the `exec` allowlist and denylist, permitted
`systemctl` verbs and unit-name pattern, chmod/chown constraints,
`install-file` destination prefixes, and protected paths.

Two deliberate properties:

- Shells and interpreters (`bash`, `sh`, `env`, `python3`, `perl`, `awk`,
  `find`, `xargs`, `tee`, `dd`, editors) are denied as privileged targets - one
  authentication must not become a general root shell.
- Protected paths (sudoers, PAM, polkit, `/etc/agent-privexec`, the broker
  binaries, `/etc/ssh`, `/root`, `/boot`) are refused by every path operation,
  so the boundary cannot be edited through the boundary.

The helper refuses to run if the policy file is not root-owned or is
group/world-writable, and ignores a caller-supplied `--policy` whenever it is
privileged.

## Tests

```bash
python3 tests/test_client.py # 5 client preflight tests, no GUI needed
python3 tests/test_polkit_policy.py # authentication prompt includes the command
./tests/test_policy.sh        # 38 policy decisions, unprivileged dry-run, no GUI needed
./tests/test_hook.sh          # 33 Claude hook cases (deny bypasses / allow normal work)
./tests/test_codex_rules.sh   # 17 execpolicy decisions via `codex execpolicy check`
```

### Acceptance status (design §19)

| Test | Status |
|---|---|
| `sudo id`, `/usr/bin/sudo id`, `pkexec id` refused by Codex | automated - verified, and confirmed against the Codex runtime |
| same refused by Claude Code | automated (hook); permission rules installed by `install-agents.sh` |
| `bash -lc 'sudo id'` | Claude: denied by hook. Codex: `prompt` - see *Known limits* |
| `agent-privexec exec -- /bin/bash` denied by the root helper | automated |
| protected paths, symbolic/setuid modes, bad units, oversized or control-character input | automated |
| `agent-privexec exec -- /usr/bin/id` → approval + GUI authentication | manual, after `sudo ./install.sh` |
| GUI authentication dialog includes the requested broker command | automated policy check; visual rendering is desktop-agent-specific |
| Cancel in the GUI dialog → operation fails, no retry | manual |
| No graphical polkit agent → fails, no TTY fallback | manual (e.g. over SSH: exits 4) |
| Editing the skill or a project hook does not affect OS policy | by construction - policy is root-owned |
| journald shows request / argv / result | manual, after install |

## Known limits

- **Codex and inner interpreters.** Codex wraps every command in `zsh -lc` and
  decomposes exactly that one layer, so `sudo id` is refused outright. An
  *explicit* inner interpreter is not decomposed: `bash -lc 'sudo id'` would
  otherwise slip past the prefix rules (verified against Codex 0.147). The
  rules therefore mark inner interpreters (`bash -c`, `sh -c`, `python3 -c`,
  `env`, `xargs`, ...) as `prompt`, so they reach the user instead of running
  silently. Drop those rules from `privileged.rules` if you prefer fewer
  prompts - direct `sudo`/`pkexec` stay forbidden either way.
- **The hook is a filter, not a proof.** The Claude guard denies command-position
  escalation and quoted payloads up to three levels deep; sufficiently creative
  string construction can still evade it. It never auto-approves anything.
- **Residual risk is bounded by the OS.** Even a bypass gains nothing: there is
  no `NOPASSWD` entry and no cached credential, so `sudo` simply fails. What the
  layers above buy is that the agent cannot make the user type a password into
  an unaudited prompt.
- **Desktop only.** Over SSH or in a headless session the client exits 4 by
  design. There is no TTY fallback and none should be added.
