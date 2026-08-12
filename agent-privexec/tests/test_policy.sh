#!/usr/bin/env bash
# Policy tests for the root helper. Runs unprivileged in --dry-run against the
# repository policy, so no authentication and no root are required.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HELPER="$ROOT/system/libexec/agent-privexec-root"
POLICY="$ROOT/system/etc/policy.toml"

pass=0 fail=0

# expect EXPECTED_CODE "description" -- <request...>
expect() {
  local want="$1" desc="$2"; shift 3
  local out code
  out="$("$HELPER" --dry-run --policy "$POLICY" --request-id test --caller-agent cli \
        --caller-cwd "$PWD" -- "$@" 2>&1)"
  code=$?
  if [[ $code -eq $want ]]; then
    pass=$((pass + 1))
    printf '  ok   %-58s (exit %d)\n' "$desc" "$code"
  else
    fail=$((fail + 1))
    printf '  FAIL %-58s (want %d, got %d)\n       %s\n' "$desc" "$want" "$code" "$out"
  fi
}

ALLOW=0
DENY=3

echo "allowed operations"
expect $ALLOW "exec /usr/bin/id"                 -- exec /usr/bin/id
expect $ALLOW "exec /usr/bin/apt install"        -- exec /usr/bin/apt install -y jq
expect $ALLOW "systemctl restart unit"           -- systemctl restart chrony.service
expect $ALLOW "systemctl daemon-reload"          -- systemctl daemon-reload
expect $ALLOW "chmod 0644 /etc/hostname"         -- chmod 0644 /etc/hostname
expect $ALLOW "chown root:root /etc/hostname"    -- chown root:root /etc/hostname
expect $ALLOW "install-file into /etc"           -- install-file 0644 root:root "$POLICY" /etc/agent-privexec-test.conf

echo "shells and interpreters as privileged targets"
expect $DENY  "exec /bin/bash"                   -- exec /bin/bash
expect $DENY  "exec /usr/bin/bash"               -- exec /usr/bin/bash
expect $DENY  "exec /bin/sh -c id"               -- exec /bin/sh -c id
expect $DENY  "exec /usr/bin/env bash"           -- exec /usr/bin/env bash
expect $DENY  "exec /usr/bin/python3 -c"         -- exec /usr/bin/python3 -c 'import os;os.system("sh")'
expect $DENY  "exec /usr/bin/sudo"               -- exec /usr/bin/sudo id
expect $DENY  "exec /usr/bin/pkexec"             -- exec /usr/bin/pkexec id
expect $DENY  "exec /usr/bin/tee"                -- exec /usr/bin/tee /etc/sudoers

echo "path traversal into the denylist"
expect $DENY  "exec /bin/../bin/bash"            -- exec /bin/../bin/bash
expect $DENY  "exec relative path"               -- exec bash

echo "non-allowlisted programs"
expect $DENY  "exec /usr/bin/wc"                 -- exec /usr/bin/wc /etc/hostname
expect $DENY  "exec missing program"             -- exec /usr/bin/definitely-not-here

echo "protected paths"
expect $DENY  "chmod 0777 /etc/sudoers"          -- chmod 0777 /etc/sudoers
expect $DENY  "chown user /etc/shadow"           -- chown "$(id -un)" /etc/shadow
expect $DENY  "chmod on the root helper"         -- chmod 0777 /usr/local/libexec/agent-privexec-root
expect $DENY  "install-file into /etc/sudoers.d" -- install-file 0644 root:root "$POLICY" /etc/sudoers.d/x
expect $DENY  "install-file into polkit actions" -- install-file 0644 root:root "$POLICY" /usr/share/polkit-1/actions/x.policy
expect $DENY  "install-file into /etc/agent-privexec" -- install-file 0644 root:root "$POLICY" /etc/agent-privexec/policy.toml

echo "argument validation"
expect $DENY  "chmod symbolic mode"              -- chmod u+s /etc/hostname
expect $DENY  "chmod setuid bit"                 -- chmod 4755 /etc/hostname
expect $DENY  "chmod relative path"              -- chmod 0644 hostname
expect $DENY  "chmod extra arguments"            -- chmod -R 0644 /etc /tmp
expect $DENY  "chown unknown user"               -- chown nosuchuser42 /etc/hostname
expect $DENY  "chown shell metacharacters"       -- chown 'root; id' /etc/hostname
expect $DENY  "systemctl unknown verb"           -- systemctl cat chrony.service
expect $DENY  "systemctl bad unit name"          -- systemctl restart '../../etc/passwd'
expect $DENY  "systemctl daemon-reload + unit"   -- systemctl daemon-reload chrony.service
expect $DENY  "install-file outside prefixes"    -- install-file 0644 root:root "$POLICY" /tmp/x
expect $DENY  "install-file missing source"      -- install-file 0644 root:root /nonexistent/src /etc/x
expect $DENY  "unknown operation"                -- rm -rf /
expect $DENY  "control character in argument"    -- exec /usr/bin/id $'a\nb'

echo "policy override is refused only while privileged (unprivileged here: honoured)"
printf '\n%d passed, %d failed\n' "$pass" "$fail"
[[ $fail -eq 0 ]]
