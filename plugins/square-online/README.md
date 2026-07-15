# Square Online

Manage Square Online storefront operations that aren't covered by Square's REST APIs.

Square's API surface for online stores is incomplete. The Catalog API can create categories, but the storefront won't show them until the navigation is republished in the dashboard. The Locations API can update hours, but the Shop All page's sort default lives in the editor. This plugin fills those gaps  -  two skills use Chrome teach-mode walkthroughs for dashboard-only settings, one skill uses the Snippets API to inject custom HTML/CSS/JS into every page.

## Skills

### `storefront-sort-default`

Walks the user through changing the default product sort on the Shop All page (e.g., Featured -> Newest). Chrome teach-mode walkthrough  -  Square doesn't expose this via API.

**Triggers on:** "default sort", "Featured to Newest", "shop page sort", "items sorted wrong"

### `storefront-publish-categories`

When new categories are created via the Catalog API, the storefront's published navigation cache lags  -  direct URLs return 404 until the nav is republished. This skill walks the user through adding new categories to the menu and publishing.

**Triggers on:** "category 404", "publish category to storefront", "category not showing on site"

### `brand-guidelines` *(v0.3)*

Applies Richmond General's visual identity (colors, typography, component patterns) to anything that needs to look on-brand  -  Square Online storefront snippets, marketing emails, social images, new web pages. Source of truth wrapper around `brand/BRAND.md` in the sibling brand repo.

**Triggers on:** "brand", "make this on-brand", "apply our colors", "Richmond General style", "match the website"

### `brand-voice` *(v0.3, expanded in v0.4)*

Writes or rewrites content in the Richmond General brand voice  -  "curated mercantile". Slightly archaic, intentional, heritage-and-craft-forward. Each item gets a small story; every piece gets provenance and condition stated plainly. Replaces hype-y product descriptions with specific, era-anchored copy.

**v0.4 expansion:** includes `references/anchor-library.md`  -  a catalog of the 60+ cultural and historical anchors actually used in Richmond General descriptions (Victorian apothecaries, Palmer paint-by-number kits, Railway Express Agency 1929-1975, etc.). Reuse anchors across similar items so the catalog reads as one coherent shop.

**Triggers on:** "write a description", "make this sound like us", "on-brand the copy", "rewrite in our voice"

### `catalog-voice-audit` *(v0.4)*

Scans Square catalog item descriptions against the brand voice and flags drift. Identifies hype words, missing era anchors, missing condition information, missing practical use notes, and vendor copy. Returns a prioritized list of items needing rewrite with specific feedback per item.

**Triggers on:** "audit descriptions", "check the catalog voice", "find items needing rewrite", "voice check"

### `catalog-voice-rewrite` *(v0.4)*

Generates new product descriptions in the brand voice for one or more catalog items. Follows the four-part template (form & provenance -> cultural anchor -> condition -> practical close), pulls reusable anchors from the brand-voice anchor library, and batch-updates items via the Catalog API. Includes both `description` and `description_html` for each item.

**Triggers on:** "rewrite this item", "redo the description", "rewrite from vendor copy", "fix the items the audit flagged"

### `storefront-hero-tiles`

Manages the category-tile hero section above the Shop All product grid. Uses Square's Snippets API to inject HTML/CSS/JS without touching the dashboard. Lets users pick 4-8 categories to feature with taglines.

**v0.2  -  four design variants:**
- **A  -  Text only:** clean serif cards, no images
- **B  -  Subtle background image (default):** each tile shows its category image at low visibility under a cream overlay (78% default, tunable)
- **C  -  Dark gradient overlay:** image fills the tile, gradient at the bottom, white text
- **D  -  Side image + text panel:** ~38% image on the left, text on the right, 5:3 aspect

Tile image URLs are pulled from category `image_ids[0]` via `batchGetobjects`. See `skills/storefront-hero-tiles/references/variant-templates.md` for exact CSS/JS templates.

**v0.2.1  -  subcategory tile restyling:** the same variant treatment is applied via CSS overrides to Square's native subcategory tiles on category pages (`/shop/{slug}/{id}`), so the design stays consistent as users drill into departments.

**Triggers on:** "category tiles", "hero section storefront", "shop landing page"

## Commands

- `/storefront-sort`  -  change the default sort on Shop All
- `/storefront-publish`  -  publish new categories to the storefront nav
- `/storefront-hero`  -  manage the category-tile hero section

## Requirements

- A Square account with Square Online sites (the Sites API is used to list available sites).
- For dashboard walkthroughs: Chrome with the Claude in Chrome extension installed.
- For the hero-tiles skill: access to Square's Snippets API (currently in early-access program).

## How it works

Two of the skills are **Chrome teach-mode walkthroughs**  -  they drive the user's browser through the dashboard click paths, because Square doesn't expose the underlying settings via REST. The third skill uses the **Snippets API** to upsert a snippet containing HTML/CSS/JS that's injected into every page's `<head>`. The snippet runs on `DOMContentLoaded` and inserts a category-tiles section at the top of the `/s/shop` page.

## Limitations

- Square's `ecom_visibility` field on catalog items is read-only via the Catalog API, so this plugin can't directly toggle online visibility per-item  -  use the catalog `is_archived` field to hide items completely, or the dashboard for per-channel visibility.
- Snippets API only injects into `<head>`. Server-rendered HTML can't be replaced, only manipulated after the page loads.
- The Snippets API is part of an early-access program; behavior may change.

## Source

This plugin was built for the Richmond General storefront and assumes a similar setup (single merchant, multiple Square Online sites, curated retail).
