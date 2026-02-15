# square-cache

Claude beta skill for accessing MongoDB-cached Square catalog with comprehensive change tracking.

## Quick Start

```bash
# Token
export SQUARE_ACCESS_TOKEN=your_token

# Check cache status
~/workspace/square/square-tools/bin/square_cache.sh status

# Sync catalog
~/workspace/square/square-tools/bin/square_cache.sh sync

# View recent changes
~/workspace/square/square-tools/bin/square_cache.sh changes

# Search cached items
~/workspace/square/square-tools/bin/square_cache.sh search "vinyl"
```

## Python Usage

```python
from skills.square_cache.scripts.cache_wrapper import SquareCacheWrapper

cache = SquareCacheWrapper()
status = cache.get_status()
items = cache.search_items("trading places")
changes = cache.get_recent_changes(since="2025-12-01")
```

## Key Features

- **10-50x faster** searches than Square API
- **Complete audit trail** with before/after snapshots
- **Field-level diffs** showing exactly what changed
- **Offline access** to catalog data
- **Pre-built MongoDB queries** for common operations

## Files

- `SKILL.md` - Main skill documentation
- `scripts/cache_wrapper.py` - Python wrapper for cache operations
- `scripts/query_helper.py` - MongoDB query templates
- `references/api_reference.md` - Complete technical documentation

## Integration

Use with:
- `rg-full-auto` - Fast item lookups before API calls
- `square-image-upload` - Verify items exist before uploads
- `product-labeler` - Pull cached data for labels

Built: 2025-12-20
