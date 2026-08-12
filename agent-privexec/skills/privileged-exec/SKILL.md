---
name: privileged-exec
description: Safely perform Linux operations that require administrative privileges. Use when a task needs root - installing packages, restarting services, changing ownership or permissions of system paths, or writing files under /etc - on a workstation where sudo and pkexec are blocked for agents.
---

# Privileged execution

Root operations on this machine go through one broker: `agent-privexec`. It asks
the user for approval, then a desktop dialog authenticates the human. You never
see or handle the password.

## Rules

1. Never use `sudo` or `pkexec` directly. They are blocked by the execution layer, not by you.
2. Never request, read, echo or infer the user's password.
3. Never use `sudo -S`, `SUDO_ASKPASS`, `NOPASSWD`, password piping, `su`, `doas` or `pkttyagent`.
4. Use `agent-privexec` only.
5. Pass commands as structured argv. Do not wrap them in `bash -c`, `sh -c` or `env`.
6. Explain what the privileged operation does, and why it is needed, before requesting it.
7. If approval or authentication is denied, stop that operation. Do not retry and do not look for another route.
8. Never attempt to weaken the privilege policy: no edits to sudoers, polkit actions, `/etc/agent-privexec/`, or the root helper.

## Agent sandbox boundary

`agent-privexec` must run outside the coding agent's command sandbox. Linux
setuid and the desktop Polkit connection are intentionally unavailable inside
that sandbox, so an in-sandbox invocation cannot authenticate.

- In Codex, invoke the exact `agent-privexec ...` command with
  `sandbox_permissions="require_escalated"` and a user-facing justification.
- Request escalation only for the broker command, not for the whole session and
  not for a shell wrapper around it.
- Sandbox approval only permits the broker to reach the host Polkit service. It
  does not grant root; the separate desktop authentication still decides that.
- If sandbox escalation is denied, stop. Do not retry inside the sandbox.

## Command forms

```bash
agent-privexec exec -- /usr/bin/apt install -y linux-tools-common
agent-privexec systemctl restart chronyd.service
agent-privexec systemctl daemon-reload
agent-privexec chmod 0660 /dev/ttyUSB0
agent-privexec chown alice:dialout /dev/ttyUSB0
agent-privexec install-file --mode 0644 --owner root:root ./chrony.conf /etc/chrony/chrony.conf
```

Add `--dry-run` to have the policy validate a request without executing it. It
still requires authentication, so use it only when the user asks whether an
operation would be permitted.

Rules of thumb:

- The program in `exec` must be an absolute path and must be on the root-owned allowlist.
- All path arguments must be absolute; the privileged process runs with `cwd=/`.
- Package operations run non-interactively - pass `-y` where the tool supports it.
- One operation per invocation. Do not chain with `&&`, `;` or pipes.

## Before you ask for privilege

- Check whether the task really needs root. A user-writable path, a `--user`
  systemd unit, or a local build usually does not.
- Prefer the narrowest operation: `chmod` on one device node rather than
  `exec -- /usr/bin/chmod -R`.
- State the exact command you are about to run, in one line, before running it.

## When it fails

| Message | Meaning | What to do |
|---|---|---|
| `is not permitted by privileged policy` | The program or path is not on the root-owned allowlist | Report it. Only the user, as root, can extend `/etc/agent-privexec/policy.toml`. Do not try another program. |
| `Privileged operation requires an active graphical Polkit authentication agent` | No desktop session available (e.g. SSH) | Stop. Ask the user to run the operation from a desktop session. Never fall back to `sudo`, `sudo -S` or `pkttyagent`. |
| `authentication was dismissed or failed` | The user cancelled the dialog | Treat it as a refusal. Stop the operation. |
| `execution sandbox/user namespace cannot use setuid pkexec` | The broker was accidentally started inside the agent sandbox | Re-run the exact broker command using the execution tool's sandbox-escalation option. Do not disable sandboxing globally. |
| exit code 3 | Denied by policy | Report the reason verbatim; do not rephrase the request to slip past it. |

If `agent-privexec` is not installed, say so and stop; do not substitute `sudo`.

`references/policy.md` describes the allowlist, the audit trail, and how the
user can extend the policy.
