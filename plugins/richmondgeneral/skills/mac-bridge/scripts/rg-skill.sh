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

  rg-skill.sh <skill> <script> [args...]          run inline (must finish < ~25s over the bridge)
  rg-skill.sh --detach <skill> <script> [args...] run in background; prints {"pid","log"} immediately
  rg-skill.sh --status <pid> <log>                poll a detached job: running/exit + log tail
  rg-skill.sh --list

The osascript bridge's MCP client abandons any call after ~30s (measured 2026-07-16:
28s ok / 30s fail). The child process is NOT killed — it keeps running blind. Any job
that can exceed ~25s MUST use --detach + --status polling instead of an inline call.

Examples:
  rg-skill.sh photos-library query_photos.py --days 7 --limit 10 --json
  rg-skill.sh --detach photos-library file_cluster.py --mint --uuids "UUID1,UUID2"
  rg-skill.sh --status 12345 ~/workspace/richmondgeneral/scratch/bridge-jobs/20260716-1.log
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

if [ "$1" = "--status" ]; then
  [ $# -eq 3 ] || usage
  pid="$2"; log="$3"
  [ -f "$log" ] || err "no such log: $log" 66
  if kill -0 "$pid" 2>/dev/null; then running=true; else running=false; fi
  exitcode="$(grep -o 'RGEXIT:[0-9]*' "$log" 2>/dev/null | tail -1 | cut -d: -f2)"
  printf '{"running":%s,"exit":%s,"log":"%s"}\n' "$running" "${exitcode:-null}" "$log"
  echo "--- log tail ---"
  tail -20 "$log"
  exit 0
fi

detach=false
if [ "$1" = "--detach" ]; then detach=true; shift; fi

[ $# -ge 2 ] || usage
skill="$1"; script="$2"; shift 2
target="$PLUGIN_ROOT/skills/$skill/scripts/$script"
[ -f "$target" ] || err "not found: skills/$skill/scripts/$script" 66
command -v uv >/dev/null 2>&1 || err "uv not on PATH after sourcing ~/.local/bin/env" 127

run_target() {
  case "$target" in
    *.py) uv run --project "$PLUGIN_ROOT" python "$target" "$@" ;;
    *.sh) bash "$target" "$@" ;;
    *)    "$target" "$@" ;;
  esac
}

if $detach; then
  jobdir="${RG_BRIDGE_JOBDIR:-$HOME/workspace/richmondgeneral/scratch/bridge-jobs}"
  mkdir -p "$jobdir"
  log="$jobdir/$(date +%Y%m%d-%H%M%S)-$skill-${script%.*}-$$.log"
  # stdout/stderr must go to the log and stdin to /dev/null, or AppleScript's
  # `do shell script` blocks on the open pipes and the detach defeats itself.
  ( set +e; run_target "$@"; echo "RGEXIT:$?" ) >>"$log" 2>&1 </dev/null &
  pid=$!
  printf '{"ok":true,"pid":%s,"log":"%s","poll":"rg-skill.sh --status %s %s"}\n' \
    "$pid" "$log" "$pid" "$log"
  exit 0
fi

run_target "$@"
