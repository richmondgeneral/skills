---
name: daily-briefing
description: Generate morning briefing with CRM status, promises, and action items. Use when user asks for daily briefing, morning briefing, CRM status, what they owe people, or who they're waiting on. Outputs to Apple Notes with rich formatting. Reads contacts-manager for promise/waiting fields.
metadata:
  version: "1.1"
  author: scottybe
  updated: "2025-12-21"
  changelog: |
    v1.1 - Anthropic skills update:
    - Added author and updated fields
---

# Daily Briefing

Generate consolidated morning briefings with CRM status, promises to keep, and pending items.

## Generate Briefing

```bash
# Output to terminal
python3 ~/.claude/skills/daily-briefing/scripts/crm_briefing.py

# Save to Apple Notes (CRM Briefings folder) with rich formatting
python3 ~/.claude/skills/daily-briefing/scripts/crm_briefing.py --note

# Force legacy mode (plain text, no formatting)
python3 ~/.claude/skills/daily-briefing/scripts/crm_briefing.py --legacy
```

## Output Sections

| Section | Meaning |
|---------|---------|
| 🔴 Promises to Keep | What I owe them (from Promise field) |
| 🟡 Their Turn | What they owe me (from Waiting field), with cold warnings >7 days |
| 🟢 Nurture | Relationship maintenance, no action needed |
| ⚠️ Don't Forget | Special reminders flagged in profiles |

## Data Source

Reads `~/.claude/skills/contacts-manager/references/contacts.md` for:
- **Promise**: What I owe them
- **Waiting**: What they owe me  
- **Category**: Lead / Customer / Partner / Nurture
- **Status**: Current state of engagement

Cross-references with Messages database (`~/Library/Messages/chat.db`) for:
- Last message date
- Whose turn it is (them or me)
- Cold contact detection (>7 days)

## Apple Notes Integration

The `--note` flag uses macOS 26+ markdown import for rich formatting:
- Tables render properly
- Headers, bold, emoji preserved
- Saves to iCloud → CRM Briefings folder
- Auto-cleans old daily briefings

**Requires:** System Events accessibility permission for UI automation.

## Future Enhancements

Planned additions to the daily briefing:
- Calendar: Today's events and meetings
- Messages: Unread/urgent message summary
- Weather: Local forecast
- Square: Daily sales summary
- Scheduled automation: 7am daily trigger
