---
name: square-cache
description: Access MongoDB-cached Square catalog with change tracking and audit trails. Use when checking catalog status, searching items (faster than API), viewing change history, monitoring updates, or querying cached data. Triggers on "Square cache", "catalog changes", "what changed", "search cached items", "sync catalog", "item history", "cache status". Required for offline catalog access and automated change detection.
metadata:
  version: "1.5"
  author: scottybe
  updated: "2026-07-15"
  runtime_tier: "WEB_SAFE"
  required_capabilities:
    - mcp_local_tools
  changelog: |
    v1.5 - square-catalog-ops delegation removed (skill deleted 2026-06-20); cache framed as speed layer (live Square = source of truth)

    v1.4 - runtime contract alignment:
    - Added runtime tier and capability metadata
    - Added runtime policy guidance references for WEB_SAFE vs LOCAL_STANDARD sync operations

    v1.3 - webhook monitor integration:
    - Added webhook-monitor triage workflow for near-real-time change detection

    v1.2 - path and token compatibility update:
    - Updated square-tools path references to ~/workspace/square/square-tools
    - Standardized token guidance to SQUARE_ACCESS_TOKEN with SQUARE_TOKEN fallback
    - Aligned documentation with wrapper path/token auto-resolution

    v1.1 - Anthropic skills update:
    - Added author and updated fields
---

# Square Cache Management

Local MongoDB cache of Square catalog items with comprehensive change tracking, before/after snapshots, and field-level diff reports.

## Why This Skill Exists

⚠️ **Live Square is the source of truth — this cache is a SPEED LAYER.** Never base a write
decision (price/state/category change, listing, mark-sold) on cache data alone; reconcile
against the live API first. Cache staleness is normal between syncs.

**Performance:** Cache searches are instant vs. API calls taking seconds.

**Change Detection:** Automated tracking of all catalog modifications with SHA256 content hashing.

**Audit Trail:** Complete before/after snapshots with field-level diffs for every change.

**Offline Access:** Query catalog data without hitting Square API limits.

**Historical Data:** Track item evolution over time with complete change history.

## Runtime Policy Contract

This skill follows runtime policy files in:

- `/Users/scottybe/workspace/square/square-tools/runtime/capability_matrix.json`
- `/Users/scottybe/workspace/square/square-tools/runtime/operation_policy.json`

Mode expectations:

- `WEB_SAFE`: `status/search/changes/report/item`
- `LOCAL_STANDARD`: `sync` (mutating operation)

Preflight gate:

```bash
/Users/scottybe/workspace/square/square-tools/bin/agent_preflight.sh --operation square_cache_read --runtime "${SQUARE_RUNTIME_ID:-local_cli}"
```

## Access Methods

This skill supports **two access methods** depending on your environment:

1. **Bash commands** (terminal/Warp CLI) - Use `square_cache.sh` wrapper
2. **MCP tools** (Warp Agent Mode) - Native tool integration via MCP server

### MCP Tools (Claude Desktop / Agent Mode)

**Available MCP tools when `square_cache_mcp` MCP server is configured:**
- `square_cache_search` - Search by name or SKU
- `square_cache_get_item` - Get full item details
- `square_cache_status` - Check cache health
- `square_cache_changes` - View recent changes
- `square_cache_sync` - Trigger sync

**Usage in Warp Agent Mode:**
```
"Search cache for Bears items"
"Check if SKU RG-0010 exists"
"Get details for item A55Q4TG7EJ2IJUDIFX3VHVAH"
"What changed in the catalog today?"
```

See MCP server setup: `~/workspace/square/square-tools/mcp-server/README.md`

## Quick Start

### Prerequisites

1. MongoDB running: `brew services start mongodb-community@8.0`
2. Python 3.7+ with pymongo, requests
3. Square token wired up: Keychain entry `SQUARE_ACCESS_TOKEN` exists (auto-exported by `~/.zshrc`); falls back to project `.env`. See [project root `.env.example`](../../.env.example) for setup.
4. Initial sync: `~/workspace/square/square-tools/bin/square_cache.sh sync`
5. (Optional) Configure MCP server for Warp Agent Mode

### Verify Setup

```bash
# Check cache status
~/workspace/square/square-tools/bin/square_cache.sh status

# Should show MongoDB running, items cached, last sync time
```

## Core Commands

### Sync Catalog

```bash
# Full sync from Square API to MongoDB
~/workspace/square/square-tools/bin/square_cache.sh sync
```

Fetches all catalog items, detects changes, creates snapshots. Run after making changes in Square dashboard or via API.

### Check Status

```bash
~/workspace/square/square-tools/bin/square_cache.sh status
```

Shows:
- MongoDB connection status
- Items cached count
- Change records count
- Last sync timestamp and status

### View Recent Changes

```bash
# All recent changes
~/workspace/square/square-tools/bin/square_cache.sh changes

# Changes since specific date
~/workspace/square/square-tools/bin/square_cache.sh changes --since 2025-12-01
```

Displays changes with emoji indicators:
- 🆕 = new item created
- 🔄 = item updated (with field-level diffs)
- ❌ = item deleted

### Search Cached Items

```bash
# Search by name pattern (case-insensitive, default)
~/workspace/square/square-tools/bin/square_cache.sh search "Trading Places"

# Search by SKU (exact or prefix)
~/workspace/square/square-tools/bin/square_cache.sh search --sku RG-0005
~/workspace/square/square-tools/bin/square_cache.sh search --sku "RG-"

# Explicit name search
~/workspace/square/square-tools/bin/square_cache.sh search --name "Bears"

# Returns matching items instantly from cache (100x faster than API)
```

### Get Item Details

```bash
# Get cached item by ID
~/workspace/square/square-tools/bin/square_cache.sh item ANE5SXKQR4JZ6AYEZDO26IMX
```

### Generate Change Report

```bash
# Detailed change report
~/workspace/square/square-tools/bin/square_cache.sh report

# JSON format for parsing
~/workspace/square/square-tools/bin/square_cache.sh report --json
```

## Direct MongoDB Queries

### Basic Queries

```bash
# Access MongoDB shell
mongosh square_cache

# Count total items
mongosh square_cache --eval "db.catalog_items.countDocuments()"

# Get items with images
mongosh square_cache --eval "db.catalog_items.find({'item_data.image_ids': {\$exists: true}}).count()"

# Get items without descriptions
mongosh square_cache --eval "db.catalog_items.find({'item_data.description': {\$exists: false}}).count()"
```

### Change Tracking Queries

```bash
# View latest sync operation
mongosh square_cache --eval "db.sync_log.findOne({}, {sort: {timestamp: -1}})"

# View all changes for specific item
mongosh square_cache --eval "db.change_snapshots.find({item_id: 'ITEM_ID'}).pretty()"

# Changes in last 24 hours
mongosh square_cache --eval "db.change_snapshots.find({timestamp: {\$gte: new Date(Date.now() - 24*60*60*1000)}}).pretty()"

# Count changes by type
mongosh square_cache --eval "db.change_snapshots.aggregate([{\\$group: {_id: '\\$change_type', count: {\\$sum: 1}}}])"
```

### Advanced Queries

```bash
# Items updated in last week
mongosh square_cache --eval "db.catalog_items.find({updated_at: {\$gte: new Date(Date.now() - 7*24*60*60*1000)}}).count()"

# Items by category
mongosh square_cache --eval "db.catalog_items.find({'item_data.categories': {\$exists: true}}).pretty()"

# Recent sync errors
mongosh square_cache --eval "db.sync_log.find({error: {\$exists: true}}).sort({timestamp: -1}).limit(5).pretty()"
```

## Python Integration

### Using cache_wrapper.py

```python
from cache_wrapper import SquareCacheWrapper  # illustrative — run from the skill's scripts/ dir

cache = SquareCacheWrapper()

# Get cache status
status = cache.get_status()
print(f"Items cached: {status['items_count']}")

# Search items
results = cache.search_items("vinyl")
for item in results:
    print(f"{item['id']}: {item['item_data']['name']}")

# Get item history
history = cache.get_item_history("ANE5SXKQR4JZ6AYEZDO26IMX")
for change in history:
    print(f"{change['timestamp']}: {change['change_type']}")

# Recent changes
changes = cache.get_recent_changes(since="2025-12-01")
```

### Using query_helper.py

```python
from query_helper import QueryHelper  # illustrative — run from the skill's scripts/ dir

helper = QueryHelper()

# Get mongosh commands as strings
cmd = helper.items_with_images()
cmd = helper.items_without_descriptions()
cmd = helper.changes_by_date_range("2025-12-01", "2025-12-20")
cmd = helper.sync_errors()

# Execute via subprocess
import subprocess
result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
```

## Integration Workflows

### With rg-full-auto

When creating new item:
1. Search cache first for similar items
2. If found, clone attributes for consistency
3. After creation via API, trigger cache sync
4. Verify item appears in cache

### With square-image-upload

Before uploading image:
1. Search cache for item by ID
2. Verify item exists and is active
3. After upload, sync cache to capture new image_ids

### With product-labeler

When generating labels:
1. Search cache for items needing labels
2. Pull cached data (faster than API)
3. Generate label batch
4. Update cache with label_generated flag

### After catalog mutations

After any category/visibility mutation:
1. Run cache sync:
   - `~/workspace/square/square-tools/bin/square_cache.sh sync`
2. Verify recent diffs:
   - `~/workspace/square/square-tools/bin/square_cache.sh changes --since YYYY-MM-DD`

### With square-webhook-monitor

Use webhook events to trigger sync on catalog updates:
1. Create/verify webhook subscription for `catalog.version.updated`
2. Monitor incoming events using local monitor endpoint
3. Run cache sync when event is received

## Change Detection Algorithm

The cache uses SHA256 content hashing for efficient change detection:

1. **Hash Calculation:** Excludes volatile fields (`updated_at`, `version`)
2. **Comparison:** Compares hashes between Square API and cached version
3. **Diff Generation:** Field-by-field comparison identifies exactly what changed
4. **Snapshot Creation:** Stores complete before/after data for audit trail

Example change output:
```
🔄 Trading Places - Rare Video 8 Format (1983)
   Type: update
   Changes: item_data.image_ids, version, updated_at
   Version: 1759194139169 → 1759194200000
   BEFORE: No images attached  
   AFTER:  2 images attached
```

## MongoDB Schema

### catalog_items Collection

```javascript
{
  _id: ObjectId,
  id: "SQUARE_ITEM_ID",  // unique index
  type: "ITEM",
  updated_at: "2025-12-20T04:00:00.000Z",
  version: 1759194200000,
  is_deleted: false,
  item_data: {
    name: "Trading Places VHS",
    description: "1983 comedy starring Eddie Murphy...",
    product_type: "REGULAR",
    image_ids: ["IMAGE_ID_1", "IMAGE_ID_2"],
    variations: [...],
    categories: [...]
  },
  content_hash: "sha256_hash",  // for change detection
  cached_at: ISODate
}
```

### change_snapshots Collection

```javascript
{
  _id: ObjectId,
  item_id: "SQUARE_ITEM_ID",  // indexed
  item_name: "Trading Places VHS",
  change_type: "update",  // create, update, delete
  timestamp: ISODate,  // indexed
  before_data: {...},  // complete previous state
  after_data: {...},   // complete new state
  differences: {       // field-level diffs
    "item_data.image_ids": {
      before: [],
      after: ["IMAGE_ID_1", "IMAGE_ID_2"]
    }
  },
  square_version_before: 1759194139169,
  square_version_after: 1759194200000
}
```

### sync_log Collection

```javascript
{
  _id: ObjectId,
  timestamp: ISODate,  // indexed
  status: "success",   // or "error"
  items_processed: 142,
  changes_detected: 3,
  duration_seconds: 8.5,
  error: null  // or error message
}
```

## Troubleshooting

### MongoDB Not Running

```bash
# Check status
brew services list | grep mongodb

# Start MongoDB
brew services start mongodb-community@8.0

# Test connection
mongosh --eval "db.runCommand('ping')" --quiet
```

### Sync Errors

```bash
# Check recent sync logs
mongosh square_cache --eval "db.sync_log.find({error: {\$exists: true}}).sort({timestamp: -1}).limit(5).pretty()"

# Verify Square token
echo $SQUARE_ACCESS_TOKEN

# Test Square API connectivity
curl -H "Square-Version: 2026-04-21" \
     -H "Authorization: Bearer $SQUARE_ACCESS_TOKEN" \
     "https://connect.squareup.com/v2/catalog/list?types=ITEM&limit=1"
```

### Cache Reset (Nuclear Option)

```bash
# Clear all cache data
mongosh square_cache --eval "db.catalog_items.deleteMany({}); db.change_snapshots.deleteMany({}); db.sync_log.deleteMany({})"

# Resync from scratch
~/workspace/square/square-tools/bin/square_cache.sh sync
```

### Cache Out of Sync

If cache doesn't match Square dashboard:
1. Check last sync time: `square_cache.sh status`
2. Review sync errors: query `sync_log` collection
3. Trigger manual sync: `square_cache.sh sync`
4. Verify with spot check: compare cache vs API

## Environment Variables

`SQUARE_ACCESS_TOKEN` (and legacy alias `SQUARE_TOKEN`) are resolved automatically:
1. Shell env — `~/.zshrc` exports both from macOS Keychain entry `SQUARE_ACCESS_TOKEN` (account `$USER`).
2. Project `.env` at the repo root — fallback for launchd/cron/scripts that don't inherit shell env.

Other knobs (read by `square-tools/config.sh` and the cache scripts):

```bash
# Defaults; override per-shell if you need a different setup
export SQUARE_ENVIRONMENT="production"   # or 'sandbox' — also in project .env
export MONGO_URI="mongodb://localhost:27017/"
export MONGO_DATABASE="square_cache"
export SQUARE_LOG_LEVEL="INFO"           # also in project .env
```

To rotate the token:

```bash
security add-generic-password -U -a "$USER" -s SQUARE_ACCESS_TOKEN -w '<new-token>' -A \
    -j "Richmond General Square API production token"
# then update project .env to mirror the new value
```

## Performance Tips

1. **Use cache for searches:** 100x faster than API calls
2. **Sync periodically:** Not every operation (API rate limits)
3. **Leverage indexes:** Queries on `id`, `name`, `timestamp` are optimized
4. **Batch operations:** When possible, query multiple items at once
5. **JSON output:** Use `--json` flag for programmatic parsing

## Reference Files

See [references/api_reference.md](references/api_reference.md) for:
- Complete MongoDB schema details
- Index strategy explanation
- Change detection internals
- Advanced query patterns
- Performance benchmarks

## Related Skills

- **rg-full-auto:** Primary orchestrator using cache for item lookups
- **square-image-upload:** Verifies items exist before image uploads
- **product-labeler:** Pulls cached data for label generation
- **square-crm:** May cache customer data in future

## Future Enhancements

- Automated sync scheduling (cron job)
- Cache expiration policies
- Variation-level change tracking
- Real-time change notifications
- Cache analytics dashboard
- Export to CSV/JSON for reporting
