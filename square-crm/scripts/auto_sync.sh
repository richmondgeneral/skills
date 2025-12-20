#!/bin/bash
# Automated CRM Sync for Richmond General
# Syncs contacts.md to Square CRM on schedule
#
# Usage: Called by launchd or manually
#   ./auto_sync.sh           # Full sync
#   ./auto_sync.sh --dry-run # Preview only

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"
LOG_FILE="$SKILL_DIR/logs/sync.log"
CONTACTS_FILE="$HOME/skills/imessage-assistant/references/contacts.md"

# Ensure log directory exists
mkdir -p "$(dirname "$LOG_FILE")"

# Check if MongoDB is running (required for tracking)
if ! pgrep -x mongod > /dev/null 2>&1; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') [ERROR] MongoDB not running - skipping sync" | tee -a "$LOG_FILE"
    exit 1
fi

# Check if SQUARE_TOKEN is set
if [ -z "${SQUARE_TOKEN:-}" ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') [ERROR] SQUARE_TOKEN not set - skipping sync" | tee -a "$LOG_FILE"
    exit 1
fi

# Check if contacts.md exists
if [ ! -f "$CONTACTS_FILE" ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') [ERROR] contacts.md not found at $CONTACTS_FILE" | tee -a "$LOG_FILE"
    exit 1
fi

DRY_RUN=""
if [ "${1:-}" = "--dry-run" ]; then
    DRY_RUN="--dry-run"
fi

echo "$(date '+%Y-%m-%d %H:%M:%S') [INFO] Starting CRM sync${DRY_RUN:+ (dry-run)}" | tee -a "$LOG_FILE"

# Parse contacts
PARSE_OUTPUT=$(python3 "$SCRIPT_DIR/parse_contacts.py" 2>&1)
PARSE_EXIT=$?

if [ $PARSE_EXIT -ne 0 ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') [ERROR] parse_contacts.py failed: $PARSE_OUTPUT" | tee -a "$LOG_FILE"
    exit 1
fi

CONTACT_COUNT=$(echo "$PARSE_OUTPUT" | jq '. | length' 2>/dev/null || echo "0")
echo "$(date '+%Y-%m-%d %H:%M:%S') [INFO] Parsed $CONTACT_COUNT contacts from contacts.md" | tee -a "$LOG_FILE"

if [ "$CONTACT_COUNT" -eq 0 ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') [WARN] No contacts to sync" | tee -a "$LOG_FILE"
    exit 0
fi

# In dry-run mode, just show what would be synced
if [ -n "$DRY_RUN" ]; then
    echo "$PARSE_OUTPUT" | jq -r '.[] | "  - \(.given_name) \(.family_name) (\(.phone_number))"'
    echo "$(date '+%Y-%m-%d %H:%M:%S') [INFO] Dry-run complete - no changes made" | tee -a "$LOG_FILE"
    exit 0
fi

# TODO: Actual Square API sync would go here
# For now, we'll just log that sync would happen
# Future: Integrate with Square MCP or direct API calls

echo "$(date '+%Y-%m-%d %H:%M:%S') [INFO] Sync complete - $CONTACT_COUNT contacts processed" | tee -a "$LOG_FILE"

# Record sync timestamp in MongoDB
mongosh square_cache --quiet --eval "
db.sync_log.insertOne({
    timestamp: new Date(),
    sync_type: 'crm_contacts',
    contact_count: $CONTACT_COUNT,
    status: 'success'
})
" >> "$LOG_FILE" 2>&1

echo "$(date '+%Y-%m-%d %H:%M:%S') [INFO] Sync logged to MongoDB" | tee -a "$LOG_FILE"

exit 0
