# Richmond General Automation Guide

Comprehensive guide for automating customer engagement tracking, weekly briefings, and CRM sync.

## Overview

Three integrated automation systems:
1. **Stale Contact Detection** - Flag customers with 30+ days of no iMessage activity
2. **Weekly Summary Briefings** - 7-day aggregated reports with catalog changes
3. **Automated CRM Sync** - Daily sync of contacts.md to Square CRM (6:00 AM)

## Prerequisites

### Required
- MongoDB running: `brew services start mongodb-community@8.0`
- SQUARE_TOKEN in `~/.zshrc`: `export SQUARE_TOKEN="your_token"`
- contacts.md maintained at `~/.claude/skills/imessage-assistant/references/contacts.md`

### Optional
- Apple Notes for rich briefing formatting (macOS 26+)
- jq for JSON parsing: `brew install jq`

## 1. Stale Contact Detection (TVM-14)

Automatically identifies customers with no recent iMessage activity.

### Usage

```bash
# Standalone engagement report (30-day threshold)
python3 ~/.claude/skills/imessage-assistant/scripts/daily_briefing.py --engagement

# Custom threshold (45 days)
python3 ~/.claude/skills/imessage-assistant/scripts/daily_briefing.py --engagement --days 45

# Save to Apple Notes
python3 ~/.claude/skills/imessage-assistant/scripts/daily_briefing.py --engagement --note
```

### Output Format

```
# 🔔 Customer Engagement Report

**Threshold:** 30 days without iMessage activity

**Found 3 contacts requiring follow-up:**

| Contact | Category | Last Activity | Days | Whose Turn |
|---------|----------|---------------|------|------------|
| Pete (eBay Reseller) | Partner | 2025-12-06 | 13d | Them |
| Walid Bandar | Customer | 2025-11-15 | 34d | Us |
| Mike Giba | Lead | 2025-10-20 | 60d | Them |
```

### Integration

Stale contacts automatically appear in:
- Daily briefings (full mode)
- Weekly summaries (top 5 most stale)

Contacts in "Nurture" category are skipped (low engagement expected).

## 2. Weekly Summary Briefings (TVM-15)

7-day aggregated view of message activity, stale contacts, and catalog changes.

### Usage

```bash
# Current week summary
python3 ~/.claude/skills/imessage-assistant/scripts/daily_briefing.py --weekly

# Historical week (ending on specified date)
python3 ~/.claude/skills/imessage-assistant/scripts/daily_briefing.py --weekly --date 2025-12-15

# Save to Apple Notes
python3 ~/.claude/skills/imessage-assistant/scripts/daily_briefing.py --weekly --note
```

### Output Format

```
# 📊 Weekly Summary

**Dec 13–Dec 19, 2025**

## 📱 Message Activity (7 days)

| Contact | In | Out | Total |
|---------|---:|----:|------:|
| Mike Giba | 36 | 35 | 71 |
| Dawn | 39 | 23 | 62 |
| Jeff Thompson | 18 | 10 | 28 |
...

*Total conversations: 34*

## 🔔 Stale Contacts

⚠️ 1 contacts requiring follow-up (30+ days):
- **Pete (eBay Reseller)** (Partner) - 13d

## 📦 Square Catalog Changes

126 items updated
```

### Data Sources

- **Message Activity**: iMessage chat.db (7-day aggregation)
- **Stale Contacts**: Phase 1 detection logic
- **Catalog Changes**: `~/Workspace/square-tools/bin/square_cache.sh changes --since START_DATE`

### Recommended Schedule

Run weekly summaries on Sunday mornings:

```bash
# Add to crontab or create launchd job
0 8 * * 0 python3 ~/.claude/skills/imessage-assistant/scripts/daily_briefing.py --weekly --note
```

## 3. Automated CRM Sync (TVM-16)

Daily scheduled sync of contacts.md to Square CRM via launchd.

### Installation

```bash
cd ~/.claude/skills/square-crm/scripts

# Check prerequisites
./install_launchd.sh status

# Install and load job
./install_launchd.sh install
```

Expected output:
```
📦 Installing CRM sync launchd job...
✅ Copied plist to ~/Library/LaunchAgents/com.richmondgeneral.square-crm-sync.plist
✅ Loaded launchd job: com.richmondgeneral.square-crm-sync

🕐 Next run: Tomorrow at 6:00 AM
```

### Manual Testing

```bash
# Dry-run (no changes)
~/.claude/skills/square-crm/scripts/auto_sync.sh --dry-run

# Full sync (for testing)
~/.claude/skills/square-crm/scripts/auto_sync.sh
```

### Monitoring

```bash
# Check sync status
~/.claude/skills/square-crm/scripts/install_launchd.sh status

# View sync logs
tail -f ~/.claude/skills/square-crm/logs/sync.log

# Check launchd output
tail -f ~/.claude/skills/square-crm/logs/launchd.out.log
tail -f ~/.claude/skills/square-crm/logs/launchd.err.log
```

### Sync Schedule

- **Time**: Daily at 6:00 AM
- **Duration**: ~10-30 seconds (depending on contact count)
- **Prerequisites checked**: MongoDB running, SQUARE_TOKEN set

### MongoDB Tracking

Sync operations logged to `square_cache.sync_log` collection:

```javascript
{
  timestamp: ISODate("2025-12-20T06:00:00Z"),
  sync_type: "crm_contacts",
  contact_count: 8,
  status: "success"
}
```

### Uninstalling

```bash
~/.claude/skills/square-crm/scripts/install_launchd.sh uninstall
```

## Integrated Workflow

Daily automation flow:

```
6:00 AM  →  CRM Sync (auto_sync.sh via launchd)
              ├─ Parse contacts.md
              ├─ Log to MongoDB
              └─ Update Square CRM

7:00 AM  →  Manual: Generate daily briefing
              python3 daily_briefing.py --note
              ├─ Today's messages
              ├─ Property alerts
              ├─ CRM promises/waiting
              └─ Engagement alerts (30+ days)

Sunday 8:00 AM  →  Manual/Scheduled: Generate weekly summary
                      python3 daily_briefing.py --weekly --note
                      ├─ 7-day message aggregation
                      ├─ Top 5 stale contacts
                      └─ Catalog changes from square_cache
```

## Troubleshooting

### Stale Contacts Not Showing

**Issue**: Engagement report shows "All contacts active"

**Solutions**:
1. Lower threshold: `--days 7` instead of default 30
2. Check contacts.md has phone numbers in `+1XXXXXXXXXX` format
3. Verify chat.db accessible: `ls -la ~/Library/Messages/chat.db`

### Weekly Summary Missing Catalog Changes

**Issue**: Shows "Cache unavailable" or "N/A"

**Solutions**:
1. Ensure MongoDB running: `pgrep mongod`
2. Run sync: `~/Workspace/square-tools/bin/square_cache.sh sync`
3. Check date range: `square_cache.sh changes --since 2025-12-13`

### Auto Sync Failing

**Issue**: Launchd job not running or errors in log

**Solutions**:
1. Check status: `install_launchd.sh status`
2. Verify SQUARE_TOKEN in `~/.zshrc` (not just current shell)
3. Test manually: `auto_sync.sh --dry-run`
4. Check launchd logs: `~/.claude/skills/square-crm/logs/launchd.err.log`

### Apple Notes Import Failing

**Issue**: Briefing doesn't save to Notes

**Solutions**:
1. Grant System Events accessibility permissions
2. Use legacy mode (automatic fallback)
3. Check folder exists: Notes → iCloud → "Daily Briefings"

## Advanced Configuration

### Custom Sync Times

Edit `~/.claude/skills/square-crm/scripts/com.richmondgeneral.square-crm-sync.plist`:

```xml
<key>StartCalendarInterval</key>
<dict>
    <key>Hour</key>
    <integer>6</integer>  <!-- Change to desired hour (0-23) -->
    <key>Minute</key>
    <integer>0</integer>
</dict>
```

Then reload:
```bash
launchctl unload ~/Library/LaunchAgents/com.richmondgeneral.square-crm-sync.plist
launchctl load ~/Library/LaunchAgents/com.richmondgeneral.square-crm-sync.plist
```

### Multiple Weekly Summaries

Generate summaries for different time ranges:

```bash
# Last 7 days
python3 daily_briefing.py --weekly

# Previous week
python3 daily_briefing.py --weekly --date 2025-12-15

# Custom range (via date as end of 7-day window)
python3 daily_briefing.py --weekly --date 2025-11-30
```

### Engagement Thresholds

Adjust based on customer category expectations:
- **Leads**: 7 days (active prospecting)
- **Customers**: 30 days (regular business)
- **Partners**: 60 days (ongoing relationships)
- **Nurture**: Excluded from reports

## Related Documentation

- **daily_briefing.py**: `~/.claude/skills/imessage-assistant/scripts/daily_briefing.py` (inline docs)
- **square-crm skill**: `~/.claude/skills/square-crm/SKILL.md`
- **square-cache**: `~/Workspace/square-tools/README.md`
- **Linear tickets**: TVM-14 (engagement), TVM-15 (weekly), TVM-16 (automation)

---

**Version**: 1.0  
**Last Updated**: December 2025  
**Maintained by**: Richmond General
