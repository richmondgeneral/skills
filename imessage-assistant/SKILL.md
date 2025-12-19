---
name: imessage-assistant
description: Check and respond to iMessages with full context. Use when user asks to check messages, read texts, respond to texts, send messages, check today's messages, or mentions specific contacts. Queries chat.db directly for BOTH sent and received messages. Supports 1:1, group chats, and RCS/SMS/iMessage smart sending. Can identify unknown numbers and match to contacts.
---

# iMessage Assistant

Scripts run on Scotty's Mac via `osascript do shell script "python3 ..."` to query Messages database directly.

**Scripts location:** `~/skills/imessage-assistant/scripts/`

---

## Quick Reference

| Contact | Phone | Service |
|---------|-------|---------|
| Freeman (Dad) | +12242308079 | RCS |
| Dawn | +18472871148 | iMessage |
| Sue Miller | +18152362387 | RCS |
| Jennifer | +16305444884 | iMessage |
| Jeff Thompson | +18475677182 | iMessage |
| Mike Giba | +13129143889 | RCS |
| Amy D (HOA) | +17736763930 | iMessage |
| Gary Goza Sr | +18474179386 | iMessage |
| Jamie Boutain | +16519834441 | iMessage |

**Group Chats:** Dawn & Jennifer = 980 | RG Building Mgmt (Dawn + Sue) = TBD | HOA Drywall = 1343 | Shagbark = 1053

**Service IDs:** 
- iMessage = `33900AA6-BFB5-49A8-B34A-2A8F783BE2F4`
- SMS = `E0595A22-53AF-4ECC-93BE-D717796D445F`
- RCS = `E91298EB-BC75-4C35-9F62-8FADC3564235`

**Full contact details & style notes:** See `references/contacts.md`  
**Known spam numbers:** See `references/spam_numbers.md`

---

## Core Workflows

### Check Messages

```bash
# 1:1 conversation (default 25 messages)
python3 ~/skills/imessage-assistant/scripts/get_imessage_convo.py +1XXXXXXXXXX 20

# Deep history for close friends (use 100-200 for context)
python3 ~/skills/imessage-assistant/scripts/get_imessage_convo.py +1XXXXXXXXXX 200

# Group chat
python3 ~/skills/imessage-assistant/scripts/get_imessage_convo.py --chat CHAT_ID 25

# Today's summary (for daily audits)
python3 ~/skills/imessage-assistant/scripts/get_imessage_convo.py --today

# Get service type for contact
python3 ~/skills/imessage-assistant/scripts/get_imessage_convo.py --service +1XXXXXXXXXX

# List group chats
python3 ~/skills/imessage-assistant/scripts/get_imessage_convo.py --groups
```

### Send Messages

```bash
# 1:1 (auto-detects service from history)
python3 ~/skills/imessage-assistant/scripts/send_message.py +1XXXXXXXXXX "message"

# Force specific service (for new contacts or after error=22)
python3 ~/skills/imessage-assistant/scripts/send_message.py --service RCS +1XXXXXXXXXX "message"
python3 ~/skills/imessage-assistant/scripts/send_message.py --service SMS +1XXXXXXXXXX "message"
python3 ~/skills/imessage-assistant/scripts/send_message.py --service iMessage +1XXXXXXXXXX "message"

# Group chat
python3 ~/skills/imessage-assistant/scripts/send_message.py --chat CHAT_ID "message"

# Lookup group chat details
python3 ~/skills/imessage-assistant/scripts/send_message.py --lookup CHAT_ID
```

**Note:** MCP `send_imessage` only works for iMessage. Use scripts for RCS/Android and group chats.

### Check Delivery Status

```bash
# All messages sent today
python3 ~/skills/imessage-assistant/scripts/sent_today.py

# Only failed/pending messages
python3 ~/skills/imessage-assistant/scripts/sent_today.py --failed
```

### CRM Daily Briefing

```bash
# Generate briefing to stdout
python3 ~/skills/imessage-assistant/scripts/crm_briefing.py

# Generate and save to Apple Notes (CRM Briefings folder)
python3 ~/skills/imessage-assistant/scripts/crm_briefing.py --note
```

Reads `references/contacts.md` for:
- **Promise**: What I owe them
- **Waiting**: What they owe me
- **Category**: Lead / Customer / Partner / Nurture

Outputs sections:
- 🔴 Promises to Keep
- 🟡 Their Turn (with cold warnings >7 days)
- 🟢 Nurture (no action)
- ⚠️ Don't Forget (reminders)

### Daily Message Audit

1. Run `get_imessage_convo.py --today`
2. Compare numbers against Quick Reference
3. For unknown numbers:
   - Check `references/spam_numbers.md` (ignore if spam)
   - Use MCP `search_contacts` by name if visual context available
   - Query recent messages for identity clues
4. Add confirmed contacts to `references/contacts.md`

---

## Composing Replies

### Context Gathering

**For casual contacts:** 15-25 recent messages sufficient

**For close friends/family:** Pull 100-200 messages to understand:
- Relationship depth and history
- Shared jokes, references, dreams
- Current life situation
- Communication style and tone

### Reply Drafting

1. Match their energy and style
2. Reference shared context naturally
3. For long friendships, acknowledge the bond
4. Include forward-looking elements (plans, dreams, business ideas)

---

## Pre-Send Verification (CRITICAL)

**Before sending to ANY contact, especially common names:**

1. Check last message date to verify recent activity
2. Review last 5-10 messages to confirm correct person
3. Multiple contacts same name? Pick most recent relevant conversation

---

## Error Handling

| Error | Cause | Fix |
|-------|-------|-----|
| `error=22` | Wrong service | Use `--service RCS` or `--service SMS` flag |
| `is_delivered=0` | Pending/failed | Check with `sent_today.py --failed` |
| osascript fails | Messages not running | Open Messages.app |
| Wrong contact | Multiple same name | Verify last message date |

---

## Agent-Friendly Contacts

These contacts know Scott uses AI agents and can receive messages directly FROM the agent:

| Contact | Style Notes |
|---------|-------------|
| Jeff Thompson | "Badass!" - loves it. Turing test jokes. Co-founder bond. |
| Jennifer Long | Plays along. Use "forewarn" = lookup/pre-qualify a contact. |
| Jamie Boutain | Bot detection jokes. "We won't know till the cutting starts." |

**When messaging as agent:**
- Identify as "Scott's AI" or "Claude"
- Reference that Scott asked you to reach out
- Joke about Eleven Labs voice clones
- Keep it playful

---

## Message Escaping

**Use double quotes for messages containing apostrophes:**
```bash
# WRONG - will fail
python3 send_message.py +1234567890 'Don\'t forget!'

# RIGHT
python3 send_message.py +1234567890 "Don't forget!"
```

---

## Sync with Square CRM & Contacts

When discovering customer info from iMessages, keep all 4 systems in sync:

```
iMessage → Apple Contacts → contacts.md → Square CRM
```

### Example: New Customer Discovery

**Scenario:** Customer messages with their name, and you discover it from the iMessage thread.

**Step 1: Update Apple Contacts (iPhone)**
```bash
# Scott's iMessage shows "Mike" + phone +13129143889
# But his last name is "Giba" (from company context)
python3 ~/skills/square-crm/scripts/sync_to_apple_contacts.py +13129143889 --last-name "Giba"
```

**Step 2: Update contacts.md (reference)**
```markdown
### Mike Giba (Richmond)
- **Phone**: +13129143889
- **Service**: RCS
- **Context**: Store operations, flea market
- **Source**: Discovered via iMessage + Square CRM
```

**Step 3: Sync to Square CRM**
```bash
# Using square-crm skill to update
python3 ~/skills/square-crm/scripts/parse_contacts.py --phone +13129143889
```

**Result:** All 4 systems updated, data flows in both directions

### Sync Scripts Available

See `~/skills/square-crm/scripts/` for:
- `sync_to_apple_contacts.py` - Update iPhone from Square discoveries
- `parse_contacts.py` - Export contacts.md for Square sync
- `lookup_customer.py` - Search Square by phone

Full documentation: `~/skills/square-crm/references/sync-to-contacts-guide.md`

---

## Spam Filter

Ignore patterns in `references/spam_numbers.md`:
- 800/855/888 toll-free with promotional content
- Short codes (5-6 digits) with URLs
- `wgames.app` links
- Banking app alerts (legitimate but automated)

