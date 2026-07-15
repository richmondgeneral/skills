---
name: storefront-sort-default
description: Walk the user through changing the default product sort order on the Square Online Shop All page (e.g., Featured to Newest). Triggers when the user mentions "default sort", "Featured to Newest", "shop page sort", "items sorted wrong", "change how products are ordered", or any request to control product ordering on the storefront's main shop page. Use this skill instead of attempting the change through Square's REST APIs, which do not expose sort defaults.
---

# Storefront Sort Default

## When to use

The Square Online "Shop All" page defaults to "Featured" sort. For curated retailers this often looks random because the shop owner never set per-item Featured priorities. Users typically want "Newest" (so inventory rotation refreshes the page naturally), "Popularity", or "Price".

Square does not expose this setting through Catalog, Locations, or Sites APIs. It lives in the Square Online editor under the Shop All template's Item List section. This skill drives the user's browser through the click path.

## Prerequisites

- Chrome MCP must be connected. If `mcp__Claude in Chrome__*` tools are deferred or unavailable, ask the user to open Chrome and connect the extension before proceeding.
- The user must be signed into Square in Chrome.

## Procedure

### Step 1: identify the target site

Call the Sites API to list the user's Square Online sites:

```
service: sites
method: list
request: {}
```

Present the sites as a numbered list and ask the user which one to update. Capture the `site_id` (format: `site_<digits>`) and the `domain` for the rest of the walkthrough.

### Step 2: get the user's Square user ID

The editor URL needs the user's numeric Square user ID. Get it by:

1. Calling `mcp__Claude in Chrome__tabs_context_mcp` to see if the user has a Square dashboard tab open. URLs like `https://square.online/app/home/users/<USER_ID>/sites/...` contain the user ID.
2. If no dashboard tab exists, ask the user to open `https://square.online/` once and confirm. Then re-read the tabs context.

### Step 3: offer the walkthrough format

Use the AskUserQuestion tool to ask whether the user wants:

- **Interactive walkthrough**  -  Claude drives the browser via teach mode, highlighting each click. (Recommended.)
- **Plain text instructions**  -  just print the click path and let the user do it.

### Step 4a: interactive walkthrough (teach mode)

Use `mcp__computer-use__request_teach_access` for Chrome, then drive the user through these steps with `teach_step` or `teach_batch`:

1. Navigate to `https://square.online/app/website/users/{USER_ID}/sites/{SITE_ID}/dashboard/editor` and wait for the editor canvas to fully render (about 5 seconds).
2. Click the **page selector dropdown** at the top-left of the editor sidebar (currently shows "Home").
3. In the dropdown, scroll down to the **Category pages** section and click **Shop All**.
4. In the left sidebar, click the **Item list** section. **Important**: Do NOT click anything labeled "Set as homepage"  -  Square Online's editor occasionally offers this on click-and-hold of sidebar items. Click once cleanly.
5. In the Item list settings panel that opens, locate the **Default sort** dropdown.
6. Select the user's preferred option (typically Newest).
7. Click **Publish** in the top-right corner to push the change live.

### Step 4b: plain-text instructions

If the user picked plain text, output:

```
1. Open: https://square.online/app/website/users/{USER_ID}/sites/{SITE_ID}/dashboard/editor
2. Click the page dropdown at the top-left (it currently says "Home")
3. Under "Category pages", click "Shop All"
4. In the left sidebar, click "Item list"
5. Find the "Default sort" dropdown in the settings panel
6. Change it to your preferred option (Newest is most common)
7. Click "Publish" in the top-right
```

### Step 5: verify

After the user confirms they've published, navigate the public-facing tab to `https://{domain}/s/shop` and screenshot. Confirm the Sort dropdown now shows the new default.

## Caveats

- The editor autosaves on every change, but autosave is not the same as published. The change only goes live after clicking **Publish**.
- Category pages (like `/shop/wellness-apothecary/...`) have their own sort defaults that are separate from Shop All. If the user wants those changed too, repeat steps 4-5 for each category-page template.
- Some Item list options (like "Featured" priority weights) are stored per-item in the Catalog API. Mention this if relevant.

## Related

- `storefront-hero-tiles`  -  for adding a curated tile section above the product grid (often paired with switching sort to Newest).
- `storefront-publish-categories`  -  for fixing 404s on newly created categories before they can be sorted.
