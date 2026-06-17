# Two-Way Sync Design: contacts.md ↔ Square CRM

**Status**: Design Phase (Phase 3 - Future Implementation)  
**Last Updated**: December 19, 2025  
**Complexity Level**: High (requires conflict resolution, timestamp tracking)

---

## Executive Summary

Enable bidirectional synchronization between `contacts.md` (source of truth for relationship context) and Square CRM (source of truth for transaction data). This allows:

1. **Local editing** of relationship notes → syncs to Square
2. **Square POS updates** (new phone, notes from staff) → syncs to contacts.md
3. **Sales data** from Square → enriches contacts.md with purchase history
4. **Conflict detection** → flags inconsistencies for manual resolution

---

## Current State (Phase 1: One-way)

```
contacts.md  →→→  parse_contacts.py  →→→  Square CRM
 (source)          (transform)             (destination)
                                           ↓ (dead end)
```

**Limitations:**
- Changes in Square stay in Square
- Staff notes at POS don't flow back
- No purchase history in contacts.md
- Manual reconciliation required

---

## Proposed Two-Way Flow (Phase 3)

```
     contacts.md                           Square CRM
   (structured)                          (transactional)
        ↓                                      ↓
   [timestamp]                            [last_modified]
        ↓                                      ↓
   [sync_state]  ←→  CONFLICT DETECTOR  ←→  [sync_state]
        ↓                                      ↓
   [audit_log]  ←→  MERGE ENGINE        ←→  [audit_log]
```

---

## Core Challenges & Solutions

### Challenge 1: Which System Is Source of Truth?

**Problem**: contacts.md and Square have different strengths
- contacts.md: Relationship context (Promise, Waiting, Interest)
- Square: Transaction truth (confirmed phone, staff notes, payment history)

**Solution: Hybrid Authority Model**

| Data Type | Source | Authority |
|-----------|--------|-----------|
| **Core Identity** | Either (with linking) | Unified by phone + reference_id |
| **Relationship Context** | contacts.md | contacts.md (primary) |
| **Transaction Data** | Square | Square (immutable) |
| **Staff Notes** | Square | Merge with contacts.md notes |
| **Contact Info** | Both | Last-write-wins + conflict flag |
| **Purchase History** | Square | One-way → contacts.md |

### Challenge 2: Data Format Mismatch

**Problem**: Different structures
```
contacts.md structure (Richmond General Customers section):
  - **Phone**: +1234567890
  - **Category**: Customer
  - **Interest**: New Wave records
  - **Status**: Active
  - **Promise**: Call next week
  - **Waiting**: Price estimates
  - **Note**: Additional context
  - **Last Contact**: 2025-12-19

Square structure (customer.note field):
  [Category]
  Interest: New Wave records
  Status: Active
  Promise: Call next week
  Waiting: Price estimates
  <Staff notes from POS>
  Source: iMessage contact
  Last Modified: 2025-12-19 14:30:15
```

**Solution: Bidirectional Parsers**

```python
# contacts.md → Square payload
struct ContactsEntry:
  phone: str              # Unique identifier
  category: str           # Enum: Customer, Lead, Partner, Nurture
  interest: str           # Free text
  status: str             # Free text
  promise: str            # Free text
  waiting: str            # Free text
  notes: List[str]        # Array of notes
  last_contact: datetime  # When last contacted
  last_synced: datetime   # When last synced to Square
  sync_status: str        # "synced", "pending", "conflict"

# Square → contacts.md reverse parser
struct SquareCustomer:
  reference_id: str                       # Link back: "imessage:+1234567890"
  given_name + family_name: str           # Name
  phone_number: str                       # Unique identifier
  note: str                               # Parsed for structured fields
  updated_at: datetime                    # Last modified in Square
  metadata: {
    last_staff_note: str
    last_staff_note_timestamp: datetime
    contact_source: "imessage" | "poshmark" | "...", etc.
  }
```

### Challenge 3: Conflict Detection & Resolution

**Problem**: Both systems modified independently → conflicts

**Example Conflict:**
```
contacts.md:  Status: "Waiting for call back"  (edited 2025-12-19 09:00)
Square:       Status: "Active"                 (updated 2025-12-19 14:30 by staff)

Question: Which is correct? Did the customer call back? Or did staff mistype?
```

**Solution: Timestamp-Based Conflict Detection + Manual Review Queue**

```
CONFLICT RESOLUTION STRATEGY

1. DETECTION (automatic)
   If (local_timestamp > remote_timestamp) AND (local_value ≠ remote_value):
     → CONFLICT: Log both versions, flag for review

2. AUTO-RESOLVE (when safe)
   - If only one system changed: Accept the change
   - If both changed to same value: No conflict
   - If both systems agree: No conflict
   - Otherwise: Flag for manual review

3. MANUAL REVIEW QUEUE
   Generate: conflict_review_YYYYmmdd.md
   
   Format:
   ```
   ## Conflict: Walid Bandar (+13124483219)
   
   ### Field: Status
   - contacts.md (2025-12-19 09:00): "Waiting for call back"
   - Square      (2025-12-19 14:30): "Active"
   
   ### Context:
   - Last sync: 2025-12-18 22:15
   - Who changed in Square: staff (POS entry)
   - Type: Metadata field (likely safe to merge)
   
   ### Recommendation: [ACCEPT_LOCAL | ACCEPT_REMOTE | MERGE_MANUAL]
   
   ---
   ```

4. MERGE STRATEGIES
   - ACCEPT_LOCAL: Keep contacts.md version (relationship truth)
   - ACCEPT_REMOTE: Keep Square version (transaction truth)
   - MERGE: Combine both with notes
     Status: "Waiting for call back (Updated: now Active per Square)"
```

---

## Implementation Architecture

### Phase 3a: Data Tracking Layer (Prerequisites)

Add tracking to both systems:

**contacts.md additions:**
```yaml
---
last_synced: 2025-12-19T19:05:00Z
sync_source: "imessage:+1234567890"
sync_status: "synced"  # synced | pending | conflict
sync_version: 1
---
```

**Square metadata (via custom fields if available, or note footer):**
```
[Customer]
Interest: New Wave records
Status: Active
...

---SYNC METADATA---
imessage_synced_at: 2025-12-19T19:05:00Z
sync_version: 1
conflict_flags: []
```

### Phase 3b: Sync Engine Script

**New script: `sync_bidirectional.py`**

```python
class BidirectionalSyncEngine:
    
    def __init__(self):
        self.conflict_log = []
        self.sync_log = []
    
    def detect_changes(self):
        """Compare local vs remote timestamps"""
        # 1. Read contacts.md with timestamps
        # 2. Query Square customer.updated_at
        # 3. Compare: which changed since last sync?
    
    def fetch_from_square(self):
        """Pull updated customers from Square"""
        # Query API: customers where updated_at > last_sync
        # Returns list of changed customer objects
    
    def fetch_from_contacts(self):
        """Read contacts.md changes"""
        # Parse contacts.md, compare to last_synced field
        # Returns list of changed contact objects
    
    def detect_conflicts(self, local_change, remote_change):
        """Find conflicts between systems"""
        # If both changed same field to different values → conflict
        # Otherwise → safe to merge
    
    def auto_resolve_conflicts(self, conflicts):
        """Apply auto-resolution rules"""
        # One-way-wins: accept if only one system changed
        # Timestamp-wins: last-write-wins for overrides
        # Immutable wins: never override transaction data
    
    def create_conflict_review_queue(self, conflicts):
        """Generate conflict_review_YYYYmmdd.md"""
        # Write unresolved conflicts to file
        # User reviews and marks resolution manually
    
    def merge_resolved(self, conflicts, resolutions):
        """Apply user decisions"""
        # Update both systems with resolved values
        # Log decisions for audit trail
    
    def push_to_square(self, changes):
        """Upload contacts.md changes to Square"""
        # API calls: customers.update() for each change
        # Update Square notes with new metadata
    
    def push_to_contacts(self, changes):
        """Write Square changes back to contacts.md"""
        # Parse Square notes
        # Update contact entry in contacts.md
        # Preserve manual edits while adding transaction data
    
    def generate_sync_report(self):
        """Create audit trail"""
        # What synced?
        # What conflicted?
        # What was resolved?
        # Timestamp & version for each
```

**Usage:**
```bash
# Full bidirectional sync
python3 scripts/sync_bidirectional.py

# Show conflicts only (don't auto-resolve)
python3 scripts/sync_bidirectional.py --conflicts-only

# Apply resolutions from review file
python3 scripts/sync_bidirectional.py --resolve conflict_review_20251219.md

# Dry run (show what would change)
python3 scripts/sync_bidirectional.py --dry-run
```

---

## Data Flow Examples

### Example 1: Local Edit → Square Sync

**Step 1: User edits contacts.md**
```md
### Walid Bandar
- **Phone**: +13124483219
- **Status**: Visit scheduled Dec 28-30 with brother ← EDITED
- **Promise**: Call before visit ← EDITED
```

**Step 2: sync_bidirectional.py detects changes**
```
Local timestamp: 2025-12-19 19:05:00
Remote timestamp: 2025-12-18 22:15:00
→ Local is newer → Safe to push
```

**Step 3: Generates Square update payload**
```python
{
  "customer_id": "JDKYHBWT1D4F8MFH63DBMEN8Y4",
  "note": "[Customer]
Interest: New Wave records
Status: Visit scheduled Dec 28-30 with brother
Promise: Call before visit
Waiting: null
Source: iMessage contact
---SYNC METADATA---
imessage_synced_at: 2025-12-19T19:05:00Z
sync_version: 2"
}
```

**Step 4: Pushes to Square via API**
```
mcp_square_api:make_api_request
  service: "customers"
  method: "update"
  request: {customer_id: "...", note: "..."}
```

**Step 5: Updates contacts.md tracking**
```md
### Walid Bandar
- **Phone**: +13124483219
- **Status**: Visit scheduled Dec 28-30 with brother
- **Promise**: Call before visit

<!-- metadata -->
last_synced: 2025-12-19T19:05:00Z
sync_status: synced
sync_version: 2
```

---

### Example 2: Square Edit → contacts.md Sync

**Step 1: Staff edits customer in Square POS**
```
User: "John (cashier)"
Time: 2025-12-19 14:30:00
Change: "Customer called - confirmed next order for Jan 5"
```

**Step 2: sync_bidirectional.py queries Square**
```
GET /customers?updated_at_begin=2025-12-19T14:00:00Z
→ Returns: Walid's customer object with new note
```

**Step 3: Parses Square note**
```
[Customer]
Interest: New Wave records
Status: Visit scheduled Dec 28-30 with brother
Promise: Call before visit
Note: Customer called - confirmed next order for Jan 5  ← NEW from POS
```

**Step 4: Checks for conflicts**
```
contacts.md timestamp: 2025-12-19 19:05:00
Square timestamp:      2025-12-19 14:30:00
→ contacts.md is newer for Status, but Square added new note
→ Safe to merge: Add POS note without overwriting Status
```

**Step 5: Merges into contacts.md**
```md
### Walid Bandar
- **Phone**: +13124483219
- **Status**: Visit scheduled Dec 28-30 with brother
- **Promise**: Call before visit
- **Note**: Customer called - confirmed next order for Jan 5
  Source: Square POS (staff: John, 2025-12-19 14:30)

<!-- metadata -->
last_synced: 2025-12-19T19:35:00Z
sync_status: synced
sync_version: 3
```

---

### Example 3: CONFLICT - Both Systems Edited

**Step 1: Simultaneous edits**
```
contacts.md (user edit 09:00):
  Status: "Waiting for call back"

Square (staff edit 14:30):
  Note: "Status: Active (customer confirmed available)"
```

**Step 2: Conflict detection**
```
Field: Status
Local (contacts.md):  "Waiting for call back" [2025-12-19 09:00]
Remote (Square):      "Active"               [2025-12-19 14:30]
→ CONFLICT: Both changed, different values
```

**Step 3: Generate review queue**
```md
## Conflict: Walid Bandar (+13124483219)

### Field: Status

**contacts.md (2025-12-19 09:00)**
Value: "Waiting for call back"
Context: User manually edited

**Square (2025-12-19 14:30)**
Value: "Active"
Context: POS staff entry (John)
Note: "customer confirmed available"

### Analysis:
- Type: Relationship status (both systems care)
- Recency: Square is newer (5+ hours later)
- Confidence: Square has direct customer confirmation
- Risk: Overwriting local intent with Square reality

### Options:
1. ACCEPT_REMOTE: Update contacts.md to "Active" (Square sees reality)
2. ACCEPT_LOCAL: Keep "Waiting for call back" (local context important)
3. MERGE: "Active (called 2025-12-19 14:30 per Square POS)"

### Recommendation: MERGE
Rationale: Preserve both pieces of info - status updated AND timestamp

---
```

**Step 4: User reviews and resolves**
```
# Edit review file to mark resolution:
### Options:
1. ACCEPT_REMOTE
2. ACCEPT_LOCAL
3. MERGE: "Active (confirmed available 2025-12-19 14:30 per POS)"

[User marks: 3 ← MERGE]
```

**Step 5: Engine applies resolution**
```md
### Walid Bandar
- **Status**: Active (confirmed available 2025-12-19 14:30 per POS)

<!-- metadata -->
last_synced: 2025-12-19T19:45:00Z
sync_status: synced
sync_version: 4
conflicts_resolved: 1
```

---

## Implementation Roadmap

### Phase 3a: Foundation (1-2 weeks)
- [ ] Add sync tracking to contacts.md (last_synced, sync_version, sync_status)
- [ ] Add sync metadata to Square notes (footer section)
- [ ] Create `SyncState` model to track both systems
- [ ] Build conflict detection logic

### Phase 3b: Sync Engine (2-3 weeks)
- [ ] Implement `BidirectionalSyncEngine` class
- [ ] Build Square fetch/query methods
- [ ] Build contacts.md parse/update methods
- [ ] Create conflict resolution strategies

### Phase 3c: Manual Review (1 week)
- [ ] Implement conflict review queue generation
- [ ] Create CLI for resolving conflicts
- [ ] Add audit logging for all changes
- [ ] Generate sync reports

### Phase 3d: Testing & Safety (1-2 weeks)
- [ ] Unit tests for conflict detection
- [ ] Integration tests with Square Sandbox
- [ ] Dry-run mode (shows what would change, doesn't apply)
- [ ] Rollback mechanism for bad syncs

### Phase 3e: Automation (1-2 weeks, optional)
- [ ] Scheduled sync via launchd (daily)
- [ ] Slack notifications on conflicts
- [ ] Auto-resolution rules (configurable)
- [ ] Sync health monitoring

---

## Risk Mitigation

### Risk 1: Data Loss

**Mitigation:**
- Keep audit log of all syncs
- Version tracking (sync_version field)
- Dry-run mode before live sync
- Backup contacts.md before each sync
- Never auto-delete fields, only update

### Risk 2: Merge Conflicts

**Mitigation:**
- Manual review queue for complex conflicts
- Clear flagging when both systems disagree
- Preserve both versions in conflict log
- User must explicitly approve resolutions

### Risk 3: Circular Sync Loops

**Mitigation:**
- Check timestamp before updating
- Skip if local and remote timestamps are identical
- Increment sync_version to prevent re-applying same change
- Log all sync operations

### Risk 4: API Rate Limits

**Mitigation:**
- Batch updates (max 100 per call)
- Respect Square rate limits (100 req/sec)
- Implement exponential backoff on 429 errors
- Stagger syncs for large contact lists

---

## Success Criteria

**Phase 3 completion when:**
- ✅ Contacts edited locally appear in Square within 1 minute
- ✅ Square staff notes appear in contacts.md within 1 minute
- ✅ Conflicts detected and flagged for review
- ✅ Manual resolution preserves intent from both systems
- ✅ Zero data loss in test scenarios
- ✅ Audit trail complete for all changes

---

## Future Enhancements (Phase 4+)

### Scheduled Sync (Phase 5)
```bash
# Add to launchd (runs daily at 6 AM)
/usr/local/bin/python3 /Users/scottybe/.claude/skills/square-crm/scripts/sync_bidirectional.py
```

### Smart Conflict Resolution (Phase 3b+)
- ML-based confidence scoring
- Auto-accept low-risk conflicts
- Context-aware merging (time of day, contact pattern, etc.)

### Multi-Source Sync (Phase 4)
- Google Contacts as secondary source
- Apple Contacts integration
- Aggregate phone number changes across platforms

---

## Summary: Why Two-Way Sync?

**Current (Phase 1) Problem:**
- Changes at POS don't flow back → stale contacts.md
- Local edits require manual Square updates → repetitive work
- No purchase history in contacts.md → missing context

**Two-Way Sync Solution:**
- Automatic bidirectional updates → always in sync
- Manual review for conflicts → human control maintained
- Rich context everywhere → better decision-making at POS
- Audit trail → full history of customer relationship

**Next Step:** Decide priority. If high-priority, start Phase 3a foundation work.
