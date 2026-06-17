#!/bin/bash
# Wrapper script for launchd to run daily briefing with uv environment
# This ensures consistent Python environment with other skills

source /Users/scottybe/.local/bin/env 2>/dev/null
source /Users/scottybe/.env 2>/dev/null

uv run --project /Users/scottybe/.claude/skills \
    python /Users/scottybe/.claude/skills/daily-briefing/scripts/daily_briefing.py "$@"
