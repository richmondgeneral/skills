#!/bin/bash
# Simple helper to update Apple Contacts by phone number
# Uses the proven pattern you already used with osascript
#
# Usage:
#   ./update_contact_simple.sh "+13129143889" "Mike Giba" "+17085970480"
#   ./update_contact_simple.sh "+13129143889" "Mike Giba"  # name only
#
# Args:
#   $1 = Primary phone (E.164 format, e.g., +13129143889)
#   $2 = Full name (optional)
#   $3 = Alternate phone (optional)

set -e

if [ $# -lt 1 ]; then
    echo "Usage: $0 <primary_phone> [full_name] [alternate_phone]"
    echo ""
    echo "Examples:"
    echo "  $0 +13129143889 'Mike Giba' '+17085970480'"
    echo "  $0 +13129143889 'Mike Giba'"
    exit 1
fi

PRIMARY_PHONE="$1"
NEW_NAME="${2:-}"
ALT_PHONE="${3:-}"

echo "📱 Updating contact for: $PRIMARY_PHONE"

# Normalize phone (strip everything but digits, ensure +1 prefix)
NORMALIZED=$(echo "$PRIMARY_PHONE" | grep -o '[0-9]*' | tail -1)
if [ ${#NORMALIZED} -eq 10 ]; then
    NORMALIZED="+1$NORMALIZED"
elif [ ${#NORMALIZED} -eq 11 ] && [[ $NORMALIZED == 1* ]]; then
    NORMALIZED="+$NORMALIZED"
else
    NORMALIZED="+$NORMALIZED"
fi

# Update name if provided
if [ -n "$NEW_NAME" ]; then
    echo "Updating name to: $NEW_NAME"
    
    osascript << EOF
tell application "Contacts"
    repeat with person in (every person)
        repeat with phoneEntry in (every phone of person)
            if value of phoneEntry contains "$(echo $NORMALIZED | grep -o '[0-9]*' | tail -1)" then
                set name of person to "$NEW_NAME"
                return "SUCCESS"
            end if
        end repeat
    end repeat
    return "NOT_FOUND"
end tell
EOF
    echo "✅ Name updated"
fi

# Add alternate phone if provided
if [ -n "$ALT_PHONE" ]; then
    echo "Adding alternate phone: $ALT_PHONE"
    
    # Normalize alt phone
    ALT_NORMALIZED=$(echo "$ALT_PHONE" | grep -o '[0-9]*' | tail -1)
    if [ ${#ALT_NORMALIZED} -eq 10 ]; then
        ALT_NORMALIZED="+1$ALT_NORMALIZED"
    elif [ ${#ALT_NORMALIZED} -eq 11 ] && [[ $ALT_NORMALIZED == 1* ]]; then
        ALT_NORMALIZED="+$ALT_NORMALIZED"
    else
        ALT_NORMALIZED="+$ALT_NORMALIZED"
    fi
    
    osascript << EOF
tell application "Contacts"
    repeat with person in (every person)
        repeat with phoneEntry in (every phone of person)
            if value of phoneEntry contains "$(echo $NORMALIZED | grep -o '[0-9]*' | tail -1)" then
                make new phone at end of phones of person with properties {value: "$ALT_NORMALIZED", label: "other"}
                return "SUCCESS"
            end if
        end repeat
    end repeat
    return "NOT_FOUND"
end tell
EOF
    echo "✅ Alternate phone added"
fi

echo ""
echo "✅ Contact updated successfully!"
