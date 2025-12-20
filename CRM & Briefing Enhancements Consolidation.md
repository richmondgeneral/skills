# CRM & Briefing Enhancements Consolidation
## Problem Statement
Three remaining Linear backlog items \(TVM\-14, TVM\-15, TVM\-16\) all relate to customer engagement automation and reporting\. These can be consolidated into a unified enhancement that improves both CRM management and daily briefing workflows\.
## Current State
**Existing Systems:**
* `square-crm` skill: Bidirectional sync between contacts\.md ↔ Square CRM ↔ Apple Contacts
* `daily_briefing.py`: Unified briefing with iMessage activity, property alerts, CRM contact parsing
* `square_cache.sh`: MongoDB cache with 63 items, change tracking operational
* Reference files: contacts\.md with Richmond General customer profiles \(Promise/Waiting fields\)
**What Works:**
* Contact sync workflow: contacts\.md → Square → Apple Contacts
* Daily activity summaries with property keyword flagging
* Customer profile parsing with category/interest/status fields
**What's Missing \(from roadmap\.md:44 & backlog\):**
* Stale contact detection \(no activity 30\+ days\)
* Weekly summary briefing format
* Automated Square CRM sync scheduling
## Proposed Changes
### 1\. Stale Contact Detection \(TVM\-14\)
**Implementation:** Enhance `daily_briefing.py` to add customer engagement monitoring\.
**New function:** `get_stale_contacts(days_threshold=30)`
* Query chat\.db for last message per contact from contacts\.md
* Cross\-reference with customer category \(Leads, Active, VIP\)
* Flag contacts exceeding threshold with last interaction date
* Include in daily briefing output under "🔔 Engagement Alerts" section
**Output format:**
```warp-runnable-command
🔔 Engagement Alerts
⚠️  No contact in 30+ days:
   • Mike Giba (+1312...) - Last: Nov 20 - Category: Lead
   • Walid Bandar (+1312...) - Last: Nov 15 - Category: Customer
```
**Files to modify:**
* `skills/imessage-assistant/scripts/daily_briefing.py` \(~50 lines added\)
* Add `--engagement` flag for engagement\-only report
### 2\. Weekly Summary Format \(TVM\-15\)
**Implementation:** Add weekly aggregation mode to `daily_briefing.py`\.
**New flag:** `--weekly` with date range support
* Aggregate last 7 days of message activity
* Group by contact with total inbound/outbound counts
* Include property alerts from full week
* Show stale contacts \(using TVM\-14 function\)
* Add Square catalog changes summary \(via square\_cache\.sh changes\)
**Output format:**
```warp-runnable-command
📊 Weekly Summary (Dec 13-20, 2025)
📱 Message Activity (7 days)
   Sue Miller: 12 msgs (8 in, 4 out)
   Dawn: 5 msgs (3 in, 2 out)
   ...
🔔 Stale Contacts: 3 requiring follow-up
📦 Catalog Changes: 5 items updated, 2 new
```
**Files to modify:**
* `skills/imessage-assistant/scripts/daily_briefing.py` \(~80 lines\)
* Reuse existing query logic with date range params
* Integrate with `square_cache.sh changes --since` for catalog section
### 3\. Automated CRM Sync \(TVM\-16\)
**Implementation:** Create launchd plist for scheduled sync\.
**New script:** `~/skills/square-crm/scripts/auto_sync.sh`
* Wrapper that runs `parse_contacts.py` → Square API update workflow
* Logs to `~/skills/square-crm/logs/sync.log`
* Sends errors to daily briefing for manual review
* Tracks last sync timestamp in MongoDB `square_cache.sync_log`
**Launchd config:** `~/Library/LaunchAgents/com.richmondgeneral.square-crm-sync.plist`
* Schedule: Daily at 6:00 AM \(before briefing\)
* Only if MongoDB is running
* Retry on failure with exponential backoff
**Files to create:**
* `skills/square-crm/scripts/auto_sync.sh` \(~40 lines\)
* `skills/square-crm/scripts/install_launchd.sh` \(setup helper\)
* launchd plist file
**Files to modify:**
* `skills/imessage-assistant/scripts/daily_briefing.py` \- add "Last CRM sync" status line
* `skills/square-crm/SKILL.md` \- document automation setup
### 4\. Integration Points
**Unified workflow:**
1. 6:00 AM \- Auto CRM sync runs \(TVM\-16\)
2. 7:00 AM \- Daily briefing generates with stale contacts \(TVM\-14\)
3. Sunday 8:00 AM \- Weekly summary with full engagement report \(TVM\-15\)
**Dependencies:**
* MongoDB must be running \(already operational\)
* SQUARE\_TOKEN in environment \(already configured\)
* contacts\.md must be up\-to\-date \(manual curation\)
**Error handling:**
* If Square API fails, log and continue with cached data
* If chat\.db locked, retry with 5s delay
* All errors logged and surfaced in next briefing
## Success Criteria
* ✅ Stale contacts flagged automatically in daily briefing
* ✅ Weekly summary command generates 7\-day aggregated report
* ✅ CRM sync runs daily without manual intervention
* ✅ All logs accessible via standard paths
* ✅ Documentation updated with automation setup guide
* ✅ Tests added for stale contact detection logic
## Implementation Plan
1. **Phase 1:** Stale contact detection \(TVM\-14\)
    * Add function to daily\_briefing\.py
    * Test with chat\.db queries
    * Validate against known stale contacts
2. **Phase 2:** Weekly summary mode \(TVM\-15\)
    * Add \-\-weekly flag with date range logic
    * Integrate square\_cache\.sh changes output
    * Test with historical date ranges
3. **Phase 3:** Automated sync \(TVM\-16\)
    * Create auto\_sync\.sh wrapper
    * Build launchd plist with error handling
    * Install and validate scheduled execution
4. **Phase 4:** Documentation & cleanup
    * Update SKILL\.md files with new features
    * Add AUTOMATION\.md guide for launchd setup
    * Update Linear tickets and mark Done
## Risks & Mitigations
**Risk:** chat\.db locked during query \(Messages app open\)
**Mitigation:** Add retry logic with 5\-10s delay, fall back to "unavailable" status
**Risk:** Square API rate limiting with daily sync
**Mitigation:** Parse contacts\.py already batches requests, add 1s delay between creates
**Risk:** Stale contact false positives \(customer prefers email/phone\)
**Mitigation:** Flag as "no iMessage activity" rather than "inactive customer"
**Risk:** launchd job fails silently
**Mitigation:** Log all output, add health check to daily briefing status section