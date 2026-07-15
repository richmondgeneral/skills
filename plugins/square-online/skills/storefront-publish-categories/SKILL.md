---
name: storefront-publish-categories
description: >-
  Publish newly created Square catalog categories to the Square Online storefront. Triggers when
  categories created via the Catalog API return 404 on the storefront, when the user mentions
  "category not showing on site", "new category 404", "publish category to storefront", "storefront
  nav out of date", or when a new category was just created via batchInsertObjects and needs to be
  exposed publicly. The fix is API-only: add the Square Online channel IDs to the category's
  `category_data.channels` via catalog batchUpdateObjects (sparse_update) — no dashboard editor
  required.
---

# Storefront Publish Categories

## When to use

Square's Catalog API creates categories instantly, but a freshly created category carries only the base/POS channel. The result: it returns 404 on `/shop/<slug>/<id>` storefront URLs until the Square Online channel IDs are added to its `category_data.channels`. (The SPA returns HTTP 200 then client-404s, so `curl` cannot confirm the 404 — verify by loading the URL in a real browser.)

Symptoms:
- "I just created a category but the URL returns 404"
- The site's main shop menu still shows old/deleted categories
- New top-level categories don't appear in the storefront nav

**This is fixed with the Catalog API alone — no dashboard editor.** `CatalogCategory.channels` is writable (`readOnly: false`), and adding the Square Online channels propagates to the storefront immediately (no nav republish, no cache-bust). See the Procedure below.

> Note: there is a separate, intentional `category_data.online_visibility: false` flag ("hidden on all Square Online sites", e.g. Food sub-categories). Do **not** conflate it with channel membership — a category can carry the online channels and still be deliberately hidden.

## Prerequisites

- The Square API MCP must be available (`mcp__mcp_square_api__make_api_request`). Square-Version `2026-04-21`.
- The categories must already exist in the Catalog API (verify with `searchObjects` on `object_types=["CATEGORY"]` if uncertain).
- A browser (Chrome MCP) is only needed for the optional Step 4 verification render — the publish itself is API-only.

## Procedure

### Step 1: confirm which categories need publishing

Run a category search to list categories that exist in the catalog but may not carry the Square Online channels yet (`searchObjects` with `object_types=["CATEGORY"]`; pass `include_deleted_objects: true` if you also need to spot deleted ones still referenced elsewhere). Show the user a list:

```
The following categories exist in your catalog:
  1. The Apothecary Cabinet (id: QIPW32HGKMU5BDPU3A7YZCM4, created 2026-05-11)  -  base channel only (not on storefront)
  2. The Gallery (id: UMWTT7Q6UU4PXPUKU3DVNLFJ, created 2026-05-11)  -  base channel only (not on storefront)
  3. Artisan Lighting (id: QL6DE4DZCY5IEMZ7JDULLQLB)  -  subcategory under The Gallery
  ...
```

Ask the user which categories should appear on the storefront. Subcategories appear automatically as dropdown children of their parents.

### Step 2: read the channel set from a category that is already live

Pull the exact `category_data.channels` array from a top-level category that already renders on the storefront (e.g. **The Vintage Market**, id `TX6SBQLJDMZOCVXBUD3KT3CL`) so you copy the precise channel IDs this seller's site uses. A published category carries the base/POS channel **plus the 5 Square Online channels**; a category that only has the base channel `CH_daFuutbKh5TWFcBJOpaUXfeKdLce51PkoMdi3STj9945o` is not on the storefront.

Read with `batchGetobjects` (note the lowercase `o`):

```jsonc
// make_api_request { service: "catalog", method: "batchGetobjects", request: { ... } }
{ "object_ids": ["TX6SBQLJDMZOCVXBUD3KT3CL"], "include_deleted_objects": true }
```

Diagnose the target: `batchGetobjects` it and check `is_deleted` and the length of `category_data.channels` (1 = base only; 6 = published).

### Step 3: add the Square Online channels (the publish)

For each category to publish, write its `channels` array — the **full** 6-channel set copied from Step 2 — back with `batchUpdateObjects` using `sparse_update: true`, sending only `{type, id, version, category_data:{channels:[...]}}`. `CatalogCategory.channels` is writable (`readOnly: false`), and the change propagates to the storefront **immediately** — there is no separate nav-republish or cache-bust step.

```jsonc
// make_api_request { service: "catalog", method: "batchUpdateObjects", request: { ... } }
{
  "idempotency_key": "<uuid>",
  "batches": [{ "objects": [{
    "type": "CATEGORY",
    "id": "QIPW32HGKMU5BDPU3A7YZCM4",
    "version": <latest_version_from_step_2_read>,
    "category_data": { "channels": [ /* the exact 6 IDs from the live category */ ] }
  }]}]
}
```

Keep batches to 10 objects or fewer. Re-read the updated category and confirm `category_data.channels` now has all 6 IDs in the response.

> Do **not** send a non-sparse upsert here — without `sparse_update: true` the write replaces the whole object and can drop fields. (For categories specifically, also never blank `name`/`category_type`/`parent_category`.) Send only the changed `channels`.

### Step 4: verify

Load each category URL `https://{domain}/shop/{slug}/{category_id}` in a real browser (Chrome MCP) — **not** `curl`, which sees the SPA's 200 shell and misses the client-side 404. The slug is derived from the category name (lowercase, spaces and special chars replaced with hyphens). For "The Apothecary Cabinet" with id `QIPW32HGKMU5BDPU3A7YZCM4`, the URL is `/shop/the-apothecary-cabinet/QIPW32HGKMU5BDPU3A7YZCM4`.

Take a screenshot of each verified page and confirm with the user.

## Caveats

- Slugs are auto-generated by Square the first time a category becomes visible online. If a slug collides with an existing one (e.g., recreating a category with the same name as a deleted one), Square appends a suffix.
- Subcategories cascade from their parent in dropdown menus; publishing the parent is what surfaces them.
- The `channels` array is per-Square-Online-site. To show the same category on multiple sites (e.g., Richmond General + Richmond Vintage Market), include each site's channel IDs in the array — adding a site's channels is exactly what publishes the category there. There is no separate manual "add to nav" step.
- `category_data.online_visibility` is a distinct flag (hidden on **all** Square Online sites). A category can carry the online channels yet still be hidden via this flag — check it if a published category still doesn't render.

### Fallback only — dashboard editor

The API channel write above is the supported, immediate way to publish. Only if the Square API is unavailable, walk the user through the dashboard editor manually:

```
1. Open: https://square.online/app/website/users/{USER_ID}/sites/{SITE_ID}/dashboard/editor
2. Click "Site design" (top-left)
3. Click "Navigation" or "Header navigation"
4. For each new top-level category: "Add menu item" -> choose "Category" -> pick it -> Save
5. Remove stale items (deleted categories) by clicking them and choosing "Remove"
6. Click "Done", then "Publish" (top-right)
```

## Related

- `storefront-sort-default`  -  for changing how categories sort after they're published.
- `storefront-hero-tiles`  -  for featuring new categories prominently above the product grid.
