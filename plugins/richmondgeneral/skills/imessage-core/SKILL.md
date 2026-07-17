---
name: imessage-core
description: Read and send iMessage/RCS/SMS messages. Use when user asks to check messages, read texts, send a text, text back, reply to someone, respond to a message, check delivery status, or list group chats. Queries chat.db directly for full sent+received history. Supports 1:1 conversations, group chats, and smart service detection (iMessage vs RCS vs SMS).
metadata:
  version: "1.2"
  author: scottybe
  updated: "2026-06-17"
  changelog: |
    v1.2 - Safe database access (critical fix):
    - All scripts now open chat.db with mode=ro&immutable=1 (was a plain
      read-write connection). chat.db is a live, WAL-mode database written
      continuously by Messages + iCloud; a plain connection could take locks
      and checkpoint the WAL, disrupting Messages/iCloud sync. immutable=1
      guarantees no locks and no WAL access. Scripts are read-only; sending
      still goes through AppleScript and is unaffected.

    v1.1 - Anthropic skills update:
    - Enhanced triggers: "text back", "reply to", "respond to a message"
    - Added author and updated fields
---

# iMessage Core

Scripts at `${CLAUDE_PLUGIN_ROOT}/skills/imessage-core/scripts/` query Messages database directly via `osascript do shell script "python3 ..."`.

## Service IDs

| Service | ID |
|---------|-----|
| iMessage | `33900AA6-BFB5-49A8-B34A-2A8F783BE2F4` |
| SMS | `E0595A22-53AF-4ECC-93BE-D717796D445F` |
| RCS | `E91298EB-BC75-4C35-9F62-8FADC3564235` |

## Read Messages

```bash
# 1:1 conversation (default 25 messages)
python3 ${CLAUDE_PLUGIN_ROOT}/skills/imessage-core/scripts/get_imessage_convo.py +1XXXXXXXXXX 25

# Deep history (100-200 for close contacts)
python3 ${CLAUDE_PLUGIN_ROOT}/skills/imessage-core/scripts/get_imessage_convo.py +1XXXXXXXXXX 200

# Group chat
python3 ${CLAUDE_PLUGIN_ROOT}/skills/imessage-core/scripts/get_imessage_convo.py --chat CHAT_ID 25

# Today's summary by contact
python3 ${CLAUDE_PLUGIN_ROOT}/skills/imessage-core/scripts/get_imessage_convo.py --today

# Get service type for contact
python3 ${CLAUDE_PLUGIN_ROOT}/skills/imessage-core/scripts/get_imessage_convo.py --service +1XXXXXXXXXX

# List group chats
python3 ${CLAUDE_PLUGIN_ROOT}/skills/imessage-core/scripts/get_imessage_convo.py --groups
```

## Send Messages

```bash
# 1:1 (auto-detects service from history)
python3 ${CLAUDE_PLUGIN_ROOT}/skills/imessage-core/scripts/send_message.py +1XXXXXXXXXX "message"

# Force specific service (for new contacts or after error=22)
python3 ${CLAUDE_PLUGIN_ROOT}/skills/imessage-core/scripts/send_message.py --service RCS +1XXXXXXXXXX "message"
python3 ${CLAUDE_PLUGIN_ROOT}/skills/imessage-core/scripts/send_message.py --service SMS +1XXXXXXXXXX "message"
python3 ${CLAUDE_PLUGIN_ROOT}/skills/imessage-core/scripts/send_message.py --service iMessage +1XXXXXXXXXX "message"

# Group chat
python3 ${CLAUDE_PLUGIN_ROOT}/skills/imessage-core/scripts/send_message.py --chat CHAT_ID "message"

# Lookup group chat details
python3 ${CLAUDE_PLUGIN_ROOT}/skills/imessage-core/scripts/send_message.py --lookup CHAT_ID
```

**Note:** MCP `send_imessage` only works for iMessage. Use scripts for RCS/Android and group chats.

## Check Delivery Status

```bash
# All messages sent today
python3 ${CLAUDE_PLUGIN_ROOT}/skills/imessage-core/scripts/sent_today.py

# Only failed/pending messages
python3 ${CLAUDE_PLUGIN_ROOT}/skills/imessage-core/scripts/sent_today.py --failed
```

## Error Handling

| Error | Cause | Fix |
|-------|-------|-----|
| `error=22` | Wrong service type | Use `--service RCS` or `--service SMS` |
| `is_delivered=0` | Pending or failed | Check with `sent_today.py --failed` |
| osascript fails | Messages not running | Open Messages.app |

## Message Escaping

Use double quotes for messages with apostrophes:

```bash
# WRONG - will fail
python3 send_message.py +1234567890 'Don\'t forget!'

# RIGHT
python3 send_message.py +1234567890 "Don't forget!"
```

## Pre-Send Verification

Before sending to ANY contact:
1. Check last message date to verify recent activity
2. Review last 5-10 messages to confirm correct person
3. Multiple contacts with same name? Pick most recent relevant conversation
