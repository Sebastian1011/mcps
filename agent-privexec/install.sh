#!/usr/bin/env bash
# Phase 1: install the OS-level privileged execution boundary.
# Must run as root:   sudo ./install.sh
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

BIN=/usr/local/bin/agent-privexec
HELPER=/usr/local/libexec/agent-privexec-root
ACTION=/usr/share/polkit-1/actions/com.local.agent-privexec.policy
POLICY_DIR=/etc/agent-privexec
POLICY="$POLICY_DIR/policy.toml"

if [[ $EUID -ne 0 ]]; then
  echo "install.sh must run as root: sudo $0" >&2
  exit 1
fi

PKEXEC=/usr/bin/pkexec
[[ -x "$PKEXEC" ]] || { echo "$PKEXEC not found - install pkexec / polkit" >&2; exit 1; }
if [[ $(stat -c %u "$PKEXEC") -ne 0 || ! -u "$PKEXEC" ]]; then
  echo "$PKEXEC must be owned by root and have its setuid bit" >&2
  echo "repair the host's pkexec package before installing agent-privexec" >&2
  exit 1
fi
command -v python3 >/dev/null || { echo "python3 not found" >&2; exit 1; }
python3 - <<'EOF' || { echo "python3 >= 3.11 required (tomllib)" >&2; exit 1; }
import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)
EOF

python3 -m py_compile "$SRC/system/bin/agent-privexec" "$SRC/system/libexec/agent-privexec-root"
rm -rf "$SRC/system/bin/__pycache__" "$SRC/system/libexec/__pycache__"

install -o root -g root -m 0755 -D "$SRC/system/bin/agent-privexec" "$BIN"
install -o root -g root -m 0755 -D "$SRC/system/libexec/agent-privexec-root" "$HELPER"
install -o root -g root -m 0644 -D "$SRC/system/polkit/com.local.agent-privexec.policy" "$ACTION"

install -o root -g root -m 0755 -d "$POLICY_DIR"
if [[ -e "$POLICY" ]]; then
  echo "keeping existing $POLICY (new default written to $POLICY.dist)"
  install -o root -g root -m 0644 "$SRC/system/etc/policy.toml" "$POLICY.dist"
else
  install -o root -g root -m 0644 "$SRC/system/etc/policy.toml" "$POLICY"
fi

# Sanity check: the policy must parse, and every binaries.* entry must exist.
python3 - "$POLICY" <<'EOF'
import os, sys, tomllib
with open(sys.argv[1], "rb") as fh:
    policy = tomllib.load(fh)
missing = [p for p in policy.get("binaries", {}).values() if not os.path.isfile(os.path.realpath(p))]
if missing:
    print(f"warning: policy references missing binaries: {', '.join(missing)}", file=sys.stderr)
absent = [p for p in policy.get("exec", {}).get("allowed", []) if not os.path.isfile(os.path.realpath(p))]
if absent:
    print(f"note: allowlisted programs not installed on this host: {', '.join(absent)}", file=sys.stderr)
EOF

echo
echo "Installed:"
ls -l "$BIN" "$HELPER" "$ACTION" "$POLICY"
echo
echo "Verify (as your normal user, from a desktop session):"
echo "  agent-privexec --dry-run exec -- /usr/bin/id       # allowed, expects GUI authentication"
echo "  agent-privexec --dry-run exec -- /bin/bash         # denied by policy, exit 3"
echo "  journalctl -t agent-privexec -n 5 --output cat     # audit trail"
