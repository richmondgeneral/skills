# CRM & Briefing Enhancements - Quick Start

Get started with stale contact detection, weekly summaries, and automated CRM sync in under 5 minutes.

## Prerequisites Check

```bash
# Verify MongoDB is running
pgrep mongod && echo "✅ MongoDB running" || echo "❌ Start MongoDB: brew services start mongodb-community@8.0"

# Verify SQUARE_TOKEN is set
[ -n "$SQUARE_TOKEN" ] && echo "✅ SQUARE_TOKEN set" || echo "❌ Add to ~/.zshrc: export SQUARE_TOKEN='your_token'"

# Verify contacts.md exists
[ -f ~/skills/imessage-assistant/references/contacts.md ] && echo "✅ contacts.md found" || echo "❌ Create contacts.md"
```

## 5-Minute Quick Start

### 1. Test Engagement Detection (30 seconds)

```bash
# Find contacts with no activity in 30+ days
python3 ~/skills/imessage-assistant/scripts/daily_briefing.py --engagement

# Try shorter threshold (7 days)
python3 ~/skills/imessage-assistant/scripts/daily_briefing.py --engagement --days 7
```

**Expected Output:**
```
🔔 Customer Engagement Report
Threshold: 30 days without iMessage activity
Found 1 contacts requiring follow-up:
- Pete (eBay Reseller) | Partner | 2025-12-06 | 13d | Them
```

### 2. Generate Weekly Summary (1 minute)

```bash
# View last 7 days of activity
python3 ~/skills/imessage-assistant/scripts/daily_briefing.py --weekly
```

**Expected Output:**
```
📊 Weekly Summary
Dec 13–Dec 19, 2025

Message Activity (7 days):
- Mike Giba: 71 msgs (36 in, 35 out)
- Dawn: 62 msgs (39 in, 23 out)
Total conversations: 34

Stale Contacts: 1 requiring follow-up
Catalog Changes: 126 items updated
```

### 3. Test Auto Sync (30 seconds)

```bash
# Dry-run to verify setup
~/skills/square-crm/scripts/auto_sync.sh --dry-run

# Check system status
~/skills/square-crm/scripts/install_launchd.sh status
```

**Expected Output:**
```
2025-12-20 06:00:00 [INFO] Starting CRM sync (dry-run)
2025-12-20 06:00:00 [INFO] Parsed 8 contacts from contacts.md
2025-12-20 06:00:00 [INFO] Dry-run complete - no changes made
```

### 4. (Optional) Install Daily Automation (2 minutes)

```bash
cd ~/skills/square-crm/scripts

# Install launchd job for 6:00 AM daily sync
./install_launchd.sh install
```

**Expected Output:**
```
📦 Installing CRM sync launchd job...
✅ Copied plist to ~/Library/LaunchAgents/...
✅ Loaded launchd job: com.richmondgeneral.square-crm-sync
🕐 Next run: Tomorrow at 6:00 AM
```

### 5. Save Briefings to Apple Notes (30 seconds)

```bash
# Daily briefing with engagement alerts
python3 ~/skills/imessage-assistant/scripts/daily_briefing.py --note

# Weekly summary
python3 ~/skills/imessage-assistant/scripts/daily_briefing.py --weekly --note

# Engagement report only
python3 ~/skills/imessage-assistant/scripts/daily_briefing.py --engagement --note
```

## Daily Usage

### Morning Routine (7:00 AM)

```bash
# Generate today's briefing
python3 ~/skills/imessage-assistant/scripts/daily_briefing.py --note

# Check if any contacts need follow-up
python3 ~/skills/imessage-assistant/scripts/daily_briefing.py --engagement --days 7
```

### Sunday Morning (8:00 AM)

```bash
# Generate weekly recap
python3 ~/skills/imessage-assistant/scripts/daily_briefing.py --weekly --note
```

## Troubleshooting

### "No module named 'pymongo'"
```bash
pip3 install pymongo requests Pillow
```

### "MongoDB not running"
```bash
brew services start mongodb-community@8.0
```

### "SQUARE_TOKEN not set"
```bash
echo 'export SQUARE_TOKEN="your_token_here"' >> ~/.zshrc
source ~/.zshrc
```

### "No contacts found"
Verify contacts.md has Richmond General Customers section:
```bash
grep "Richmond General Customers" ~/skills/imessage-assistant/references/contacts.md
```

## Next Steps

**Want more details?**
- Full documentation: `~/skills/AUTOMATION.md`
- Stress test results: `~/skills/STRESS_TEST_REPORT.md`
- GitHub issues: #1 (stale contacts), #2 (weekly), #3 (auto sync)
- Linear tickets: TVM-14, TVM-15, TVM-16

**Common Workflows:**
1. **Daily Briefing**: Check today's messages, CRM promises, engagement alerts
2. **Weekly Review**: Analyze conversation patterns, identify cold leads
3. **Monthly Cleanup**: Review stale contacts, update categories, sync to Square

**Advanced Features:**
- Custom engagement thresholds: `--days N`
- Historical summaries: `--date YYYY-MM-DD`
- CRM-only mode: `--crm`
- Dry-run testing: `--dry-run`

## Success Indicators

✅ Engagement reports show relevant contacts  
✅ Weekly summaries include catalog changes  
✅ Auto sync logs appear in `~/skills/square-crm/logs/sync.log`  
✅ Daily briefings saved to Apple Notes  
✅ MongoDB shows sync_log entries  

## Support

**Known Issues:**
- Invalid date format causes traceback (use YYYY-MM-DD)

**Performance:**
- Engagement reports: < 1 second
- Weekly summaries: ~2 seconds
- Auto sync: < 1 second

**Last Updated:** December 20, 2025  
**Version:** 1.0  
**Status:** Production Ready ✅
