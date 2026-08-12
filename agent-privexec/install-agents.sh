#!/usr/bin/env bash
# Phases 2-4: agent-side enforcement and the shared skill. Run as your normal
# user, AFTER install.sh has established the OS boundary.
#
#   ./install-agents.sh [--codex] [--claude] [--skill]   (default: all three)
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
CLAUDE_HOME="$HOME/.claude"

do_codex=0 do_claude=0 do_skill=0
if [[ $# -eq 0 ]]; then
  do_codex=1 do_claude=1 do_skill=1
else
  for arg in "$@"; do
    case "$arg" in
      --codex) do_codex=1 ;;
      --claude) do_claude=1 ;;
      --skill) do_skill=1 ;;
      *) echo "usage: $0 [--codex] [--claude] [--skill]" >&2; exit 2 ;;
    esac
  done
fi

if [[ $EUID -eq 0 ]]; then
  echo "run install-agents.sh as your normal user, not root" >&2
  exit 1
fi

if [[ ! -x /usr/local/bin/agent-privexec ]]; then
  echo "warning: /usr/local/bin/agent-privexec is not installed yet." >&2
  echo "         Establish the OS boundary first:  sudo $SRC/install.sh" >&2
fi

# ---------------------------------------------------------------- Codex -----
if [[ $do_codex -eq 1 ]]; then
  mkdir -p "$CODEX_HOME/rules"
  install -m 0644 "$SRC/agents/codex/privileged.rules" "$CODEX_HOME/rules/privileged.rules"
  echo "installed $CODEX_HOME/rules/privileged.rules"
  if command -v codex >/dev/null; then
    "$SRC/tests/test_codex_rules.sh" || echo "warning: codex rule verification failed" >&2
  fi
fi

# --------------------------------------------------------------- Claude -----
if [[ $do_claude -eq 1 ]]; then
  mkdir -p "$CLAUDE_HOME/hooks"
  install -m 0755 "$SRC/agents/claude/hooks/agent-privexec-guard.py" \
                  "$CLAUDE_HOME/hooks/agent-privexec-guard.py"
  echo "installed $CLAUDE_HOME/hooks/agent-privexec-guard.py"

  python3 - "$CLAUDE_HOME/settings.json" <<'PY'
import json, os, shutil, sys

path = sys.argv[1]
settings = {}
if os.path.exists(path):
    shutil.copy2(path, path + ".agent-privexec.bak")
    with open(path) as fh:
        settings = json.load(fh)

deny = [
    "Bash(sudo)", "Bash(sudo:*)", "Bash(sudo *)",
    "Bash(/usr/bin/sudo:*)", "Bash(/usr/bin/sudo *)",
    "Bash(sudoedit:*)",
    "Bash(pkexec)", "Bash(pkexec:*)", "Bash(pkexec *)",
    "Bash(/usr/bin/pkexec:*)", "Bash(/usr/bin/pkexec *)",
    "Bash(su:*)", "Bash(doas:*)", "Bash(run0:*)",
    "Bash(pkttyagent:*)", "Bash(visudo:*)",
]
ask = ["Bash(agent-privexec:*)", "Bash(/usr/local/bin/agent-privexec:*)"]

perms = settings.setdefault("permissions", {})
for key, wanted in (("deny", deny), ("ask", ask)):
    current = perms.setdefault(key, [])
    for rule in wanted:
        if rule not in current:
            current.append(rule)

hook_cmd = 'python3 "$HOME/.claude/hooks/agent-privexec-guard.py"'
pre = settings.setdefault("hooks", {}).setdefault("PreToolUse", [])
entry = next((m for m in pre if m.get("matcher") == "Bash"), None)
if entry is None:
    entry = {"matcher": "Bash", "hooks": []}
    pre.append(entry)
if not any(h.get("command") == hook_cmd for h in entry.setdefault("hooks", [])):
    entry["hooks"].append({"type": "command", "command": hook_cmd})

with open(path, "w") as fh:
    json.dump(settings, fh, indent=2)
    fh.write("\n")
print(f"updated {path} (backup: {path}.agent-privexec.bak)")
PY
fi

# ---------------------------------------------------------------- Skill -----
if [[ $do_skill -eq 1 ]]; then
  for dir in "$CLAUDE_HOME/skills" "$CODEX_HOME/skills"; do
    [[ -d "$(dirname "$dir")" ]] || continue
    mkdir -p "$dir"
    ln -sfnT "$SRC/skills/privileged-exec" "$dir/privileged-exec"
    echo "linked $dir/privileged-exec -> $SRC/skills/privileged-exec"
  done
fi

echo
echo "Restart running Codex / Claude Code sessions to pick up the new rules."
