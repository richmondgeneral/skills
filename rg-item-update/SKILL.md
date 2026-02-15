---
name: rg-item-update
description: Quick edits to existing Richmond General catalog items. Use for price changes, description updates, SEO tweaks, adding/replacing images, category changes, or fixing typos. Triggers on "update item", "change price", "edit description", "fix", "modify existing". Also handles BATCH operations like "move all food items" or "update category for multiple items". NOT for new items—use rg-full-auto for complete onboarding workflow.
metadata:
  version: "1.2"
  author: scottybe
  updated: "2026-02-15"
  changelog: |
    v1.2 - cache reconciliation update:
    - Added required post-write square-cache sync/verification step
    - Updated related skills table to current rg-full-auto phase count

    v1.1 - Anthropic skills update:
    - Added batch operation triggers to description
    - Added author and updated fields
---

# Richmond General Item Update

Lightweight operations for modifying existing catalog items.

## Quick Reference

| Key | Value |
|-----|-------|
| Square Location | B87BAEZ0NWV34 |
| Search cache | `square_cache_search` (fast) |
| Direct API | `catalog.searchItems` |

## Find the Item First

**Option 1: Cache search (fastest)**
```
square_cache_search with name_pattern or sku_pattern
```

**Option 2: API search**
```
catalog.searchItems with text_filter or exact_query
```

Returns `item_id` and `variation_id` needed for updates.

## Update Operations

### Price Change

**Endpoint:** `catalog.batchUpdateObjects` with `sparse_update: true`

```json
{
  "idempotency_key": "uuid",
  "objects": [{
    "type": "ITEM_VARIATION",
    "id": "VARIATION_ID",
    "item_variation_data": {
      "price_money": {"amount": 2499, "currency": "USD"}
    }
  }],
  "sparse_update": true
}
```

### Description / SEO Update

```json
{
  "idempotency_key": "uuid",
  "objects": [{
    "type": "ITEM",
    "id": "ITEM_ID",
    "item_data": {
      "description": "New HTML description",
      "ecom_seo_data": {
        "page_title": "Updated Title | Richmond General",
        "page_description": "Updated meta description. Richmond, IL.",
        "permalink": "updated-slug"
      }
    }
  }],
  "sparse_update": true
}
```

### Category Change

**Categories (choose ONE):**
- The Real Rarities: `FL4L42RRUE5UXMWFDLXOCNB5` (rare/special)
- The New Finds: `P34KX3L7XRZJJ5RP6W35K4YO` (regular new stock)

```json
{
  "idempotency_key": "uuid",
  "objects": [{
    "type": "ITEM",
    "id": "ITEM_ID",
    "item_data": {
      "categories": [
        {"id": "CHOSEN_CATEGORY_ID"}
      ]
    }
  }],
  "sparse_update": true
}
```

### Add/Replace Image

MCP doesn't support multipart uploads. Generate curl for user:

```bash
curl -X POST "https://connect.squareup.com/v2/catalog/images" \
  -H "Authorization: Bearer $SQUARE_ACCESS_TOKEN" \
  -H "Accept: application/json" \
  -F "request={
    \"idempotency_key\": \"update-$(date +%s)\",
    \"image\": {
      \"type\": \"IMAGE\",
      \"id\": \"#temp-update\",
      \"image_data\": {
        \"name\": \"Item Name - New Image\"
      }
    },
    \"object_id\": \"ITEM_ID\"
  };type=application/json" \
  -F "image_file=@new-image.jpeg;type=image/jpeg"
```

To **replace** primary image: delete old image first via `catalog.deleteObjects`, then upload new.

### Inventory Adjustment

**Endpoint:** `inventory.batchChange`

```json
{
  "idempotency_key": "uuid",
  "changes": [{
    "type": "ADJUSTMENT",
    "adjustment": {
      "catalog_object_id": "VARIATION_ID",
      "from_state": "IN_STOCK",
      "to_state": "SOLD",
      "location_id": "B87BAEZ0NWV34",
      "quantity": "1",
      "occurred_at": "2025-01-15T12:00:00Z"
    }
  }]
}
```

## Cache Reconciliation (Required)

After any write to Square (price, description, category, image, inventory), sync cache and verify the update is visible.

**Primary (MCP):**
```
square_cache_sync
```

**Fallback (local script):**
```bash
uv run --project ~/.claude/skills python ~/.claude/skills/square-cache/scripts/cache_wrapper.py sync --json
```

Verification:
- Query the changed SKU/item via `square_cache_search` or `square_cache_get_item`
- For image updates, confirm `item_data.image_ids` includes the new image
- For batch updates, run one sync at the end, then spot-check at least 3 updated items

## Common Fixes

| Issue | Solution |
|-------|----------|
| Typo in name | `batchUpdateObjects` with corrected `name` |
| Wrong price | Update variation `price_money` |
| Missing from online | Check `ecom_visibility: "VISIBLE"` and inventory > 0 |
| Wrong category | Update `categories` array with correct category ID |

## Related Skills

| Skill | Use For |
|-------|---------|
| `rg-full-auto` | New item onboarding (10-phase workflow) |
| `square-image-upload` | Dedicated image upload handling |
| `square-cache` | Sync and verify cached catalog state after updates |
