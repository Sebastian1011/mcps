#!/usr/bin/env bash
# Symlink the minio skill into Claude Code and/or Codex.
#
#   ./install.sh [--claude] [--codex]   (default: both)
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
CLAUDE_HOME="$HOME/.claude"

if [[ $EUID -eq 0 ]]; then
  echo "run install.sh as your normal user, not root" >&2
  exit 1
fi

do_claude=0 do_codex=0
if [[ $# -eq 0 ]]; then
  do_claude=1 do_codex=1
else
  for arg in "$@"; do
    case "$arg" in
      --claude) do_claude=1 ;;
      --codex) do_codex=1 ;;
      *) echo "usage: $0 [--claude] [--codex]" >&2; exit 2 ;;
    esac
  done
fi

if ! command -v mc >/dev/null; then
  echo "warning: mc (MinIO client) is not installed or not on PATH." >&2
  echo "         Install it from https://min.io/download before using this skill." >&2
fi

[[ $do_claude -eq 1 ]] && dirs=("$CLAUDE_HOME/skills")
[[ $do_codex -eq 1 ]] && dirs+=("$CODEX_HOME/skills")

for dir in "${dirs[@]}"; do
  [[ -d "$(dirname "$dir")" ]] || continue
  mkdir -p "$dir"
  target="$dir/minio"
  if [[ -e "$target" && ! -L "$target" ]]; then
    echo "skipping $target: exists and is not a symlink (not overwriting)" >&2
    continue
  fi
  ln -sfnT "$SRC/skills/minio" "$target"
  echo "linked $target -> $SRC/skills/minio"
done

echo
echo "Restart running Codex / Claude Code sessions to pick up the skill."
