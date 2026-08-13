#!/usr/bin/env bash
# Remove the minio skill symlinks installed by install.sh.
# Only removes a target if it is a symlink pointing into this repo -
# never touches a real directory a user created themselves.
#
#   ./uninstall.sh [--claude] [--codex]   (default: both)
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
CLAUDE_HOME="$HOME/.claude"

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

[[ $do_claude -eq 1 ]] && dirs=("$CLAUDE_HOME/skills/minio")
[[ $do_codex -eq 1 ]] && dirs+=("$CODEX_HOME/skills/minio")

for target in "${dirs[@]}"; do
  if [[ -L "$target" ]] && [[ "$(readlink -f "$target")" == "$SRC/skills/minio" ]]; then
    rm "$target"
    echo "removed $target"
  elif [[ -e "$target" ]]; then
    echo "skipping $target: not a symlink to this repo (leaving it alone)" >&2
  else
    echo "$target not present, nothing to do"
  fi
done
