# Square Catalog API Reference

## Location & Merchant IDs

- **Location ID:** B87BAEZ0NWV34 (Richmond General - ACTIVE)
- **Merchant ID:** 7MM9AFJAD0XHW

**Scope:** This reference is for Square catalog payloads only. GitHub Pages and Whatnot use separate category formats.

## Categories

> **Verified live 2026-05-11** via `catalog.searchObjects { object_types: ["CATEGORY"] }`.
> If you find drift, re-query and update this table — process_new_item.py's
> `ROOM_BY_TYPE` map relies on these IDs being correct.

### RG Rooms (top-level, `is_top_level: true`)

The hero tiles on `/shop` route to these. An item may have a TYPE that lives
under one of these rooms (via `parent_category`), in which case ROOM_BY_TYPE
auto-attaches the room. An item whose TYPE *is* itself one of these rooms
(Apothecary Cabinet, Gallery, New Arrivals) needs no separate room category.

| Room | ID | Notes |
|------|-----|-------|
| **The General Store** | `QLM2GZ643LOCYHB653YIDJWT` | Parent of Books & Paper, Furniture-not, Wellness, Gifts, Home, Pottery, Food & Pantry, Art & Craft Kits |
| **The Vintage Market** | `TX6SBQLJDMZOCVXBUD3KT3CL` | Parent of Furniture, Collectibles, Analog & Vintage Media, Trésor Vintage Market |
| **The Apothecary Cabinet** | `QIPW32HGKMU5BDPU3A7YZCM4` | Top-level room (NOT a sub-type — items get this as their primary category) |
| **The Gallery** | `UMWTT7Q6UU4PXPUKU3DVNLFJ` | Parent of Artisan Lighting |
| **New Arrivals** | `TGWDFETSQPR6BF67YJCTOLW6` | **Default intake tier** — assigned to every new item on intake (re-tier later) |

### RG Type Categories (choose ONE primary)

| Category | ID | Parent Room | Use For |
|----------|-----|-------------|---------|
| **Books & Paper** | `CLZCJ62H4TTHDQ3ZBYMZQASQ` | General Store | Books, magazines, paper ephemera, cookbooks |
| **Furniture** | `W3EYAJJPTNC46WSLNYI4WH7V` | Vintage Market | Stools, trunks, tables, chairs, shelving |
| **Pottery & Ceramics** | `APSTFSN4UXQI44HBFSDTSEX7` | General Store | Mugs, vases, plaques, figurines, Hummel |
| **Collectibles** | `YQWBSOJDENMXDGUUQ3TGI3HF` | Vintage Market | Games, toys, dolls, ornaments, vintage misc |
| **Art & Craft Kits** | `F4JQYK4Z5MEBV5VFCDYHIAWT` | General Store | Watercolor kits, craft supplies, DIY art |
| **Wellness & Apothecary** | `I5PMPWGTVR7IDBL4RUJWN3A4` | General Store | Teas, serums, tinctures, natural products, R&L brand |
| **Gifts** | `AR3ZTA45KU4BH23AJ7LOLLRA` | General Store | Home decor, giftable items (live name: "Gifts" — previously labeled "Home & Gifts") |
| **Home** | `43IPDJV36K4AX55M4QFPYHHO` | General Store | General home goods that don't fit Gifts or Pottery |
| **Food & Pantry** | `CYTCL6ES7TSG2XCUVHIDG5B2` | General Store | Snacks, beverages — parent of Chips & Crisps / Cookies & Sweets / Drinks / Asian Imports |
| **Analog & Vintage Media** | `N35REXL33FZWJNJV24IUQGPN` | Vintage Market | Vinyl, LPs, cassettes, DVDs, film, magazines, analog tech (absorbed the deleted "Vintage Media" category) |
| **Trésor Vintage Market** | `XQY33UQNPA7IPZ4CBIYJX3VM` | Vintage Market | TVM-curated vintage (parent of Classic Beauty / Timeless Treasures / Expressly TVM / Whimsical Gifts) |

### Snack Categories

| Category | ID | Use For |
|----------|-----|---------|
| **Chips & Crisps** | `RZDJCH4X2C725QEU2AQCX2Y6` | Potato chips, tallow chips, savory snacks |
| **Cookies & Sweets** | `E23E2FWMORU4VLHRVTDMNWKB` | Biscuits, candy, chocolate |
| **Drinks** | `Z4CC7D2BNM5YLEQZXL6VA7I2` | Beverages, tea, juice |
| **Asian Imports** | `3NDGJCHLWBB3D7XKRJLYGCPF` | Japanese/Korean/Chinese snacks |

### Tier Categories (secondary overlay)

| Category | ID | Use For |
|----------|-----|---------|
| **New Arrivals** | `TGWDFETSQPR6BF67YJCTOLW6` | **Default intake tier** — every new item lands here, re-tier later as it ages |
| **The Real Rarities** | `FL4L42RRUE5UXMWFDLXOCNB5` | Truly rare, showcase-worthy pieces (secondary only) |
| **The New Finds** | `P34KX3L7XRZJJ5RP6W35K4YO` | A re-tier destination (no longer the intake default) |

### TVM Categories (reserved)

| Category | ID | Use For |
|----------|-----|---------|
| Classic Beauty | `FRBSRJRTP5Q5UQXPHK5JB666` | Vintage beauty, fashion |
| Timeless Treasures | `3N3II4W6Q7AA43RWQGEEWELY` | Rare French/European vintage |
| Expressly TVM | `JSL7MTE6Y2QRXTV2VCASRF2R` | TVM exclusives |
| Whimsical Gifts | `RXMZRCGB2XUBRSB4FQYZE464` | Giftable vintage |

### Category Assignment Rules

1. **Primary category** = type-based (Books & Paper, Furniture, etc.) — determines reporting
2. **Secondary category (tier)** = New Arrivals (default intake) — items get re-tiered over time
3. **The New Finds / The Real Rarities** = re-tier destinations for aged / genuinely special items
4. **Reporting category** = ALWAYS set to the type-based primary category (for Square sales reports)

**Decision flow:**
- Pick the type category that best fits → set as primary + reporting_category
- Add New Arrivals as the secondary tier on intake (re-tier to The New Finds / The Real Rarities later)

### Reporting Category

- **MUST be set** for items to appear in Category Sales reports
- Use the type-based **primary** category ID (not the tier category)
- If not set via API, item won't be attributed to any category in reports

### Tax ID
- **IL State + Richmond Local (8.5%):** `LPKEJF7H27NOPK7EE6A5CA7V`

Query all categories with: `catalog.searchObjects` with `object_types: ["CATEGORY"]`

## Creating Catalog Items

### Endpoint
Primary: `catalog.batchInsertObjects`
Fallback: `catalog.upsertCatalogObject`

**Compatibility note:** Connector method availability varies. If `batchInsertObjects` returns method/schema errors, switch to `upsertCatalogObject` using the alternate payload below.

**Idempotency rule:** `idempotency_key` remains top-level for both methods.

### Complete Item Creation (with required fields)

```json
{
  "idempotency_key": "uuid-v4-here",
  "batches": [{
    "objects": [{
      "type": "ITEM",
      "id": "#temp-id",
      "present_at_all_locations": false,
      "present_at_location_ids": ["B87BAEZ0NWV34"],
      "item_data": {
        "name": "Product Name",
        "description_html": "<p>Description paragraph one.</p><p>&nbsp;</p><p><b>Condition:</b> Good.</p>",
        "categories": [
          {"id": "TYPE_CATEGORY_ID"},
          {"id": "TIER_CATEGORY_ID"}
        ],
        "reporting_category": {"id": "TYPE_CATEGORY_ID"},
        "tax_ids": ["LPKEJF7H27NOPK7EE6A5CA7V"],
        "is_taxable": true,
        "ecom_visibility": "VISIBLE",
        "variations": [{
          "type": "ITEM_VARIATION",
          "id": "#temp-var-id",
          "present_at_all_locations": false,
          "present_at_location_ids": ["B87BAEZ0NWV34"],
          "item_variation_data": {
            "item_id": "#temp-id",
            "name": "Regular",
            "sku": "RG-XXXX",
            "pricing_type": "FIXED_PRICING",
            "price_money": {
              "amount": 1999,
              "currency": "USD"
            },
            "track_inventory": true,
            "sellable": true,
            "stockable": true
          }
        }]
      }
    }]
  }]
}
```

### Alternate Item Creation (upsertCatalogObject)

```json
{
  "idempotency_key": "uuid-v4-here",
  "object": {
    "type": "ITEM",
    "id": "#temp-id",
    "present_at_all_locations": false,
    "present_at_location_ids": ["B87BAEZ0NWV34"],
    "item_data": {
      "name": "Product Name",
      "description_html": "<p>Description paragraph one.</p><p>&nbsp;</p><p><b>Condition:</b> Good.</p>",
      "categories": [
        {"id": "TYPE_CATEGORY_ID"},
        {"id": "TIER_CATEGORY_ID"}
      ],
      "reporting_category": {"id": "TYPE_CATEGORY_ID"},
      "tax_ids": ["LPKEJF7H27NOPK7EE6A5CA7V"],
      "is_taxable": true,
      "ecom_visibility": "VISIBLE",
      "variations": [{
        "type": "ITEM_VARIATION",
        "id": "#temp-var-id",
        "present_at_all_locations": false,
        "present_at_location_ids": ["B87BAEZ0NWV34"],
        "item_variation_data": {
          "item_id": "#temp-id",
          "name": "Regular",
          "sku": "RG-XXXX",
          "pricing_type": "FIXED_PRICING",
          "price_money": {
            "amount": 1999,
            "currency": "USD"
          },
          "track_inventory": true,
          "sellable": true,
          "stockable": true
        }
      }]
    }
  }
}
```

### Extracting IDs Robustly

Use this order:
1. `id_mappings` by temp IDs (`#temp-id`, `#temp-var-id`)
2. `batchInsertObjects`: `objects[0].id` and nested variation ID
3. `upsertCatalogObject`: `catalog_object.id` and nested variation ID

### Set Inventory Count (Required after item creation)

**Endpoint:** `inventory.batchChange`

```json
{
  "idempotency_key": "uuid-v4-here",
  "changes": [{
    "type": "PHYSICAL_COUNT",
    "physical_count": {
      "catalog_object_id": "VARIATION_ID",
      "state": "IN_STOCK",
      "location_id": "B87BAEZ0NWV34",
      "quantity": "1",
      "occurred_at": "CURRENT_ISO_TIMESTAMP"
    }
  }]
}
```

**⚠️ Important:** 
- Do NOT include `catalog_object_type` - Square sets this automatically
- Use the VARIATION ID, not the ITEM ID
- `occurred_at` must be within 24 hours and in RFC 3339 format

### Updating Existing Items

When updating, you MUST include the current `version` and use `sparse_update: true`:

```json
{
  "idempotency_key": "uuid-v4-here",
  "sparse_update": true,
  "batches": [{
    "objects": [{
      "type": "ITEM",
      "id": "EXISTING_ITEM_ID",
      "version": 1234567890123,
      "item_data": {
        "categories": [
          {"id": "TYPE_CATEGORY_ID"},
          {"id": "TIER_CATEGORY_ID"}
        ],
        "reporting_category": {"id": "TYPE_CATEGORY_ID"}
      }
    }]
  }]
}
```

### With Images

**⚠️ IMPORTANT - Use square-image-upload skill (MCP), not direct API calls**

Direct API image uploads fail with 403 authentication error. The `SQUARE_ACCESS_TOKEN` lacks image upload permissions.

**Correct approach:** Use the `square-image-upload` skill via MCP, which handles proper authentication and token scopes.

For reference, images must be uploaded separately via `catalog.createCatalogImage` (MCP will handle this):

```json
{
  "idempotency_key": "uuid-v4-here",
  "image": {
    "type": "IMAGE",
    "id": "#temp-image-id",
    "image_data": {
      "name": "Product Image",
      "caption": "Front view"
    }
  },
  "object_id": "EXISTING_ITEM_ID"
}
```

## Payment Links

### Endpoint
`checkout.createPaymentLink`

### Quick Pay (Simple)

```json
{
  "idempotency_key": "uuid-v4-here",
  "quick_pay": {
    "name": "Item Name",
    "price_money": {
      "amount": 1999,
      "currency": "USD"
    },
    "location_id": "B87BAEZ0NWV34"
  },
  "checkout_options": {
    "ask_for_shipping_address": true
  }
}
```

### Response

```json
{
  "payment_link": {
    "id": "LINK_ID",
    "url": "https://square.link/u/XXXXXXXX",
    "long_url": "https://checkout.square.site/merchant/..."
  },
  "related_resources": {
    "orders": [{ "id": "ORDER_ID" }]
  }
}
```

## Useful Queries

### List All Items
```
catalog.listCatalog with types: ["ITEM"]
```

### Search by SKU
```
catalog.searchCatalogItems with text_filter containing SKU
```

### Get Item Details
```
catalog.retrieveCatalogObject with object_id
```

## Price Formatting

- Prices in **cents** (integer)
- $19.99 = `1999`
- $5.00 = `500`
- Always USD for Richmond General
