---
name: square-inventory-loss
description: Records inventory loss in Square POS at Richmond General as a properly-classified WASTE adjustment with a structured reference_id, then updates the local audit ledger so promotional giveaways, spoilage, damage, theft, and unexplained loss roll up separately for P&L and marketing-cost reporting. Use this skill whenever the user mentions giving away product (samples, demos, freebies, promo, sampling, gift-with-purchase, "comped these", "those got given out"), or writing off product that expired, spoiled, melted, was dropped, damaged, stolen, or "lost" — even casual phrasings like "those went bad", "that case got dropped", "mark them as a loss", "remove these from stock". Also trigger on "stock loss audit", "reconcile inventory", "write off", "shrinkage", or any phrase that means stock needs to leave inventory without being sold. Do NOT use for actual sales (Square records those automatically via orders — and for unique GitHub-Pages-listed items that sell off-storefront, use rg-item-mark-sold to retire the listing and kill the Square payment link) or for inventory transfers between locations.
---

# Square Inventory Loss — Richmond General

Records a non-sale inventory removal in Square and keeps the audit ledger in sync. The goal is that every unit that leaves stock without being sold gets classified into one of five buckets (promo, spoilage, damage, theft, unexplained) so the books can split marketing expense from operational shrinkage.

**Why this matters:** Square's Inventory API has exactly one "loss" state — `WASTE`. There is no native distinction between "I gave 12 bags away to drive trial of a new product" (marketing expense) and "12 bags expired on the shelf" (shrinkage). Both look identical in Square reports. The convention below — encoded in the `reference_id` of every adjustment — is what makes the split possible after the fact.

## Constants for this location

- **Square location_id:** `B87BAEZ0NWV34` (Richmond General — only location)
- **Ledger path:** `/Users/scottybe/workspace/richmondgeneral/inventory-waste-ledger.md`
- **Square MCP tools assumed available:**
  - `mcp__mcp_square_api__make_api_request` (with service/method pairs below)

## Classification convention

Every WASTE adjustment must carry a `reference_id` with one of these prefixes:

| Prefix | When to use | Books treatment |
|---|---|---|
| `PROMO_<campaign-or-date>` | Giveaways, samples, demos, GWP, "comped" | Marketing expense |
| `SPOILAGE_<date>` | Expired, melted, opened, otherwise not sellable | COGS — shrinkage |
| `DAMAGE_<date>` | Dropped, packaging compromised, customer-damaged | COGS — shrinkage |
| `THEFT_<date>` | Confirmed theft | COGS — shrinkage |
| `LOSS_<date>` | Unexplained / catch-all when reason isn't clear | COGS — shrinkage |
| `RECONCILE_LATE_SALE_<orig-year>` | Item actually sold in-store but never decremented at the right SKU (so it lingers in inventory / still shows online) — revenue was already booked under a generic SKU or category in the original year | No new books impact |

Suffix is normally a date (`YYYY-MM-DD`). For promo campaigns with a name, use both: `PROMO_2026-05-11_TALLOW_LAUNCH`. For reconciliations, use the year the sale actually happened: `RECONCILE_LATE_SALE_2025`.

**If the user is ambiguous about reason, ask.** "Did this get given away (promo), expire (spoilage), get dropped (damage), already sell but wasn't rung up at this SKU (reconcile), or you're not sure (loss)?" The classification is the whole point — guessing wrong defeats the purpose.

**RECONCILE_ has one extra check.** Before using it, confirm the original sale revenue actually was captured somewhere in the books (a generic category, an "Other" SKU, an off-Square invoice). If it wasn't — i.e., it was an unrecorded cash sale — recording it as `RECONCILE_*` would hide an unbooked sale. In that case, treat it as a real SOLD adjustment instead (use `to_state: SOLD` with `total_price_money` set to the catalog price), and tell the user the revenue will land on today's date, not the original sale date.

## The workflow

Follow these steps for every loss event. Don't skip steps 2 and 6 — the count check prevents over-writing-off, and the ledger update prevents data drift.

### Step 1 — Identify the item(s) and capture everything you'll need later

Search Square's catalog. Accept any of: item name, partial name, SKU, UPC.

```
mcp__mcp_square_api__make_api_request(
  service="catalog", method="searchItems",
  request={"text_filter": "<user's search string>", "limit": 10}
)
```

**Capture all of this from the response and hold it in working memory for the rest of the workflow** — `searchItems` returns everything you need; the later inventory endpoints do not return cost or name data, so re-fetching costs an extra API call you can avoid.

For each variation involved in the loss event, record:

| Field to capture | Source path in `searchItems` response | Used in step |
|---|---|---|
| `variation_id` | `items[].item_data.variations[].id` | 2, 4 |
| Parent item name | `items[].item_data.name` | 6, 7 |
| Variation name | `items[].item_data.variations[].item_variation_data.name` | 6, 7 |
| SKU or UPC | `items[].item_data.variations[].item_variation_data.sku` or `.upc` | 6 |
| `default_unit_cost.amount` (cents) | `items[].item_data.variations[].item_variation_data.default_unit_cost.amount` | 6 |

Use the `ITEM_VARIATION` id, not the parent item id — `NOT_FOUND` errors in step 4 are almost always because the parent item id was used by mistake. If there's ambiguity (e.g., multiple variations match the search), surface the candidates and have the user pick before proceeding.

### Step 2 — Confirm current state

Always pull current counts before adjusting. This catches the case where someone already wrote them off, and it gives you the upper bound on quantity.

```
mcp__mcp_square_api__make_api_request(
  service="inventory", method="batchGetcounts",
  request={
    "catalog_object_ids": ["<variation_id_1>", "..."],
    "location_ids": ["B87BAEZ0NWV34"]
  }
)
```

If `IN_STOCK` is already 0, stop and tell the user — don't create a meaningless adjustment.

### Step 3 — Classify

Pick the prefix from the table above based on what the user described. Build the `reference_id`:

- "we gave them out as samples" → `PROMO_<today's date>` or `PROMO_<campaign>_<date>`
- "they expired" / "went stale" → `SPOILAGE_<today>`
- "it got dropped" → `DAMAGE_<today>`
- "we know stuff is missing" → `THEFT_<today>`
- not clear → ask, or use `LOSS_<today>` and flag in the ledger

### Step 4 — Apply the adjustment

Use `BatchChangeInventory` with one `ADJUSTMENT` per variation. Critical gotchas baked into this template:

- **Omit `catalog_object_type`** from the adjustment object. It looks tempting to set `"ITEM_VARIATION"` but Square rejects the request — it's a read-only response-only field. (We hit `UNEXPECTED_VALUE` error here in initial testing.)
- **`occurred_at`** must be an RFC 3339 timestamp within the last 24 hours and not in the future. Today's date at noon UTC is a safe default if you don't have a precise time.
- **`idempotency_key`** must be a UUID string. Generate one fresh per call (don't reuse).
- **`from_state` is `IN_STOCK`** and **`to_state` is `WASTE`** for every loss reason — the classification lives in `reference_id`, not the state.
- **`ignore_unchanged_counts: true`** is safe and recommended.

```
mcp__mcp_square_api__make_api_request(
  service="inventory", method="batchChange",
  request={
    "idempotency_key": "<fresh UUID>",
    "ignore_unchanged_counts": true,
    "changes": [
      {
        "type": "ADJUSTMENT",
        "adjustment": {
          "reference_id": "<PREFIX>_<date or campaign>",
          "from_state": "IN_STOCK",
          "to_state": "WASTE",
          "location_id": "B87BAEZ0NWV34",
          "catalog_object_id": "<variation_id>",
          "quantity": "<number as string>",
          "occurred_at": "<YYYY-MM-DDT12:00:00Z>"
        }
      }
    ]
  }
)
```

For multi-item events (e.g., a vendor demo handing out 3 different chip flavors), put all the variations into one `changes` array — one API call, one idempotency key, one ledger event.

### Step 5 — Verify

The `batchChange` response contains updated `counts`. Confirm:
- The targeted variation(s) now show `IN_STOCK` reduced by the adjustment quantity.
- A new `WASTE` count appears (or increases) by the same amount.

The response also echoes back the `adjustment_id`s — capture them. They go in the ledger.

### Step 6 — Update the ledger

Append a row to `/Users/scottybe/workspace/richmondgeneral/inventory-waste-ledger.md` under the "Going-forward entries" table. One row per adjustment.

**All the row fields come from data you captured in earlier steps — do not make new API calls here:**

| Ledger column | Source |
|---|---|
| Adjustment ID | Step 5 response (`changes[].adjustment.id`) |
| Date | The `occurred_at` you used in step 4, in `YYYY-MM-DD` form |
| Item | "Parent item name — Variation name" from step 1 |
| SKU/UPC | From step 1 |
| Qty | The quantity you passed in step 4 |
| Unit cost | From step 1's `default_unit_cost.amount`, divide by 100 |
| Total cost | `unit_cost_cents × quantity ÷ 100` |
| reference_id | The string you built in step 3 |

If you find yourself reaching for another `searchItems` or `batchGetobjects` call at this stage, stop — that means step 1 was incomplete. Go back and capture what's missing, then proceed.

After appending the row, update the "Rollup" totals at the bottom of the ledger so the running classification totals stay accurate.

### Step 7 — Confirm to the user

Tell the user, in this shape:
- What was adjusted (item names + quantities)
- The classification used and its `reference_id`
- The total cost moved to WASTE (so they see the books impact)
- That the ledger is updated

## When the user only gives you a name and no quantity

If the user says "write off the rest of the X" or "we gave away all the remaining Y", default to the full current IN_STOCK count from step 2. Confirm that number back to them before adjusting if it's larger than ~12 units or worth more than ~$50 — those magnitudes feel like things worth a sanity check.

If the user gives a quantity larger than IN_STOCK, stop and surface the mismatch. Don't try to be clever and adjust the available amount silently.

## When something goes wrong

- **`UNEXPECTED_VALUE` on `catalog_object_type`:** you set the field. Remove it from the adjustment object.
- **`INVALID_TIME` on `occurred_at`:** timestamp is more than 24h old or in the future. Use today's date.
- **`NOT_FOUND` on catalog_object_id:** the variation id is wrong (you may have grabbed the parent item id instead). Re-run `searchItems` and look at the nested `variations[].id`.
- **Adjustment posted but ledger update failed:** the Square record is authoritative and immutable. Just retry the ledger append — don't try to "undo" the Square adjustment.

## Edge cases worth knowing

- **No locations other than B87BAEZ0NWV34 exist.** If the user mentions a different location, ask — don't make one up.
- **Square's Dashboard "Mark as Loss" UI uses Reasons (Damage / Theft / Spoilage / Other) that are not exposed via the API.** If a cashier marks loss in the POS, those entries show up in our `batchGetchanges` queries with no `reference_id` set. Those should be retro-tagged in the ledger (see the "Legacy reclassifications" section there) but cannot be edited at the API level.
- **Don't write `to_state: SOLD` with `total_price_money: 0` to "comp" giveaways.** It distorts transaction counts and sell-through. Always use `WASTE` + `PROMO_` reference_id instead.
