---
description: Manage the category-tile hero section above the Shop All product grid (uses Square's Snippets API)
---

Invoke the `storefront-hero-tiles` skill from this plugin.

Pass through any user arguments (e.g., a list of categories to feature, custom title/tagline, styling preferences). The skill will:
1. List the user's Square Online sites and capture the target site_id.
2. Check for any existing snippet on that site; update or create-fresh accordingly.
3. Enumerate top-level catalog categories and let the user pick 4-8 to feature, with taglines.
4. Build the snippet content (HTML/CSS/JS) and confirm with the user before deploying.
5. Upsert via the Snippets API.
6. Verify on the live site.

No dashboard interaction required  -  this skill works purely through the Snippets API. The Snippets API requires Square's early-access program access.
