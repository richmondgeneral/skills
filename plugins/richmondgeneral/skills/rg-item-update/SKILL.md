---
name: rg-item-update
description: Quick edits to existing Richmond General catalog items. Use for price changes, description updates, SEO tweaks, adding/replacing images, category changes, or fixing typos. Triggers on "update item", "change price", "edit description", "fix", "modify existing". Also handles BATCH operations like "move all food items" or "update category for multiple items". NOT for new items—use rg-full-auto for complete onboarding workflow. NOT for items that have sold—use rg-item-mark-sold to migrate the listing to the sold-archive pattern and delete the Square payment link.
metadata:
  version: "1.4"
  author: scottybe
  updated: "2026-02-16"
  changelog: |
    v1.4 - catalog governance delegation:
    - Added delegation to `square-catalog-ops` for category merge/audit/compliance checks
    - Added post-write cleanup audit gate before cache reconciliation
    - Added `Food & Pantry` guidance for consolidated food routing

    v1.3 - description_html + connector naming:
    - Switched item description guidance/template from `description` to `description_html`
    - Added paragraph/Unicode formatting note for Square rendering
    - Renamed Square cache connector examples to `square_cache_mcp:*`
    - Updated category update template to type + tier categories with `reporting_category`

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
| Search cache | `square_cache_mcp:square_cache_search` (fast) |
| Direct API | `catalog.searchItems` |

## Find the Item First

**Option 1: Cache search (fastest)**
```
square_cache_mcp:square_cache_search with name_pattern or sku_pattern
```

**Option 2: API search**
```
catalog.searchItems with text_filter or exact_query
```

Returns `item_id` and `variation_id` needed for updates.

## Update Operations

### Price Change

**Margin check:** If repricing significantly, consider running `rg-lot-tracker` Phase 2 to verify the new price still covers allocated cost. Trigger: "margin check for RG-XXXX at $NEW_PRICE".

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

**⚠️ Use `description_html` (NOT `description`).** Wrap paragraphs in `<p>` tags. Use Unicode characters (©, –, —) not HTML entities. See rg-full-auto Phase 2 for full formatting rules.

```json
{
  "idempotency_key": "uuid",
  "objects": [{
    "type": "ITEM",
    "id": "ITEM_ID",
    "item_data": {
      "description_html": "<p>First paragraph.</p><p>Second paragraph.</p>",
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

**Type categories (primary + reporting):** Books & Paper `CLZCJ62H4TTHDQ3ZBYMZQASQ`, Furniture `W3EYAJJPTNC46WSLNYI4WH7V`, Pottery & Ceramics `APSTFSN4UXQI44HBFSDTSEX7`, Collectibles `YQWBSOJDENMXDGUUQ3TGI3HF`, Art & Craft Kits `F4JQYK4Z5MEBV5VFCDYHIAWT`, Wellness & Apothecary `I5PMPWGTVR7IDBL4RUJWN3A4`, The Apothecary Cabinet `6E7UZYZFNZBGFRJFH272RVBE`, Home & Gifts `AR3ZTA45KU4BH23AJ7LOLLRA`, Analog `N35REXL33FZWJNJV24IUQGPN`

**Tier categories (secondary):** The New Finds `P34KX3L7XRZJJ5RP6W35K4YO` (default), The Real Rarities `FL4L42RRUE5UXMWFDLXOCNB5` (rare only)

For food items, route to consolidated `Food & Pantry` (`CYTCL6ES7TSG2XCUVHIDG5B2`) instead of legacy food categories.
See `rg-full-auto/references/square-catalog.md` for full list including TVM categories.

```json
{
  "idempotency_key": "uuid",
  "objects": [{
    "type": "ITEM",
    "id": "ITEM_ID",
    "item_data": {
      "categories": [
        {"id": "TYPE_CATEGORY_ID"},
        {"id": "TIER_CATEGORY_ID"}
      ],
      "reporting_category": {"id": "TYPE_CATEGORY_ID"}
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

To **replace** primary image: delete old image first via `catalog.batchDeleteobjects` (note the lowercase `o`; there is no `deleteObjects` method), then upload new.

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

## Catalog Governance Ops (Delegate)

Use `square-catalog-ops` for taxonomy-level operations (not ad-hoc inline updates):

```bash
# Prove version + SDK compliance
python3 ${CLAUDE_PLUGIN_ROOT}/skills/square-catalog-ops/scripts/catalog_ops.py compliance

# Merge legacy food categories -> Food & Pantry
python3 ${CLAUDE_PLUGIN_ROOT}/skills/square-catalog-ops/scripts/catalog_ops.py merge-food --apply

# Verify cleanup/channel assignment integrity
python3 ${CLAUDE_PLUGIN_ROOT}/skills/square-catalog-ops/scripts/catalog_ops.py audit-cleanup --fail-on-issues
```

## Cache Reconciliation (Required)

After any write to Square (price, description, category, image, inventory), sync cache and verify the update is visible.

Before cache reconciliation on category/visibility updates, run cleanup audit:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/square-catalog-ops/scripts/catalog_ops.py audit-cleanup --fail-on-issues
```

**Primary (MCP):**
```
square_cache_mcp:square_cache_sync
```

**Fallback (local script):**
```bash
uv run --project ${CLAUDE_PLUGIN_ROOT} python ${CLAUDE_PLUGIN_ROOT}/skills/square-cache/scripts/cache_wrapper.py sync --json
```

Verification:
- Query the changed SKU/item via `square_cache_mcp:square_cache_search` or `square_cache_mcp:square_cache_get_item`
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
| `rg-item-mark-sold` | Terminal state — item sold, kill the Square payment link, migrate the GitHub Pages card to the sold-archive pattern |
| `square-image-upload` | Dedicated image upload handling |
| `square-catalog-ops` | Category merge, cleanup audit, compliance proof |
| `square-webhook-monitor` | Webhook subscription and monitor operations |
| `square-cache` | Sync and verify cached catalog state after updates |
