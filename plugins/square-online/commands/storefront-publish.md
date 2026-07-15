---
description: Publish newly created Square catalog categories to the storefront (API-only channel add)
---

Invoke the `storefront-publish-categories` skill from this plugin.

Pass through any user arguments (e.g., specific category names/ids). Publishing is **API-only**
— no dashboard editor, no Chrome required:

1. Query the Catalog API for the target categories and inspect `category_data.channels` —
   an unpublished category carries only the 1 base/POS channel; working categories carry 6.
2. Read the 5 Square Online channel ids from a known-working category.
3. Add them with ONE `catalog.batchUpdateObjects` **sparse update** (`sparse_update: true`,
   sending only `{type, id, version, category_data: {channels}}`) — `CatalogCategory.channels`
   is writable and propagates instantly.
4. Verify each category URL resolves on the live site **in a real browser** — the SPA returns
   HTTP 200 then client-404s, so curl cannot confirm. (Browser = verification only, optional.)

⚠️ If the category is `is_deleted: true`, this is NOT a publish problem — it's a stale hero
tile pointing at a removed category; repoint the tile in
`brand/storefront/richmondgeneral-shop-snippet.html` (snippets.upsert) instead.
