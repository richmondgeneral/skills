# Square Cache API Reference

Complete technical reference for the Square catalog caching system.

## MongoDB Schema

### catalog_items Collection

Stores complete Square catalog items with change detection metadata.

**Indexes:**
- `id` (unique) - Square item ID
- `updated_at` - Item last modified timestamp
- `version` - Square version number
- `item_data.name` - Item name for text searches

**Schema:**
```javascript
{
  _id: ObjectId,                    // MongoDB document ID
  id: "SQUARE_ITEM_ID",             // Square catalog item ID (unique)
  type: "ITEM",                     // Catalog object type
  updated_at: "2025-12-20T04:00:00.000Z",  // Last modified (from Square)
  version: 1759194200000,           // Square version number (incrementing)
  is_deleted: false,                // Deletion flag
  
  item_data: {
    name: "Trading Places VHS",     // Item display name
    description: "1983 comedy...",  // Item description (optional)
    product_type: "REGULAR",        // REGULAR | GIFT_CARD | APPOINTMENTS_SERVICE
    
    image_ids: [                    // Attached image IDs (optional)
      "IMAGE_ID_1",
      "IMAGE_ID_2"
    ],
    
    variations: [                   // Item variations (prices/SKUs)
      {
        id: "VARIATION_ID",
        type: "ITEM_VARIATION",
        item_variation_data: {
          item_id: "SQUARE_ITEM_ID",
          name: "Regular",
          pricing_type: "FIXED_PRICING",
          price_money: {
            amount: 1999,           // Cents
            currency: "USD"
          },
          sku: "VHS-TP-001"
        }
      }
    ],
    
    categories: [                   // Category associations (optional)
      {
        id: "CATEGORY_ID",
        ordinal: 0
      }
    ],
    
    tax_ids: [],                    // Tax configuration (optional)
    modifier_list_info: []          // Modifier lists (optional)
  },
  
  content_hash: "sha256_hash_here",  // SHA256 hash (excluding updated_at, version)
  cached_at: ISODate("2025-12-20T04:00:00Z")  // When cached locally
}
```

### change_snapshots Collection

Complete audit trail of all catalog changes with before/after data.

**Indexes:**
- `item_id` - Links changes to items
- `timestamp` - Change occurrence time
- `change_type` - Type of change (create/update/delete)

**Schema:**
```javascript
{
  _id: ObjectId,
  item_id: "SQUARE_ITEM_ID",        // Changed item ID
  item_name: "Trading Places VHS",  // Item name (for reporting)
  change_type: "update",            // create | update | delete
  timestamp: ISODate("2025-12-20T04:00:00Z"),  // When change detected
  
  before_data: {                    // Complete item state before change
    // Full catalog_items document (null for creates)
  },
  
  after_data: {                     // Complete item state after change
    // Full catalog_items document (null for deletes)
  },
  
  differences: {                    // Field-level diffs (updates only)
    "item_data.image_ids": {
      before: [],
      after: ["IMAGE_ID_1", "IMAGE_ID_2"]
    },
    "version": {
      before: 1759194139169,
      after: 1759194200000
    },
    "updated_at": {
      before: "2025-12-19T12:00:00.000Z",
      after: "2025-12-20T04:00:00.000Z"
    }
  },
  
  square_version_before: 1759194139169,  // Square version numbers
  square_version_after: 1759194200000
}
```

### sync_log Collection

Sync operation history with performance metrics and errors.

**Indexes:**
- `timestamp` - Sync operation time

**Schema:**
```javascript
{
  _id: ObjectId,
  timestamp: ISODate("2025-12-20T04:00:00Z"),  // Sync start time
  status: "success",                            // success | error
  items_processed: 142,                         // Total items checked
  changes_detected: 3,                          // Changes found
  duration_seconds: 8.5,                        // Sync duration
  error: null                                   // Error message (if failed)
}
```

## Change Detection Algorithm

### Content Hashing

The cache uses SHA256 hashing to efficiently detect changes:

```python
def _calculate_hash(self, data: Dict) -> str:
    """Calculate SHA256 hash excluding volatile fields"""
    clean_data = data.copy()
    
    # Remove fields that change on every update
    if 'updated_at' in clean_data:
        del clean_data['updated_at']
    if 'version' in clean_data:
        del clean_data['version']
    
    # Sort keys for consistent hashing
    json_str = json.dumps(clean_data, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(json_str.encode()).hexdigest()
```

**Excluded Fields:**
- `updated_at` - Changes every sync
- `version` - Increments on every change
- `_id` - MongoDB internal ID

**Why Hashing?**
- Fast comparison (64-character string vs. full JSON)
- Detects any meaningful change
- Avoids false positives from timestamp updates

### Change Detection Flow

```
1. Fetch item from Square API
   ↓
2. Calculate content hash (exclude updated_at, version)
   ↓
3. Look up cached item by ID
   ↓
4. Compare hashes
   ↓
5a. Hash match → No change, skip
5b. Hash differs → Generate diff, create snapshot
   ↓
6. Update cache with new data
   ↓
7. Log change to change_snapshots collection
```

### Diff Generation

Field-level comparison identifies exactly what changed:

```python
compare_fields = [
    'item_data.name',
    'item_data.description',
    'item_data.image_ids',
    'item_data.variations',
    'item_data.categories',
    'version',
    'updated_at'
]

for field_path in compare_fields:
    before_val = get_nested_value(before, field_path)
    after_val = get_nested_value(after, field_path)
    
    if before_val != after_val:
        differences[field_path] = {
            'before': before_val,
            'after': after_val
        }
```

## Performance Characteristics

### Search Performance

**Cache vs. API:**
- Cache search: ~10-50ms (MongoDB indexed query)
- API search: ~200-500ms (network + Square processing)
- **Speedup: 10-50x**

**Indexes for Fast Queries:**
```javascript
// Created automatically by SquareCacheManager
items_collection.create_index("id", unique=True)
items_collection.create_index("item_data.name")
changes_collection.create_index([("item_id", 1), ("timestamp", -1)])
sync_log_collection.create_index("timestamp")
```

### Sync Performance

**Typical Metrics:**
- 150 items: ~8-12 seconds
- 500 items: ~25-35 seconds
- 1000 items: ~50-70 seconds

**Rate Limiting:**
- Square API: 200 requests/minute
- Pagination: 200 items/request
- Sync frequency: Every 1-4 hours recommended

### Storage Requirements

**Estimates:**
- catalog_items: ~5-15KB per item
- change_snapshots: ~20-40KB per change (includes before/after)
- sync_log: ~1KB per sync

**Example:**
- 150 items: ~1-2MB base cache
- 500 changes: ~10-20MB change history
- 1000 syncs: ~1MB log history
- **Total: ~12-23MB for moderate usage**

## Advanced Queries

### Aggregation Pipelines

**Items by category with counts:**
```javascript
db.catalog_items.aggregate([
  { $unwind: "$item_data.categories" },
  { $group: {
      _id: "$item_data.categories.id",
      count: { $sum: 1 }
  }},
  { $sort: { count: -1 }}
])
```

**Changes by day:**
```javascript
db.change_snapshots.aggregate([
  { $group: {
      _id: {
        year: { $year: "$timestamp" },
        month: { $month: "$timestamp" },
        day: { $dayOfMonth: "$timestamp" }
      },
      count: { $sum: 1 }
  }},
  { $sort: { "_id.year": -1, "_id.month": -1, "_id.day": -1 }}
])
```

**Top changed items:**
```javascript
db.change_snapshots.aggregate([
  { $group: {
      _id: "$item_id",
      name: { $first: "$item_name" },
      change_count: { $sum: 1 }
  }},
  { $sort: { change_count: -1 }},
  { $limit: 10 }
])
```

### Complex Filters

**Items with images but no description:**
```javascript
db.catalog_items.find({
  "item_data.image_ids": { $exists: true, $ne: [] },
  $or: [
    { "item_data.description": { $exists: false }},
    { "item_data.description": "" }
  ]
})
```

**Items updated in date range:**
```javascript
db.catalog_items.find({
  updated_at: {
    $gte: new Date("2025-12-01"),
    $lte: new Date("2025-12-31")
  }
}).sort({ updated_at: -1 })
```

**Changes with specific field modifications:**
```javascript
db.change_snapshots.find({
  "differences.item_data.image_ids": { $exists: true }
})
```

## Error Handling

### Common Errors

**MongoDB Not Running:**
```
pymongo.errors.ServerSelectionTimeoutError: localhost:27017
```
**Fix:** `brew services start mongodb-community@8.0`

**Square API Authentication:**
```
401 Unauthorized: Invalid token
```
**Fix:** Verify `SQUARE_ACCESS_TOKEN` (or legacy `SQUARE_TOKEN`) is valid with `ITEMS_READ` permission

**Rate Limiting:**
```
429 Too Many Requests: Rate limit exceeded
```
**Fix:** Reduce sync frequency, wait 60 seconds

**Network Timeout:**
```
requests.exceptions.Timeout: Connection timeout
```
**Fix:** Check internet connection, retry sync

### Sync Error Recovery

**Partial sync failure:**
1. Check `sync_log` for error details
2. Items processed before error are cached
3. Re-run sync to continue from failure point
4. Cache remains consistent (atomic updates per item)

**Cache corruption:**
1. Export data: `mongoexport --db=square_cache --collection=catalog_items --out=backup.json`
2. Clear cache: `mongosh square_cache --eval "db.catalog_items.deleteMany({})"`
3. Re-sync: `square_cache.sh sync`
4. Verify: `square_cache.sh status`

## Integration Patterns

### Pre-API Cache Check

```python
# Fast path: Check cache first
cache = SquareCacheWrapper()
item = cache.get_item(item_id)

if item:
    # Use cached data (instant)
    print(f"Found in cache: {item['item_data']['name']}")
else:
    # Fall back to API
    response = square_api.get_item(item_id)
    # Trigger sync to update cache
    cache.sync_cache()
```

### Post-Update Sync

```python
# After modifying item via API
square_api.update_item(item_id, changes)

# Sync to capture changes in cache
cache = SquareCacheWrapper()
cache.sync_cache()

# View what changed
history = cache.get_item_history(item_id)
latest_change = history[0]
print(f"Changed: {latest_change['differences']}")
```

### Change Monitoring

```python
# Daily change check
cache = SquareCacheWrapper()
changes = cache.get_recent_changes(since="2025-12-19")

for change in changes:
    if change['change_type'] == 'update':
        if 'item_data.image_ids' in change['differences']:
            print(f"Image added to: {change['item_name']}")
```

## Backup and Restore

### Export Cache

```bash
# Export items
mongoexport --db=square_cache --collection=catalog_items \
  --out=items_backup.json --jsonArray

# Export changes
mongoexport --db=square_cache --collection=change_snapshots \
  --out=changes_backup.json --jsonArray

# Export sync log
mongoexport --db=square_cache --collection=sync_log \
  --out=sync_log_backup.json --jsonArray
```

### Import Cache

```bash
# Import items
mongoimport --db=square_cache --collection=catalog_items \
  --file=items_backup.json --jsonArray

# Import changes
mongoimport --db=square_cache --collection=change_snapshots \
  --file=changes_backup.json --jsonArray

# Rebuild indexes
mongosh square_cache --eval "
  db.catalog_items.createIndex({id: 1}, {unique: true});
  db.catalog_items.createIndex({'item_data.name': 1});
  db.change_snapshots.createIndex({item_id: 1, timestamp: -1});
  db.sync_log.createIndex({timestamp: -1});
"
```

## Security Considerations

**Access Token Protection:**
- Never log `SQUARE_ACCESS_TOKEN` (or `SQUARE_TOKEN`) in plain text
- Use environment variables, not hardcoded values
- Token has `ITEMS_READ` permission (read-only)
- Sync operations don't modify Square catalog

**MongoDB Security:**
- Default: localhost-only access (no auth)
- Production: Enable authentication, SSL/TLS
- Bind to localhost: `bindIp: 127.0.0.1` in mongod.conf

**Cache Data Sensitivity:**
- Contains product names, prices, descriptions
- No customer PII (names, emails, payment info)
- Safe for local development caching
- Production: Consider encrypted storage

## Future Enhancements

**Planned Features:**
- Variation-level change tracking (currently item-level only)
- Real-time webhooks (Square → cache updates)
- Automated sync scheduling (cron/systemd)
- Cache expiration policies (TTL on stale items)
- Export to CSV for reporting
- Cache analytics dashboard (web UI)
- Multi-location support
- Category and modifier caching
- Image metadata caching

**Performance Improvements:**
- Incremental sync (only changed items)
- Parallel API requests
- Compression for change snapshots
- Archive old changes (rolling window)

**Integration Features:**
- Webhook receiver for real-time updates
- REST API wrapper (Flask/FastAPI)
- GraphQL query interface
- Pub/sub change notifications
