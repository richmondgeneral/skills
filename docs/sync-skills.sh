#!/usr/bin/env bash

# Sync canonical skills source to both Claude and Codex skill destinations.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd -P)"
SYNC_SCRIPT="$SCRIPT_DIR/sync-to-claude.sh"

if [[ ! -x "$SYNC_SCRIPT" ]]; then
  echo "sync script missing or not executable: $SYNC_SCRIPT" >&2
  exit 1
fi

SOURCE_DIR="${SKILLS_SOURCE_DIR:-$REPO_ROOT}"
CLAUDE_TARGET="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}"
CODEX_TARGET="${CODEX_SKILLS_DIR:-$HOME/.codex/skills}"

EXTRA_ARGS=("$@")

echo "Canonical source: $SOURCE_DIR"
echo "Claude target:    $CLAUDE_TARGET"
echo "Codex target:     $CODEX_TARGET"
echo

echo "==> Syncing Claude target"
"$SYNC_SCRIPT" --source "$SOURCE_DIR" --target "$CLAUDE_TARGET" "${EXTRA_ARGS[@]}"

echo

echo "==> Syncing Codex target"
"$SYNC_SCRIPT" --source "$SOURCE_DIR" --target "$CODEX_TARGET" "${EXTRA_ARGS[@]}"

echo

echo "Dual-target sync complete."
