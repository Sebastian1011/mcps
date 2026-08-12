#!/usr/bin/env python3
"""Claude Code PreToolUse hook: block privilege-escalation bypasses.

Permission rules such as `Bash(sudo *)` only match the literal start of a
command. This hook inspects the whole Bash command, including quoted payloads
of `bash -c` style wrappers, and denies anything that tries to reach root by a
route other than `agent-privexec`.

Its job is to block bypasses - never to auto-approve the broker. Requests to
`agent-privexec` stay subject to the normal `ask` permission rule.

Install as ~/.claude/hooks/agent-privexec-guard.py (mode 0755) and register it
for the Bash tool under hooks.PreToolUse.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import sys

# Commands that hand out root outside of the broker.
FORBIDDEN = {
    "sudo",
    "sudoedit",
    "pkexec",
    "su",
    "doas",
    "run0",
    "pkttyagent",
    "visudo",
}

# Prefixes that merely wrap another command.
WRAPPERS = {
    "command",
    "builtin",
    "exec",
    "nohup",
    "setsid",
    "time",
    "timeout",
    "stdbuf",
    "nice",
    "ionice",
    "xargs",
    "env",
}

# Interpreters and wrappers whose arguments can carry a whole command line.
RECURSE_INTO = {
    "bash",
    "sh",
    "dash",
    "zsh",
    "ksh",
    "fish",
    "csh",
    "python",
    "python3",
    "perl",
    "ruby",
    "node",
    "env",
    "xargs",
    "find",
    "ssh",
    "docker",
    "podman",
    "watch",
    "script",
    "flock",
    "systemd-run",
    "make",
}

# Read-only text tools: mentioning "sudo" in their arguments is not an attempt
# to escalate, so their arguments are not inspected.
TEXT_TOOLS = {"grep", "rg", "ag", "echo", "printf", "cat", "less", "head", "tail", "man"}

# Patterns that indicate an attempt to weaken the privilege boundary itself,
# wherever they appear in the command.
DANGEROUS_PATTERNS = [
    (r"NOPASSWD", "sudoers NOPASSWD configuration"),
    (r"SUDO_ASKPASS", "sudo askpass bypass"),
    (r"/etc/sudoers", "sudoers modification"),
    (r"/etc/polkit-1", "polkit policy modification"),
    (r"/usr/share/polkit-1", "polkit action modification"),
    (r"/etc/agent-privexec", "privileged policy modification"),
    (r"/usr/local/libexec/agent-privexec-root", "privileged helper modification"),
]

SEGMENT_SPLIT = re.compile(r"(?:\|\||&&|[;\n|&()`]|\$\()")
WORD_RE = re.compile(
    r"(?<![A-Za-z0-9_-])(" + "|".join(sorted(FORBIDDEN)) + r")(?![A-Za-z0-9_-])"
)

REASON = (
    "Direct privilege escalation is blocked on this machine ({what}).\n"
    "Use the privileged broker instead, for example:\n"
    "  agent-privexec exec -- /usr/bin/apt install <pkg>\n"
    "  agent-privexec systemctl restart <unit>\n"
    "It will ask for approval and then authenticate through the desktop dialog.\n"
    "Never use sudo, sudo -S, pkexec, su or NOPASSWD."
)


def tokenize(segment: str) -> list[str]:
    try:
        return shlex.split(segment, comments=True)
    except ValueError:
        return segment.split()


def scan(command: str, depth: int = 0) -> str | None:
    """Return a description of the escalation attempt, or None if clean."""
    if depth > 3:
        return None

    for segment in SEGMENT_SPLIT.split(command):
        tokens = tokenize(segment)
        i = 0
        while i < len(tokens):
            token = tokens[i]
            if "=" in token and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", token):
                i += 1  # leading environment assignment
                continue
            name = os.path.basename(token)
            if name in WRAPPERS:
                i += 1
                continue
            break

        if i >= len(tokens):
            continue

        token = tokens[i]
        name = os.path.basename(token)
        if name in FORBIDDEN:
            return f"`{name}`"

        # A quoted payload sitting in command position, e.g. the result of
        # unquoting `bash -lc '...'` one level up.
        if " " in token and WORD_RE.search(token):
            nested = scan(token, depth + 1)
            if nested:
                return nested

        if name in TEXT_TOOLS:
            continue

        recurse = name in RECURSE_INTO
        for arg in tokens[i + 1 :]:
            arg_name = os.path.basename(arg)
            if arg_name in FORBIDDEN:
                return f"`{arg_name}`"
            if recurse and WORD_RE.search(arg):
                nested = scan(arg, depth + 1)
                if nested:
                    return nested
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0  # never block on malformed hook input

    if payload.get("tool_name") != "Bash":
        return 0
    command = payload.get("tool_input", {}).get("command", "")
    if not isinstance(command, str) or not command.strip():
        return 0

    what = scan(command)
    if what is None:
        for pattern, description in DANGEROUS_PATTERNS:
            if re.search(pattern, command):
                what = description
                break

    if what is None:
        return 0

    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": REASON.format(what=what),
                }
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
