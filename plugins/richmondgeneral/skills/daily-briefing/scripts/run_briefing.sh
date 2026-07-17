#!/bin/bash
# Wrapper for launchd to run the daily briefing in the repo's uv environment.
# All paths resolved relative to this script so it works wherever the repo
# lives (repo clone or moved) without hardcoding ~/.claude/skills.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

source "$HOME/.local/bin/env" 2>/dev/null
source "$HOME/.env" 2>/dev/null

# Find the repo root (nearest ancestor with pyproject.toml) for uv's project env.
PROJECT="$SCRIPT_DIR"
while [ "$PROJECT" != "/" ] && [ ! -f "$PROJECT/pyproject.toml" ]; do
    PROJECT="$(dirname "$PROJECT")"
done

uv run --project "$PROJECT" python "$SCRIPT_DIR/daily_briefing.py" "$@"
