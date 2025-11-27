---
name: imessage-assistant
description: Check and respond to iMessages with full context. Use when user asks to check messages, read texts, respond to texts, send messages, or mentions specific contacts. Queries chat.db directly for BOTH sent and received messages. Supports 1:1, group chats, and RCS/SMS/iMessage smart sending.
---

# iMessage Assistant

## Bootstrap

On first use, install scripts if needed:

```bash
if [ ! -f ~/scripts/get_imessage_convo.py ]; then
    mkdir -p ~/scripts
    cp /mnt/skills/user/imessage-assistant/scripts/*.py ~/scripts/
    chmod +x ~/scripts/*.py
fi
```

---

## Quick Reference

| Contact | Phone | Service | AppleScript ID |
|---------|-------|---------|----------------|
| Freeman (Dad) | +12242308079 | RCS | `E91298EB-BC75-4C35-9F62-8FADC3564235` |
| Dawn | +18472871148 | iMessage | `33900AA6-BFB5-49A8-B34A-2A8F783BE2F4` |
| Jennifer | +16305444884 | iMessage | `33900AA6-BFB5-49A8-B34A-2A8F783BE2F4` |
| Jeff Thompson | +18475677182 | iMessage | `33900AA6-BFB5-49A8-B34A-2A8F783BE2F4` |
| Mike (Richmond) | +13129143889 | RCS | `E91298EB-BC75-4C35-9F62-8FADC3564235` |
| Amy D (HOA) | +17736763930 | iMessage | `33900AA6-BFB5-49A8-B34A-2A8F783BE2F4` |

**Group Chats:** Dawn & Jennifer = 980 | HOA Drywall = 1343 | Shagbark Neighbors = 1053

**Service IDs:** iMessage = `33900AA6-BFB5-49A8-B34A-2A8F783BE2F4` | SMS = `E0595A22-53AF-4ECC-93BE-D717796D445F` | RCS = `E91298EB-BC75-4C35-9F62-8FADC3564235`

See `references/contacts.md` for style preferences and detailed context.

---

## Pre-Send Verification (CRITICAL)

**Before sending to ANY contact, especially common names like "Mike":**

1. **Check last message date** to verify recent activity
2. **Review last 5-10 messages** to confirm correct person/context
3. **Multiple contacts with same name?** Pick the one with most recent relevant conversation

```sql
-- Verify last message date
SELECT datetime(MAX(m.date)/1000000000 + 978307200, 'unixepoch', 'localtime')
FROM message m JOIN handle h ON m.handle_id = h.ROWID
WHERE h.id LIKE '%PHONE%'
```

**Failure example:** "Text Mike about flea market" → Multiple Mikes → Wrong Mike selected without checking dates → Message sent to contact not texted since 2023.

---

## Core Workflow

### Check Messages

**Always prefer direct database query** (MCP `read_imessages` only returns incoming):

```python
# 1:1 conversation
query = '''
SELECT datetime(m.date/1000000000 + 978307200, 'unixepoch', 'localtime') as ts,
       m.is_from_me, m.text, m.attributedBody
FROM message m JOIN handle h ON m.handle_id = h.ROWID
WHERE h.id LIKE '%PHONE%'
ORDER BY m.date DESC LIMIT 20
'''

# Group chat
query = '''
SELECT datetime(m.date/1000000000 + 978307200, 'unixepoch', 'localtime') as ts,
       m.is_from_me, h.id as sender, m.text, m.attributedBody
FROM message m
JOIN chat_message_join cmj ON cmj.message_id = m.ROWID
LEFT JOIN handle h ON m.handle_id = h.ROWID
WHERE cmj.chat_id = CHAT_ID
ORDER BY m.date DESC LIMIT 20
'''
```

### Extract Text from Blob

When `text` is NULL, content is in `attributedBody`:

```python
def extract_text(blob):
    if not blob: return None
    idx = blob.find(b"NSString")
    if idx == -1: return None
    plus_idx = blob.find(b"+", idx)
    if plus_idx == -1: return None
    start = plus_idx + 2
    end = len(blob)
    for marker in [b"NSDictionary", b"\x00\x00\x00"]:
        pos = blob.find(marker, start)
        if pos != -1 and pos < end: end = pos
    text = blob[start:end].decode("utf-8", errors="ignore")
    return re.sub(r"iI[A-Z0-9>()]*$", "", text).strip()
```

### Send Messages

**MCP `send_imessage` fails for RCS/Android.** Use osascript:

```applescript
tell application "Messages"
    send "message" to buddy "+1234567890" of service id "SERVICE_ID"
end tell
```

**Workflow:**
1. Check contact's service in Quick Reference
2. If unknown: `SELECT service FROM message WHERE handle_id matches phone AND is_delivered=1 ORDER BY date DESC LIMIT 1`
3. Send via osascript with correct service ID

---

## Local Scripts

**Location:** `~/scripts/`

```bash
# 1:1 conversation
python3 get_imessage_convo.py PHONE_NUMBER 20

# Get service type
python3 get_imessage_convo.py --service PHONE_NUMBER

# List group chats
python3 get_imessage_convo.py --groups

# Get group chat
python3 get_imessage_convo.py --chat CHAT_ID 25

# Send to 1:1 (auto-detects service)
python3 send_message.py PHONE_NUMBER "message"

# Send to group chat
python3 send_message.py --chat CHAT_ID "message"
```

**Note:** MCP `send_imessage` only works for 1:1 iMessage. Use `send_message.py` for RCS and groups.

---

## Error Handling

| Error | Cause | Fix |
|-------|-------|-----|
| `error=22` | Wrong service type | Query correct service, retry with osascript |
| `is_delivered=0` | Message pending/failed | Check error column |
| osascript fails | Messages app not running | Open Messages.app first |
| Wrong contact sent | Multiple contacts same name | **Always verify last message date before sending** |

---

## Spam Filter

Ignore 800/855/888 numbers with promotional content, garbled URLs, or game links (wgames.app).
