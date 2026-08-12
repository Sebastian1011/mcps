#!/usr/bin/env bash
# Remove the OS-level components. Must run as root: sudo ./uninstall.sh
# The policy file is kept unless --purge is given.
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "uninstall.sh must run as root: sudo $0" >&2
  exit 1
fi

rm -fv /usr/local/bin/agent-privexec \
       /usr/local/libexec/agent-privexec-root \
       /usr/share/polkit-1/actions/com.local.agent-privexec.policy

if [[ "${1:-}" == "--purge" ]]; then
  rm -rfv /etc/agent-privexec
else
  echo "kept /etc/agent-privexec (use --purge to remove)"
fi

echo
echo "Agent-side configuration is not touched. To remove it:"
echo "  rm ~/.codex/rules/privileged.rules ~/.claude/hooks/agent-privexec-guard.py"
echo "  rm ~/.codex/skills/privileged-exec ~/.claude/skills/privileged-exec"
echo "  edit ~/.claude/settings.json to drop the agent-privexec permissions and hook"
