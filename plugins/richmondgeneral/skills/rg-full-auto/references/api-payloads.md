# Square API Payloads

JSON payload templates for Phase 2 (catalog creation), Phase 3 (inventory), and Phase 5 (payment links).

## Phase 2: Catalog Creation

### Payload A: `batchInsertObjects` (the create path)

```json
{
  "idempotency_key": "rg-XXXX-create-TIMESTAMP",
  "batches": [{
    "objects": [{
      "type": "ITEM",
      "id": "#RG-XXXX",
      "present_at_all_locations": false,
      "present_at_location_ids": ["B87BAEZ0NWV34"],
      "item_data": {
        "name": "Item Title",
        "description_html": "<p>First paragraph.</p><p>&nbsp;</p><p>Second paragraph.</p><p>&nbsp;</p><p><b>Condition:</b> Good. Notes here.</p>",
        "categories": [
          {"id": "TYPE_CATEGORY_ID"},
          {"id": "TIER_CATEGORY_ID"}
        ],
        "reporting_category": {"id": "TYPE_CATEGORY_ID"},
        "tax_ids": ["LPKEJF7H27NOPK7EE6A5CA7V"],
        "is_taxable": true,
        "ecom_visibility": "VISIBLE",
        "ecom_seo_data": {
          "page_title": "[Era] [Item] - [Feature] | Richmond General",
          "page_description": "Keyword-rich, ends with Richmond, IL",
          "permalink": "lowercase-hyphenated-slug"
        },
        "variations": [{
          "type": "ITEM_VARIATION",
          "id": "#RG-XXXX-var",
          "present_at_all_locations": false,
          "present_at_location_ids": ["B87BAEZ0NWV34"],
          "item_variation_data": {
            "item_id": "#RG-XXXX",
            "name": "Regular",
            "sku": "RG-XXXX",
            "pricing_type": "FIXED_PRICING",
            "price_money": {"amount": 1999, "currency": "USD"},
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

> **No `upsertCatalogObject` fallback.** The Square MCP catalog service exposes
> `batchInsertObjects` / `batchUpdateObjects` / `batchGetobjects` /
> `batchDeleteobjects` / `searchObjects` / `searchItems` / `list` — there is **no**
> `upsertCatalogObject` (nor `batchUpsertObjects`) method. Payload A is the only
> create path: a single item is just a one-element `objects` array (each batch is
> inserted all-or-nothing). To **update** an existing item, use
> `batchUpdateObjects` with `sparse_update: true` (see the update payload in
> `references/square-catalog.md`).

### Capture IDs from Response

In order of reliability:

1. Prefer `id_mappings` lookup by temp IDs:
   - `#RG-XXXX` -> CATALOG_ITEM_ID
   - `#RG-XXXX-var` -> VARIATION_ID
2. If no mappings:
   - `batchInsertObjects`: `objects[0].id` and `objects[0].item_data.variations[0].id`
3. If variation ID is still missing, call `batchGetobjects` (with `include_related_objects: true`) and resolve by SKU.

---

## Phase 3: Inventory (`batchChange`)

```json
{
  "idempotency_key": "rg-XXXX-inv-TIMESTAMP",
  "changes": [{
    "type": "PHYSICAL_COUNT",
    "physical_count": {
      "catalog_object_id": "VARIATION_ID_FROM_PHASE_2",
      "location_id": "B87BAEZ0NWV34",
      "quantity": "1",
      "state": "IN_STOCK",
      "occurred_at": "CURRENT_ISO_TIMESTAMP"
    }
  }]
}
```

**Notes:**
- `quantity` is a STRING, not integer
- `occurred_at` must be a current ISO 8601 timestamp (within 24 hours) -- generate dynamically
- Do NOT include `catalog_object_type` -- Square rejects it as a write-only field

---

## Phase 5: Payment Link (`createPaymentLink`)

### For shippable items:

```json
{
  "idempotency_key": "rg-XXXX-pay-TIMESTAMP",
  "quick_pay": {
    "name": "Item Title",
    "price_money": {"amount": 1999, "currency": "USD"},
    "location_id": "B87BAEZ0NWV34"
  },
  "checkout_options": {
    "ask_for_shipping_address": true
  }
}
```

### For pickup-only items:

```json
{
  "idempotency_key": "rg-XXXX-pay-TIMESTAMP",
  "quick_pay": {
    "name": "Item Title",
    "price_money": {"amount": 1999, "currency": "USD"},
    "location_id": "B87BAEZ0NWV34"
  },
  "checkout_options": {
    "ask_for_shipping_address": false
  }
}
```

**Capture:** `payment_link.url` -> `https://square.link/u/XXXXXXXX`
