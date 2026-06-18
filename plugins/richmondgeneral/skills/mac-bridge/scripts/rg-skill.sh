#!/usr/bin/env bash
#
# rg-skill.sh — run a Richmond General skill script on the Mac, in the plugin's
# uv environment. Built for the Cowork -> Mac osascript bridge:
#
#   osascript: do shell script "<this-path> <skill> <script> [args...]"
#
# It sources the uv env (the osascript `do shell script` shell is bare — no uv on
# PATH, only the system Python 3.9.6), finds the plugin root, and runs the script
# via uv so deps resolve from the bundled pyproject.toml.
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Plugin root = nearest ancestor containing .claude-plugin/plugin.json
PLUGIN_ROOT="$SCRIPT_DIR"
while [ "$PLUGIN_ROOT" != "/" ] && [ ! -f "$PLUGIN_ROOT/.claude-plugin/plugin.json" ]; do
  PLUGIN_ROOT="$(dirname "$PLUGIN_ROOT")"
done

# Put uv on PATH (the bare non-login shell over the bridge doesn't have it).
# shellcheck disable=SC1091
source "$HOME/.local/bin/env" 2>/dev/null || true

err() { printf '{"ok":false,"error":"%s"}\n' "$1" >&2; exit "${2:-1}"; }

usage() {
  cat >&2 <<'EOF'
rg-skill.sh — run a Richmond General skill script on the Mac (plugin uv env).

  rg-skill.sh <skill> <script> [args...]
  rg-skill.sh --list

Examples:
  rg-skill.sh photos-library query_photos.py --recent 10 --json
  rg-skill.sh image-processor clean.py in.png --output out.png --remove "price tag"
EOF
  exit 2
}

[ $# -ge 1 ] || usage

if [ "$1" = "--list" ] || [ "$1" = "-l" ]; then
  shopt -s nullglob
  for s in "$PLUGIN_ROOT"/skills/*/scripts/*.py "$PLUGIN_ROOT"/skills/*/scripts/*.sh; do
    echo "$(basename "$(dirname "$(dirname "$s")")")  $(basename "$s")"
  done | sort
  exit 0
fi

[ $# -ge 2 ] || usage
skill="$1"; script="$2"; shift 2
target="$PLUGIN_ROOT/skills/$skill/scripts/$script"
[ -f "$target" ] || err "not found: skills/$skill/scripts/$script" 66
command -v uv >/dev/null 2>&1 || err "uv not on PATH after sourcing ~/.local/bin/env" 127

case "$target" in
  *.py) exec uv run --project "$PLUGIN_ROOT" python "$target" "$@" ;;
  *.sh) exec bash "$target" "$@" ;;
  *)    exec "$target" "$@" ;;
esac
