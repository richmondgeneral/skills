# Square Catalog API Reference

## Location & Merchant IDs

- **Location ID:** B87BAEZ0NWV34 (Richmond General - ACTIVE)
- **Merchant ID:** 7MM9AFJAD0XHW

## Categories

### Required Categories (ALL items must have BOTH)

| Category | ID | Purpose |
|----------|----|---------|
| **Timeless Treasures** | `3N3II4W6Q7AA43RWQGEEWELY` | Main vintage/antique category |
| **The New Finds** | `P34KX3L7XRZJJ5RP6W35K4YO` | **REQUIRED** for all new items |

### Reporting Category

- **MUST be set** for items to appear in Category Sales reports
- Use `The New Finds` (`P34KX3L7XRZJJ5RP6W35K4YO`) as the reporting category
- If not set via API, item won't be attributed to any category in reports

### Tax ID
- **IL State + Richmond Local (8.5%):** `LPKEJF7H27NOPK7EE6A5CA7V`

Query all categories with: `catalog.searchObjects` with `object_types: ["CATEGORY"]`

## Creating Catalog Items

### Endpoint
`catalog.batchInsertObjects` (use `batchUpdateObjects` with `sparse_update: true` for updates)

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
        "description": "Description with <br> for line breaks",
        "categories": [
          {"id": "3N3II4W6Q7AA43RWQGEEWELY"},
          {"id": "P34KX3L7XRZJJ5RP6W35K4YO"}
        ],
        "reporting_category": {"id": "P34KX3L7XRZJJ5RP6W35K4YO"},
        "tax_ids": ["LPKEJF7H27NOPK7EE6A5CA7V"],
        "is_taxable": true,
        "ecom_visibility": "VISIBLE",
        "variations": [{
          "type": "ITEM_VARIATION",
          "id": "#temp-var-id",
          "item_variation_data": {
            "item_id": "#temp-id",
            "name": "Regular",
            "sku": "RG-XXXX",
            "pricing_type": "FIXED_PRICING",
            "price_money": {
              "amount": 1999,
              "currency": "USD"
            },
            "track_inventory": false,
            "sellable": true,
            "stockable": true
          }
        }]
      }
    }]
  }]
}
```

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
          {"id": "3N3II4W6Q7AA43RWQGEEWELY"},
          {"id": "P34KX3L7XRZJJ5RP6W35K4YO"}
        ],
        "reporting_category": {"id": "P34KX3L7XRZJJ5RP6W35K4YO"}
      }
    }]
  }]
}
```

### With Images

Images must be uploaded separately via `catalog.createCatalogImage`:

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
