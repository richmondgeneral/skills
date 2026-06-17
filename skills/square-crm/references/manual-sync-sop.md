# Manual Two-Way Sync SOP
## contacts.md ↔ Square CRM

**Version**: 1.0  
**Last Updated**: December 19, 2025  
**Frequency**: Daily or as-needed  
**Time Estimate**: 15-20 minutes per sync session  
**Risk Level**: Low (reversible, conflict detection included)

---

## Quick Reference

| What | Where | How Often |
|------|-------|-----------|
| Check for changes in contacts.md | `~/.claude/skills/contacts-manager/references/contacts.md` | Before syncing |
| Check for Square changes | [Square Dashboard](https://dashboard.squareup.com) → Customers | Before syncing |
| Document conflicts | `~/.claude/skills/square-crm/working/conflict_review_YYYYMMDD.md` | As found |
| Verify after sync | Both systems | After completing |

---

## Prerequisites

✅ You have:
- Access to Square Dashboard (credentials in 1Password)
- `contacts.md` open and accessible
- Git CLI installed (for commit/undo)
- 15-20 minutes of uninterrupted time

⚠️ Do NOT sync while:
- Square POS is actively processing transactions
- You're actively messaging customers
- Your internet connection is unstable

---

## Phase 1: Pre-Sync Preparation (5 minutes)

### Step 1.1: Open Both Systems

```bash
# Open contacts.md
open ~/.claude/skills/contacts-manager/references/contacts.md

# Open Square Dashboard in browser
open https://dashboard.squareup.com/login
```

### Step 1.2: Create Sync Session Log

Create a new file to track what you're syncing:

```bash
touch ~/.claude/skills/square-crm/working/sync_log_$(date +%Y%m%d).md
```

Edit this file and add:

```markdown
# Sync Session: December 19, 2025

**Start Time**: HH:MM  
**Syncer**: Scott  
**Status**: IN PROGRESS

## Changes to Process

### From contacts.md
- [ ] Customer A: Note change
- [ ] Customer B: Status update

### From Square
- [ ] Customer X: Staff note added
- [ ] Customer Y: Phone updated

## Conflicts Found
(none yet)

## Completed
(will fill in as we go)
```

### Step 1.3: Check What Changed

**In contacts.md:**
- Look for recent edits (compare to yesterday)
- Note any new customers, status changes, promises, waiting items

**In Square Dashboard:**
1. Go to **Customers**
2. Filter by **"Last modified in the last 24 hours"** (if available)
3. Or manually scan your customer list for updates

---

## Phase 2: Identify Changes (5-7 minutes)

### Change Types & How to Spot Them

#### Type A: Local Change (contacts.md only)

```diff
- Status: Pending
+ Status: Active — Ready for call

- Promise: Call next week
+ Promise: Call Mon Dec 23
```

**Action**: Push to Square

#### Type B: Remote Change (Square only)

In Square customer notes, you see something NEW that wasn't in contacts.md:

```
[Staff Note - 2025-12-19 14:30]
Called customer, ordered 3 vinyl records
```

**Action**: Pull back to contacts.md

#### Type C: Conflicting Change (both changed)

contacts.md says: "Status: Waiting for callback"  
Square says: "Status: Active — Spoke today"

**Action**: Detect conflict → Review → Resolve

---

## Phase 3: Sync Procedure (8-10 minutes)

### Pattern: Pull → Push → Verify

#### PULL: Bring Square Changes Into contacts.md

For each customer that changed in Square:

**Step 3.1a: Read the Square note**

Click customer → View details → Read full note

**Step 3.1b: Extract actionable info**

Staff notes typically contain:
- Phone corrections
- Payment/order info
- Customer feedback
- Activity timestamps

Example note in Square:
```
[Category] Customer
Interest: Vinyl records
Status: Active
Promise: Call with new arrivals
[Staff Note - 2025-12-19 14:30 by Mike]
Customer called, wants horror VHS. Has 300+ laserdiscs to trade.
Reference: imessage:+14148757568
Last Modified: 2025-12-19 14:30:15
```

**Step 3.1c: Update contacts.md**

Open contacts.md and find the matching customer section:

```markdown
### 414 Contact (GET NAME!)
- **Phone**: +14148757568
- **Service**: iMessage
- **Category**: Lead
- **Promise**: Bring horror VHS to trade
- **Waiting**: His name (Jen forewarning)
+ **Square Note**: Called — wants horror VHS, has 300+ laserdiscs for trade (Dec 19 2:30pm)
- **Status**: Trade TOMORROW 9:30am flea market
- **Last Contact**: Dec 19, 2025
```

**When adding Square notes:**
- Use format: `**Square Note (YYYY-MM-DD HH:mm by NAME)**: ...`
- Keep it brief (1-2 sentences)
- Include timestamp + who added it
- DON'T overwrite relationships/promises — add to them

---

#### PUSH: Send contacts.md Changes to Square

For each customer that changed in contacts.md:

**Step 3.2a: Identify the Square customer**

Use phone as lookup key:

```bash
# Use your lookup script (if available)
python3 ~/.claude/skills/square-crm/scripts/lookup_customer.py +13124483219

# Or manually search Square Dashboard
Square Dashboard → Customers → Search "+1312-448-3219"
```

**Step 3.2b: Map contacts.md fields to Square note**

Open Square customer details and find the **Note** field.

The note should follow this structure:

```
[Category]
Interest: New Wave records
Status: Visit scheduled Dec 28-30
Promise: Keep eye out for New Wave vinyl
Waiting: (none)
Last Contact: 2025-12-19
<Any staff notes from POS>
Source: imessage contact
Last Modified: 2025-12-19 11:45:00
```

**Step 3.2c: Update Square note**

1. Click **Edit** on the customer card
2. Find the **Note** field
3. Update with latest info from contacts.md
4. Keep the format consistent (structured sections)
5. Update "Last Modified" timestamp
6. Click **Save**

**Example before:**
```
Interest: New Wave records
Status: Pending
Promise: null
```

**Example after:**
```
Interest: New Wave records
Status: Visit scheduled Dec 28-30 with brother
Promise: Keep eye out for New Wave vinyl
Last Contact: 2025-12-19
```

---

### Handle Conflicts

If both systems changed, DON'T overwrite. Document it first.

**Step 3.3: Conflict Detection**

Compare timestamps:

```
contacts.md edit: Dec 19, 11:00 AM
Square change:    Dec 19, 02:30 PM

→ Square is more recent, but which is RIGHT?
```

**Step 3.3b: Log the conflict**

Create/update `~/.claude/skills/square-crm/working/conflict_review_20251219.md`:

```markdown
## Conflict #1: Walid Bandar (+13124483219)

### Field: Status

**contacts.md (Dec 19, 11:00 AM)**
```
Status: Visit scheduled Dec 28-30 with brother
```

**Square (Dec 19, 02:30 PM by Mike)**
```
Status: Active — Called today, confirmed visit
```

### Context
- Last sync: Dec 18 at 10:15 PM
- Only one change on each side
- Both changes are compatible (visit still happening)

### Decision: MERGE_MANUAL
```
Status: Visit scheduled Dec 28-30 with brother (confirmed Dec 19 call)
```
---
```

**Step 3.3c: Resolve conflict**

For each conflict, choose one:

1. **ACCEPT_LOCAL** (contacts.md is correct)
   - Use if contacts.md has fresher relationship context
   - Example: You just updated a promise, Square info is stale

2. **ACCEPT_REMOTE** (Square is correct)
   - Use if Square has fresher transaction data
   - Example: Staff just corrected a phone number at POS

3. **MERGE** (combine both)
   - Use if both are true and complementary
   - Example: "Waiting for callback (Staff note: called 2pm, will call back)")

Apply your decision to both systems.

---

## Phase 4: Verification (2-3 minutes)

### Check 4.1: Data Consistency

Pick 3 random customers and verify both systems match:

```bash
# For each customer:
# 1. Open contacts.md — note the key fields
# 2. Search Square Dashboard for that phone
# 3. Compare the note fields
# 4. They should align (allowing for Square staff notes)
```

### Check 4.2: No Data Loss

Look for:
- ❌ Phone numbers didn't get truncated
- ❌ Special characters (+ sign in phone) didn't disappear
- ❌ Promises/waiting items didn't vanish
- ❌ Timestamps are reasonable (not in future)

### Check 4.3: Audit Trail

Update your sync log:

```markdown
## Completed

**End Time**: HH:MM  
**Duration**: 18 minutes  
**Customers Synced**: 8  
**Conflicts**: 1 (Walid status merge)  
**Status**: ✅ COMPLETE

### Summary
- Pulled 2 Square staff notes into contacts.md
- Pushed 3 status updates to Square
- Resolved 1 conflict (merged both)
- Verified 3 sample records
```

---

## Common Scenarios

### Scenario 1: Customer Status Changed Locally

**You edited contacts.md:**
```diff
- Status: Pending
+ Status: Active — Ready to call
```

**What to do:**
1. Find that customer in Square
2. Open their note
3. Update the Status line
4. Save

✅ Done!

---

### Scenario 2: Staff Added a Note in Square

**Square note now shows:**
```
[Staff Note - Dec 19 2:15pm by Mike]
Customer called about laserdiscs. Wants to trade.
```

**What to do:**
1. Open contacts.md for that customer
2. Add below existing notes:
   ```
   **Square Note (2025-12-19 14:15 by Mike)**: Called about laserdiscs, interested in trade
   ```
3. Don't remove the original contacts.md context
4. Save

✅ Done!

---

### Scenario 3: Conflict — Both Systems Changed

**contacts.md (you this morning):**
```
Promise: Call Monday with new vinyl
```

**Square (staff this afternoon):**
```
Promise: Call confirmed for Tuesday
```

**What to do:**

1. Open `~/.claude/skills/square-crm/working/conflict_review_20251219.md`
2. Document both versions with timestamps
3. Think: "What's actually true?"
   - Did you make a promise in contacts.md?
   - Did staff confirm different date in Square?
   - Did customer specify a preference?
4. Choose resolution:
   - ACCEPT_LOCAL: Keep Monday
   - ACCEPT_REMOTE: Switch to Tuesday
   - MERGE: "Call Monday with new vinyl (staff confirmed Tuesday available)"
5. Apply to both systems
6. Mark conflict as resolved in the file

✅ Done!

---

### Scenario 4: New Customer in Square

**Square shows a customer not in contacts.md yet**

**What to do:**

1. Don't worry — Phase 1 sync only works one direction (contacts.md → Square)
2. New customers from Square should be manually added to contacts.md when you want to track them
3. For now, they stay in Square only

💡 **Note**: Phase 3 implementation will make this bidirectional

---

### Scenario 5: Phone Number Mismatch

**contacts.md:** +1 312-448-3219  
**Square:** (312) 448-3219

**What to do:**

These are the same! But formatting differs.

- Use normalized format in both: `+13124483219` (E.164)
- Update whichever system has sloppy formatting
- Script available: `python3 ~/.claude/skills/square-crm/scripts/lookup_customer.py +13124483219`

---

## After Each Sync

### Commit Changes

```bash
cd ~/skills

git add square-crm/working/sync_log_20251219.md
git add contacts-manager/references/contacts.md
git commit -m "Manual sync: Dec 19 - 8 customers synced, 1 conflict resolved

Co-Authored-By: Warp <agent@warp.dev>"
```

### Archive Completed Sync Log

```bash
# Move completed log to archive
mv ~/.claude/skills/square-crm/working/sync_log_20251219.md ~/.claude/skills/square-crm/working/archive/

# Or just leave it as-is for quick reference
```

### Quick Health Check

```bash
# Verify all customer records are still there
cd ~/skills

python3 square-crm/scripts/parse_contacts.py --validate
```

Expected output:
```
✅ 8 customers validated
✅ All phones in E.164 format
✅ Ready to sync
```

---

## Emergency: Undo a Sync

If something went wrong:

```bash
# See what you changed
git diff contacts-manager/references/contacts.md

# Revert the contacts.md file
git checkout contacts-manager/references/contacts.md

# Revert Square changes manually (Square doesn't have git)
# Go to each customer in Square and revert notes to previous state
# Or ask for a backup if you documented before syncing
```

---

## Troubleshooting

### Problem: Phone number didn't match between systems

**Solution:**
- Normalize both to E.164 format: `+1 + [area code] + [number]`
- Example: (312) 448-3219 → +13124483219
- Use: `python3 ~/.claude/skills/square-crm/scripts/lookup_customer.py [phone]`

---

### Problem: Can't find customer in Square

**Solution:**
1. Try different phone format (with/without dashes)
2. Try their name (search by name instead)
3. Check if they were synced already (look for "imessage:" reference in notes)
4. If still not found, this customer doesn't exist in Square yet

---

### Problem: Conflict — Can't decide which version is right

**Solution:**
1. Check your chat history (iMessage) — who contacted whom last?
2. Check Square transaction history (when did staff add the note?)
3. If still unclear, go with **MERGE** strategy
4. Mark as "MANUAL_REVIEW_NEEDED" and come back to it later

---

### Problem: Accidentally overwrote important data

**Solution:**

Immediately:
```bash
# See what you changed in the last commit
git show HEAD

# Revert if possible
git revert HEAD

# Or restore from before
git checkout HEAD~1 -- contacts-manager/references/contacts.md
```

Then:
1. Check what was lost
2. Manually re-add from backup or memory
3. Commit the fix

---

## When to Do Manual Syncs

### Daily Workflow
- **Morning**: Scan for any overnight changes (Square staff notes)
- **After customer calls/messages**: Update promises/status in contacts.md, push to Square
- **Before reaching out**: Check Square for any staff notes

### Recommended Schedule
- **Quick check**: Every morning (2-3 min)
- **Full sync**: Every 2-3 days (15-20 min)
- **Conflict review**: As conflicts arise

### High-Priority Times
- Before customer visits
- After major staff updates
- Weekly close-out (Friday end of day)

---

## Best Practices

✅ **DO:**
- Keep phone numbers in E.164 format (`+1...`)
- Use timestamps when adding Square notes to contacts.md
- Document conflicts before resolving
- Commit after each sync
- Add context to promises ("when" they should happen)

❌ **DON'T:**
- Sync while Square POS is processing
- Delete old notes — just add new ones with timestamps
- Change customer names without verifying in Square
- Leave conflicts unresolved for more than a few hours
- Sync during active customer conversations

---

## Reference Data Structures

### contacts.md Customer Format

```markdown
### Name (Descriptor)
- **Phone**: +13124483219
- **Service**: iMessage (or SMS, RCS, call)
- **Category**: Customer (or Lead, Partner, Nurture)
- **Promise**: What you promised to do
- **Waiting**: What you're waiting from them for
- **Interest**: What they're interested in
- **Status**: Current relationship status
- **Last Contact**: YYYY-MM-DD
- **Note**: Additional context
- **Square Note**: Recent staff updates (with timestamp)
```

### Square Note Format

```
[Category]
Interest: [what they want]
Status: [current status]
Promise: [what you promised]
Waiting: [what you're waiting for]
Last Contact: YYYY-MM-DD

[Staff Note - YYYY-MM-DD HH:mm by NAME]
[Description of interaction]

Source: imessage contact
Last Modified: 2025-12-19 11:45:00
```

---

## Tools Available

```bash
# Validate all customers before syncing
python3 ~/.claude/skills/square-crm/scripts/parse_contacts.py --validate

# Look up a customer by phone
python3 ~/.claude/skills/square-crm/scripts/lookup_customer.py +13124483219

# View current sync state
cat ~/.claude/skills/square-crm/working/sync_log_*.md

# Review conflicts
cat ~/.claude/skills/square-crm/working/conflict_review_*.md
```

---

## Key Contacts

- **Square Dashboard**: https://dashboard.squareup.com
- **Square API Docs**: https://developer.squareup.com/reference/square/v2026-04-21
- **contacts.md**: `~/.claude/skills/contacts-manager/references/contacts.md`
- **Sync working directory**: `~/.claude/skills/square-crm/working/`

---

## Sign-Off

After completing a sync:

```markdown
**Syncer**: Scott  
**Date**: YYYY-MM-DD  
**Time**: HH:MM  
**Duration**: XX minutes  
**Customers Synced**: X  
**Conflicts**: X (resolved/unresolved)  
**Status**: ✅ COMPLETE
```

---

**Next Step**: When ready for automation, reference `bidirectional-sync-design.md` for Phase 3 implementation roadmap.
