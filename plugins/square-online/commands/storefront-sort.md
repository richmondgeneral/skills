---
description: Change the default product sort on the Square Online Shop All page
---

Invoke the `storefront-sort-default` skill from this plugin.

Pass through any user arguments (e.g., a target sort value like "Newest" or a specific site name). The skill will:
1. List the user's Square Online sites and ask which one to update.
2. Offer interactive walkthrough (teach mode in Chrome) or plain-text instructions.
3. Drive the user to the Square Online editor's Shop All template, find the Item list section, and change the Default sort dropdown.
4. Verify the change on the live site.

If `mcp__Claude in Chrome__*` tools are not available, surface that to the user and ask them to connect the Claude in Chrome extension before proceeding.
