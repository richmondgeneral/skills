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
PROJECT_ROOT="$(cd "$SKILL_DIR/../.." && pwd)"
LOG_FILE="$HOME/Library/Logs/RichmondGeneral/sync.log"
CONTACTS_FILE="$PROJECT_ROOT/skills/contacts-manager/references/contacts.md"
SQUARE_API="https://connect.squareup.com/v2"
SQUARE_VERSION="2026-04-21"

# Resolve Square token: existing env → macOS Keychain → project .env
# (launchd/cron don't inherit shell env, so we fetch directly)
resolve_square_token() {
    if [ -n "${SQUARE_TOKEN:-}" ]; then return 0; fi
    if [ -n "${SQUARE_ACCESS_TOKEN:-}" ]; then export SQUARE_TOKEN="$SQUARE_ACCESS_TOKEN"; return 0; fi
    if command -v security >/dev/null 2>&1; then
        local t
        t="$(security find-generic-password -a "$USER" -s SQUARE_ACCESS_TOKEN -w 2>/dev/null || true)"
        if [ -n "$t" ]; then export SQUARE_ACCESS_TOKEN="$t" SQUARE_TOKEN="$t"; return 0; fi
    fi
    if [ -f "$PROJECT_ROOT/.env" ]; then
        local t
        t=$(awk -F= '/^SQUARE_ACCESS_TOKEN=/{print $2; exit}' "$PROJECT_ROOT/.env")
        if [ -n "$t" ]; then export SQUARE_ACCESS_TOKEN="$t" SQUARE_TOKEN="$t"; return 0; fi
    fi
    return 1
}
resolve_square_token || true

mkdir -p "$(dirname "$LOG_FILE")"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [$1] $2" | tee -a "$LOG_FILE"
}

# Check for dry-run flag FIRST (before other prereqs)
DRY_RUN=""
if [ "${1:-}" = "--dry-run" ]; then
    DRY_RUN="true"
fi

# Check MongoDB (required for logging)
if ! pgrep -x mongod > /dev/null 2>&1; then
    log "ERROR" "MongoDB not running - skipping sync"
    exit 1
fi

# Check contacts.md exists
if [ ! -f "$CONTACTS_FILE" ]; then
    log "ERROR" "contacts.md not found at $CONTACTS_FILE"
    exit 1
fi

log "INFO" "Starting CRM sync${DRY_RUN:+ (dry-run)}"

# Parse contacts (capture exit code without tripping `set -e`)
PARSE_EXIT=0
PARSE_OUTPUT=$(CONTACTS_FILE="$CONTACTS_FILE" python3 "$SCRIPT_DIR/parse_contacts.py" 2>&1) || PARSE_EXIT=$?

if [ $PARSE_EXIT -ne 0 ]; then
    log "ERROR" "parse_contacts.py failed: $PARSE_OUTPUT"
    exit 1
fi

CONTACT_COUNT=$(echo "$PARSE_OUTPUT" | jq '. | length' 2>/dev/null || echo "0")
log "INFO" "Parsed $CONTACT_COUNT contacts from contacts.md"

if [ "$CONTACT_COUNT" -eq 0 ]; then
    log "WARN" "No contacts to sync"
    exit 0
fi

# In dry-run mode, show what would be synced and exit
if [ -n "$DRY_RUN" ]; then
    echo "$PARSE_OUTPUT" | jq -r '.[] | "  - \(.name) (\(.phone)) [\(.category)]"'
    log "INFO" "Dry-run complete - no changes made"
    exit 0
fi

# Only check SQUARE_TOKEN for actual sync
if [ -z "${SQUARE_TOKEN:-}" ]; then
    log "ERROR" "SQUARE_TOKEN not set - skipping sync"
    exit 1
fi

# API functions
search_customer_by_phone() {
    curl -s -X POST "$SQUARE_API/customers/search" \
        -H "Square-Version: $SQUARE_VERSION" \
        -H "Authorization: Bearer $SQUARE_TOKEN" \
        -H "Content-Type: application/json" \
        -d "{\"query\":{\"filter\":{\"phone_number\":{\"exact\":\"$1\"}}}}"
}

create_customer() {
    curl -s -X POST "$SQUARE_API/customers" \
        -H "Square-Version: $SQUARE_VERSION" \
        -H "Authorization: Bearer $SQUARE_TOKEN" \
        -H "Content-Type: application/json" \
        -d "$1"
}

update_customer() {
    curl -s -X PUT "$SQUARE_API/customers/$1" \
        -H "Square-Version: $SQUARE_VERSION" \
        -H "Authorization: Bearer $SQUARE_TOKEN" \
        -H "Content-Type: application/json" \
        -d "$2"
}

add_to_group() {
    curl -s -X PUT "$SQUARE_API/customers/$1/groups/$2" \
        -H "Square-Version: $SQUARE_VERSION" \
        -H "Authorization: Bearer $SQUARE_TOKEN"
}

# Counters
CREATED=0
UPDATED=0
ERRORS=0

# Save to temp file for iteration
TMP_FILE=$(mktemp)
echo "$PARSE_OUTPUT" > "$TMP_FILE"

for i in $(seq 0 $((CONTACT_COUNT - 1))); do
    contact=$(jq ".[$i]" "$TMP_FILE")
    NAME=$(echo "$contact" | jq -r '.name')
    PHONE=$(echo "$contact" | jq -r '.phone')
    SQUARE_REQUEST=$(echo "$contact" | jq -c '.square_request')
    GROUP_IDS=$(echo "$contact" | jq -r '.group_ids[]?' 2>/dev/null || true)
    
    # Search for existing customer
    SEARCH_RESULT=$(search_customer_by_phone "$PHONE")
    EXISTING_ID=$(echo "$SEARCH_RESULT" | jq -r '.customers[0].id // empty' 2>/dev/null || true)
    
    if [ -n "$EXISTING_ID" ]; then
        UPDATE_RESULT=$(update_customer "$EXISTING_ID" "$SQUARE_REQUEST")
        if echo "$UPDATE_RESULT" | jq -e '.customer.id' > /dev/null 2>&1; then
            log "INFO" "Updated: $NAME -> $EXISTING_ID"
            UPDATED=$((UPDATED + 1))
        else
            ERROR_MSG=$(echo "$UPDATE_RESULT" | jq -r '.errors[0].detail // "Unknown"')
            log "ERROR" "Failed to update $NAME: $ERROR_MSG"
            ERRORS=$((ERRORS + 1))
        fi
        CUSTOMER_ID="$EXISTING_ID"
    else
        CREATE_RESULT=$(create_customer "$SQUARE_REQUEST")
        CUSTOMER_ID=$(echo "$CREATE_RESULT" | jq -r '.customer.id // empty' 2>/dev/null || true)
        
        if [ -n "$CUSTOMER_ID" ]; then
            log "INFO" "Created: $NAME -> $CUSTOMER_ID"
            CREATED=$((CREATED + 1))
        else
            ERROR_MSG=$(echo "$CREATE_RESULT" | jq -r '.errors[0].detail // "Unknown"')
            log "ERROR" "Failed to create $NAME: $ERROR_MSG"
            ERRORS=$((ERRORS + 1))
            continue
        fi
    fi
    
    # Add to groups
    if [ -n "$CUSTOMER_ID" ] && [ -n "$GROUP_IDS" ]; then
        for GID in $GROUP_IDS; do
            add_to_group "$CUSTOMER_ID" "$GID" > /dev/null 2>&1 && \
                log "INFO" "Added $NAME to group" || \
                log "WARN" "Failed group add for $NAME"
        done
    fi
    
    sleep 1  # Rate limit
done

rm -f "$TMP_FILE"

log "INFO" "Sync complete: Created=$CREATED Updated=$UPDATED Errors=$ERRORS"

# Log to MongoDB
STATUS="success"
[ "$ERRORS" -gt 0 ] && STATUS="partial"

mongosh square_cache --quiet --eval "db.sync_log.insertOne({
    timestamp: new Date(),
    sync_type: 'crm_contacts',
    contact_count: $CONTACT_COUNT,
    created: $CREATED,
    updated: $UPDATED,
    errors: $ERRORS,
    status: '$STATUS'
})" >> "$LOG_FILE" 2>&1 || true

log "INFO" "Sync logged to MongoDB"
