#!/usr/bin/env bash
# Tests for the Claude Code PreToolUse guard hook.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOK="$ROOT/agents/claude/hooks/agent-privexec-guard.py"

pass=0 fail=0

# check deny|allow "command"
check() {
  local want="$1" cmd="$2" out got
  out="$(python3 -c 'import json,sys; print(json.dumps({"tool_name":"Bash","tool_input":{"command":sys.argv[1]}}))' "$cmd" \
        | python3 "$HOOK")"
  if [[ -z "$out" ]]; then
    got=allow
  elif grep -q '"permissionDecision": *"deny"' <<<"$out"; then
    got=deny
  else
    got="unexpected: $out"
  fi
  if [[ "$got" == "$want" ]]; then
    pass=$((pass + 1))
    printf '  ok   %-6s %s\n' "$got" "$cmd"
  else
    fail=$((fail + 1))
    printf '  FAIL want %-5s got %-5s %s\n' "$want" "$got" "$cmd"
  fi
}

echo "must be denied"
check deny "sudo id"
check deny "/usr/bin/sudo id"
check deny "pkexec id"
check deny "/usr/bin/pkexec bash"
check deny "bash -lc 'sudo id'"
check deny "sh -c \"sudo apt update\""
check deny "bash -c 'bash -c \"sudo id\"'"
check deny "make build && sudo make install"
check deny "true; sudo id"
check deny "echo hi | sudo tee /etc/motd"
check deny "SUDO_ASKPASS=/tmp/x sudo -A id"
check deny "env SUDO_ASKPASS=/tmp/a sudo -A true"
check deny "sudo -S id <<< secret"
check deny "su - root"
check deny "doas id"
check deny "xargs sudo id"
check deny "find . -name x -exec sudo id \\;"
check deny "echo 'user ALL=(ALL) NOPASSWD: ALL' > /etc/sudoers.d/x"
check deny "vim /etc/sudoers"
check deny "cp x /usr/share/polkit-1/actions/y.policy"
check deny "\$(which sudo) id"
check deny "pkttyagent --process 1"
check deny "python3 -c 'import os;os.system(\"sudo id\")'"
check deny "ssh localhost sudo id"

echo "must be allowed"
check allow "agent-privexec exec -- /usr/bin/apt install -y jq"
check allow "agent-privexec systemctl restart chrony.service"
check allow "ls -la /etc"
check allow "grep -r sudo /var/log/dpkg.log"
check allow "journalctl -t agent-privexec -n 5"
check allow "echo 'never use sudo here'"
check allow "python3 -c 'print(1)'"
check allow "git commit -m 'document the sudo policy'"
check allow "rg 'agent-privexec' skills/"

printf '\n%d passed, %d failed\n' "$pass" "$fail"
[[ $fail -eq 0 ]]
