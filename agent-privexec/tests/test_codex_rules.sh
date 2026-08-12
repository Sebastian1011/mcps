#!/usr/bin/env bash
# Verify the Codex execpolicy rules resolve as intended, including the
# compound-shell forms an agent might use to slip past a prefix rule.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RULES="$ROOT/agents/codex/privileged.rules"

command -v codex >/dev/null || { echo "codex not installed - skipping"; exit 0; }

pass=0 fail=0

# check EXPECTED_DECISION -- <command tokens...>
check() {
  local want="$1"; shift 2
  local out got
  out="$(codex execpolicy check --rules "$RULES" -- "$@" 2>&1)"
  got="$(printf '%s' "$out" | python3 -c 'import json,sys
try:
    d = json.loads(sys.stdin.read())
except Exception:
    print("unparsable"); raise SystemExit(0)
print(d.get("decision", "none"))')"
  if [[ "$got" == "$want" ]]; then
    pass=$((pass + 1))
    printf '  ok   %-10s %s\n' "$got" "$*"
  else
    fail=$((fail + 1))
    printf '  FAIL want %-10s got %-10s %s\n       %s\n' "$want" "$got" "$*" "$out"
  fi
}

check forbidden -- sudo id
check forbidden -- /usr/bin/sudo id
check forbidden -- pkexec id
check forbidden -- /usr/bin/pkexec id
check forbidden -- pkttyagent --process 1
check forbidden -- visudo
# Codex decomposes only the shell it wraps commands in; an explicit inner
# interpreter must therefore be surfaced to the user rather than run silently.
check prompt -- bash -lc 'sudo id'
check prompt -- bash -c 'true && sudo id'
check prompt -- sh -c 'sudo id'
check prompt -- python3 -c 'import os; os.system("sudo id")'
check prompt -- env SUDO_ASKPASS=/tmp/x sudo -A id
check prompt -- xargs sudo id
check prompt -- agent-privexec exec -- /usr/bin/apt install -y jq
check prompt -- agent-privexec systemctl restart chrony.service

echo "unaffected everyday commands"
check none -- ls -la /etc
check none -- git status
check none -- pytest -q

printf '\n%d passed, %d failed\n' "$pass" "$fail"
[[ $fail -eq 0 ]]
