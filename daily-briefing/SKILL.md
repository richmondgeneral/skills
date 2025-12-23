---
name: daily-briefing
description: Generate morning briefing with personal contact status and CRM action items. Use when user asks for daily briefing, morning briefing, who needs a reply, what they owe people, who they're waiting on, or CRM status. Personal contacts first (family, close friends), then Richmond General CRM. Outputs to Apple Notes with rich formatting. NOT for sending messages—use imessage-core. NOT for contact lookup—use contacts-manager.
metadata:
  version: "2.0"
  author: scottybe
  updated: "2025-12-22"
---

# Daily Briefing

Unified morning briefing: personal contacts first, then business CRM.

## Generate Briefing

```bash
# Terminal output
uv run --project /Users/scottybe/.claude/skills \
    python /Users/scottybe/.claude/skills/daily-briefing/scripts/daily_briefing.py

# Save to Apple Notes (Daily Briefings folder)
uv run --project /Users/scottybe/.claude/skills \
    python /Users/scottybe/.claude/skills/daily-briefing/scripts/daily_briefing.py --note

# Debug mode
uv run --project /Users/scottybe/.claude/skills \
    python /Users/scottybe/.claude/skills/daily-briefing/scripts/daily_briefing.py --verbose
```

## Output Structure

```
# 📬 Daily Briefing — Monday, Dec 22, 2025

## 👥 PERSONAL
| Contact | | Turn | Last | Action |
|---------|--|------|------|--------|
| Dawn    | ✅ | them | 0d  | —      |
| Dad     | 🔴 | me   | 2d  | **reply needed** |

## 🏪 RICHMOND GENERAL CRM

### 🔴 Promises to Keep
| Contact | What I Owe | Days |

### 🟡 Their Turn  
| Contact | Waiting For | Days |

## ⚠️ DON'T FORGET
- Josh (White Dually): owes him one
```

## Status Indicators

**Personal contacts:**
| Emoji | Meaning |
|-------|---------|
| ✅ | Good — their turn, recent |
| 🟡 | My turn — reply soon |
| 🟠 | My turn — getting stale |
| 🔴 | My turn — reply needed (>3d) |
| 🔵 | Their turn — going cold (>7d) |

**CRM:**
- 🔴 Promises = what I owe them
- 🟡 Their Turn = waiting on them (⚠️ if >7 days)
- 🟢 Nurture = relationship maintenance

## Data Sources

- **Contacts**: `/Users/scottybe/.claude/skills/contacts-manager/references/contacts.md`
  - Core section → Personal contacts
  - Richmond General Customers → CRM contacts
- **Messages**: `/Users/scottybe/Library/Messages/chat.db` (one query pass for all)

## Scheduled Automation

Install launchd plist for 7am daily runs:

```bash
# Make wrapper script executable
chmod +x /Users/scottybe/.claude/skills/daily-briefing/scripts/run_briefing.sh

# Copy plist to LaunchAgents
cp /Users/scottybe/.claude/skills/daily-briefing/scripts/com.claude.dailybriefing.plist \
   /Users/scottybe/Library/LaunchAgents/

# Load the schedule
launchctl load /Users/scottybe/Library/LaunchAgents/com.claude.dailybriefing.plist

# Test immediate run
launchctl start com.claude.dailybriefing

# Check logs
cat /tmp/dailybriefing.log
cat /tmp/dailybriefing.err

# Unload if needed
launchctl unload /Users/scottybe/Library/LaunchAgents/com.claude.dailybriefing.plist
```

## Requirements

- macOS 26+ for rich Notes import
- System Events accessibility permission
- contacts-manager skill (for contacts.md)
- uv with shared environment at `/Users/scottybe/.claude/skills/`

## Troubleshooting

**Briefing empty?**
- Run with `--verbose` to see parsing
- Check contacts.md has `## Detailed Profiles - Core` and `## Detailed Profiles - Richmond General Customers` sections

**Notes not saving?**
- Grant System Events in Privacy & Security → Accessibility
- Check `/tmp/dailybriefing.err` for errors

**Scheduler not running?**
- Verify: `launchctl list | grep dailybriefing`
- Check logs in `/tmp/dailybriefing.log`
