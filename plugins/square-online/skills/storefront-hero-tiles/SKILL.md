---
name: storefront-hero-tiles
description: >-
  Create or update a category-tile hero section above the Shop All product grid on a Square Online
  site using the Snippets API. Triggers when the user mentions "category tiles", "hero section",
  "shop landing page", "/shop is messy", "browse by department", or wants to replace the default
  product grid landing with a curated category navigator. Supports four design variants — text-only,
  subtle background image with cream overlay, dark gradient overlay with white text, and side-by-
  side image and text panel. v0.3.0 adds multi-route support — the same snippet can render different
  hero tile sets on multiple top-level category pages (e.g., a "departments" hero on /shop/the-
  general-store/... in addition to the main /s/shop hero), so each "room" of the storefront has its
  own curated tile-row entry point above the product grid.
---

# Storefront Hero Tiles

## When to use

The default Square Online `/s/shop` page shows all products in a single grid sorted by "Featured". For curated retailers this looks like catalog dump. A category-tile hero (4-8 tiles linking to the main departments) above the grid gives shoppers a clear entry point.

This skill uses Square's **Snippets API** to inject a `<style>` block plus a `<script>` block into every page of the site. The script detects matching routes at runtime and inserts a tiles section as the first child of `<main>`.

Routes the script handles:

- `/s/shop` — main shop landing. Always supported. Tile set = top-level "rooms" of the storefront (Apothecary Cabinet, General Store, Vintage Market, Real Rarities, etc.).
- `/shop/{slug}/{category_id}` — top-level category pages that have meaningful sub-departments (e.g., The General Store → Wellness, Gifts, Books, Pottery, Food, Home). Optional, per-route opt-in. Each route gets its own tile array and title strings.

In addition, the CSS layer restyles Square's native subcategory tiles on category pages (`/shop/{slug}/{id}`) to match the hero treatment — so the look stays consistent as users drill into departments. When a hero is injected on a route, the native subcategory tile grid is hidden via the `body.rg-hero-active` class so users don't see duplicate tile rows.

No dashboard interaction required.

## Design variants

The skill ships four visual treatments. Pick by content fit rather than personal preference  -  each suits different storefront aesthetics:

| Variant | Look | Best for |
|---|---|---|
| **A  -  Text only** | Clean cream cards, serif type, no imagery | Pure typographic / editorial brands |
| **B  -  Subtle background image** | Category image at low visibility under a cream overlay (default 78% opacity, tunable 60-88%) | Curated retailers that want visual variety per tile without losing the typographic identity. **Recommended default.** |
| **C  -  Dark gradient overlay** | Image fills the tile, dark gradient at the bottom, white text bottom-aligned | Editorial / magazine-cover feel. Best when images are strong and full-bleed. |
| **D  -  Side image + text panel** | ~38% of the tile is image on the left, text panel on the right, tighter 5:3 aspect | Tighter "thumbnail" feel. Best for shops with many tiles or smaller screens. |

## Prerequisites

- Square Snippets API access (currently early-access program  -  confirm with `mcp__mcp_square_api__get_service_info` `service=snippets`).
- A list of categories the user wants featured. Use Catalog API `searchObjects` with `object_types=["CATEGORY"]` to enumerate top-level categories.
- For variants B / C / D: each tile's category must have at least one `image_ids[0]` set, OR be linked to an item whose first image we can borrow. See "Fetching tile image URLs" below.

## Procedure

### Step 1: identify the target site

Use the Sites API to list sites; ask the user which one.

```
service: sites, method: list, request: {}
```

Capture the `site_id`.

### Step 2: check for existing snippet

```
service: snippets, method: get, request: {"site_id": "<SITE_ID>"}
```

If `NOT_FOUND` -> first install. If existing -> parse the JS tile array and current variant to offer "what do you want to change?" instead of re-running the whole flow.

### Step 3: enumerate categories and let the user pick tiles

```
service: catalog, method: searchObjects, request: {"object_types": ["CATEGORY"], "limit": 100}
```

Present `is_top_level: true` categories. Have them pick **4-8 tiles** in order, each with a 3-6 word tagline.

For each tile, build the URL as `/shop/{slug}/{category_id}`. The slug is auto-generated from the category name (lowercase, hyphens for spaces).

### Step 4: pick the design variant

Use AskUserQuestion to offer A/B/C/D with one-sentence descriptions. Default to B.

If B is chosen, ask about overlay intensity:
- Whisper (88% overlay)  -  image barely visible
- Soft (78% overlay)  -  recommended default
- Bold (60% overlay)  -  image dominates

### Step 5: fetch tile image URLs (variants B / C / D only)

For each tile's category, get `category_data.image_ids[0]`. If missing, fall back to a representative item in that category  -  pick the first item with `image_ids[0]` set.

Then fetch the actual image URLs via:

```
service: catalog, method: batchGetobjects, request: {"object_ids": ["<imageId1>", "<imageId2>", ...]}
```

Each returned object has `image_data.url`  -  a public S3 URL that works in CSS `background-image`.

If a category has no image and no items with images, fall back to variant A styling for that tile only (or warn the user).

### Step 6: build the snippet content

Generate one HTML string with `<style>` + `<script>` blocks. See `references/variant-templates.md` for the exact CSS/JS for each variant.

Common requirements for all variants:
- Tiles array as `[{n, t, u, i}]` where `i` is the image URL (or `null` for variant A)
- A `route()` function that maps `location.pathname` to `{tiles, title, sub, key}` or `null` (see "Multi-route configuration" below)
- Idempotent across SPA navigation — `#rg-hero` carries a `data-rg-route` attribute; `build()` skips work when the existing hero already matches the current route
- Toggle `body.rg-hero-active` class on/off so the companion CSS hides Square's native subcategory tiles only when we have our own hero on screen
- Retry at 600ms, 1500ms, 3000ms for slow SPA renders
- Watch SPA route changes via `setInterval(w, 400)` polling
- Mobile breakpoint at `@media(max-width:600px)` → 2-column grid, square aspect, smaller font

Max content length: 65,535 chars (well within budget for typical tile counts).

### Multi-route configuration

The `route()` function is the single source of truth for "which tile set, on which URL." Each route returns `{tiles, title, sub, key}` where:

- `tiles` — the array of tile dicts for that route
- `title` — the hero `<h2>` text
- `sub` — the small subtitle paragraph below the title
- `key` — short identifier ("top", "gs", "vm", etc.) stored on the hero as `data-rg-route` for idempotency

Pattern:

```js
function route(){
  if(/^\/s\/shop\/?$/.test(location.pathname))
    return {tiles:T, title:'Welcome to Richmond General', sub:'Pick a room of the store to explore', key:'top'};
  if(/^\/shop\/the-general-store\/QLM2GZ643LOCYHB653YIDJWT\/?$/.test(location.pathname))
    return {tiles:G, title:'The General Store', sub:'Browse by department', key:'gs'};
  if(/^\/shop\/the-vintage-market\/TX6SBQLJDMZOCVXBUD3KT3CL\/?$/.test(location.pathname))
    return {tiles:V, title:'The Vintage Market', sub:'Browse by department', key:'vm'};
  return null;
}
```

Each route's regex must include the category ID for safety — `/shop/the-general-store/` alone could match unintended sub-paths. The ID anchors the route.

`build()` checks `existing.getAttribute('data-rg-route')` before rebuilding — if it matches the current route's `key`, no work is done. If it differs, the existing hero is removed and rebuilt. This keeps the script idempotent across SPA navigation between routes.

### Step 7: confirm before deploying

Show the user:
- Tile list (name, tagline, url, image fallback if any)
- Chosen variant and intensity
- Total snippet size

Only proceed on explicit "yes".

### Step 8: deploy

```
service: snippets, method: upsert, request: {
  "site_id": "<SITE_ID>",
  "snippet": {"content": "<full HTML string>"}
}
```

Capture the returned `snippet.id` (e.g., `snippet_<uuid>`). Note this is stable per-application across upserts  -  same ID returned on update.

### Step 9: verify on the live site

Navigate Chrome to `https://{domain}/s/shop`, wait ~6 seconds for the script to inject + image loads, screenshot. Confirm with the user that the tiles render correctly and images load.

## Updating an existing hero

If retrieving the snippet in Step 2 returns existing content, parse the tiles array and offer targeted edits:

- "Change a tile's tagline / URL"
- "Swap an image"
- "Change the variant" (re-run Step 4)
- "Add or remove a tile"
- "Add a new sub-page hero" (see below)

The Snippets API `upsert` replaces the entire snippet content  -  you must include all tiles + all styling in every update, not just the diff.

## Adding a new sub-page hero (multi-route extension)

When a user wants to extend an existing hero to also fire on a sub-page like `/shop/the-vintage-market/...`:

1. Confirm the sub-page is a top-level category with meaningful sub-departments. Flat categories (no children) don't benefit — the hero would just duplicate the product grid that's already there.
2. Enumerate the sub-categories you want to tile. Build a new array (e.g., `V` for Vintage Market) in the same `[{n, t, u, i}]` shape as the existing `T` array.
3. For categories without `image_ids`, fall back to borrowing an item's image (per Step 5 of the main procedure).
4. Add a new route to the `route()` function with a unique `key` (e.g., `'vm'`).
5. Upsert the snippet. The CSS layer's `body.rg-hero-active` rule will automatically hide Square's native subcategory tiles on that route so users don't see duplicate tile rows.

Routes are cheap to add — each one is ~3 lines in the script. Six routes for a six-room storefront is comfortable.

**Don't add a hero route for:**

- Flat tier categories like Real Rarities, New Finds, New Arrivals — they have no sub-departments and a product grid is the right UX.
- Sub-categories themselves (e.g., `/shop/wellness-apothecary/...`) — they're leaf nodes. Users have already drilled down.
- Categories with only one or two sub-categories — a 1-2 tile hero looks empty. Either consolidate or skip.

## Removing the hero

```
service: snippets, method: delete, request: {"site_id": "<SITE_ID>"}
```

This removes the entire snippet (including any unrelated code in it). Confirm with the user first if the snippet contains tracking, third-party widgets, etc.

## Caveats

- Snippet replaces the entire injected snippet  -  preserve any unrelated code when updating.
- Snippets inject into `<head>`, script runs after Square's SPA renders. Brief flash possible on slow connections  -  multiple retry timers mitigate.
- Variant B's overlay can cause subtle image bleed on the cream  -  test on the user's actual brand colors.
- Variant C with white text may fail accessibility contrast on very light category images. Recommend variant A or B for those cases.
- Variant D's tighter aspect ratio (5:3) may clip tall portrait images  -  center-crop is enforced via `background-position: center`.
- Image URLs from `image_data.url` are signed S3 paths that don't expire (CatalogImage objects are immutable). Safe to embed in snippet content.
- New categories must be published to the storefront nav first (see `storefront-publish-categories`)  -  otherwise tile URLs return 404.

## v0.2.1  -  subcategory tile restyling on category pages

The skill ships an additional CSS-only layer that targets Square's native subcategory tiles on `/shop/{slug}/{id}` pages and restyles them to match the variant chosen for the hero. The selectors are:

- `a.sub-category-group__link`  -  the outer tile anchor
- `.figure__aspect-ratio` + nested `<img>`  -  the category's image (rendered by Square as an `<img>` tag, not a background-image)
- `.sub-category-title__padding p`  -  the category title text
- `.content-grid.tight-grid:has(a.sub-category-group__link)`  -  the grid container (uses `:has()`  -  modern browsers only)

This rewrites Square's default rendering (image on top, text below) into a unified tile (image fills the card, cream overlay, title centered on top). The same pattern applies at any depth of category nesting since Square uses the same DOM structure across category pages.

The subcategory CSS lives in the same `<style>` block as the hero CSS and is appended after the hero rules. See `references/variant-templates.md` section "Subcategory tile overrides" for the exact CSS.

## v0.3.0 — multi-route hero injection

Adds support for injecting different hero tile sets on multiple top-level category pages, not just `/s/shop`. Use case: a storefront with several "rooms" (Apothecary Cabinet, General Store, Vintage Market, etc.) where each room has its own departments that deserve curated tile-row entry points.

What changed from v0.2.1:

- `on()` function (single-route regex) replaced by `route()` function returning `{tiles, title, sub, key}` or `null` (see "Multi-route configuration" in the procedure section).
- Hero element carries `data-rg-route` attribute so `build()` is idempotent across SPA navigation between routes.
- New `body.rg-hero-active` class toggled on/off by `build()` — paired with a CSS rule that hides Square's native subcategory tile grid (`.content-grid.tight-grid:has(a.sub-category-group__link)`) when our hero is on screen, eliminating duplicate tile rows on top-level category pages with sub-categories.
- Multiple tile arrays in the same snippet (e.g., `T` for top, `G` for General Store, `V` for Vintage Market) — each one is one of the existing variant shapes; you can mix variants across routes if desired (rare, but supported).

Adding a fourth route is a 3-line script edit + a new tile array. See "Adding a new sub-page hero" above for the procedure.

## Related

- `storefront-publish-categories`  -  ensure tile destination URLs resolve.
- `storefront-sort-default`  -  usually paired with hero tiles to give the underlying product grid a sensible default (Newest).
