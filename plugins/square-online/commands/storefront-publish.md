---
description: Publish newly created Square catalog categories to the storefront navigation
---

Invoke the `storefront-publish-categories` skill from this plugin.

Pass through any user arguments (e.g., specific category names that should appear in the nav). The skill will:
1. Query the Catalog API for top-level categories and identify which ones may not yet be in the published nav.
2. Ask the user to confirm which categories should be in the top-level storefront menu.
3. Drive the user through the Square Online editor's Site design -> Navigation flow to add the new categories and remove stale ones.
4. Verify each new category URL resolves on the live site after publishing.

If `mcp__Claude in Chrome__*` tools are not available, ask the user to connect Chrome before proceeding.
