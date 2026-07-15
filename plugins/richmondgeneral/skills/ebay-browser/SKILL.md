---
name: ebay-browser
description: >
  Create, revise, and verify Richmond General eBay listings through an authenticated browser session.
  Prefer the current agent's native Chrome integration or computer-use surface: Claude in Chrome,
  Codex Chrome control, or Gemini Spark Chrome auto-browse. Use the existing Playwright seller-agent
  profile only when native browser control is unavailable, disconnected, blocked, or cannot complete a
  required interaction. Use for "list on eBay", "revise eBay", "edit eBay listing", "eBay Seller Hub",
  and browser-created eBay listings. Route Inventory API-managed listings to `ebay-lister` instead.
metadata:
  version: "2.0"
  author: scottybe
  updated: "2026-07-15"
  changelog: |
    v2.0 - Made the workflow agent-neutral: native authenticated Chrome first for Claude, Codex, and
    Gemini Spark; Playwright persistent-profile automation is now the explicit fallback.
---

# eBay Browser Listing

Drive eBay Seller Hub through the best authenticated browser surface already available to the current
agent. Keep field knowledge independent of the browser driver.

## Route before acting

1. Read `items/RG-XXXX/label.json` and inspect `channels.ebay`.
2. If `offer_id` exists or the note says the listing was created through the Sell Inventory API, stop
   this workflow and use `ebay-lister`. eBay does not allow Inventory API listings to be revised in
   Seller Hub.
3. Otherwise treat the listing as browser-managed and select a driver using
   `references/native-surfaces.md`.
4. Prefer native control of the user's authenticated Chrome session. Use
   `references/playwright-fallback.md` only when the native route is genuinely unavailable or fails its
   bounded retry.

## Prepare

- Load title, SKU, price, condition, description, item specifics, shipping intent, and photo paths from
  the item record/listing pack before opening the form.
- Confirm whether the user authorized publishing. Without explicit publish authorization, prepare the
  listing and stop for review.
- For CREATE, search both Active and Drafts before starting so a retry cannot create a duplicate.
- Read `references/field-map.md` for the current create/revise form behavior and verified values.

## Drive the form

- Enter Seller Hub through its normal navigation. Do not deep-link into create/revise forms that have
  previously hung at `document_idle`.
- Prefer semantic browser actions and exact DOM targets. Use coordinate/computer actions only for
  controls that do not respond semantically.
- Treat the form as eventually interactive: take a screenshot after navigation, then edit each field and
  visually read it back before submitting. eBay has swallowed early keystrokes while still rendering.
- Upload photos with the native surface's direct file-upload capability. Preserve the requested order;
  the first photo is the main image.
- If a tab freezes, open one fresh tab and retry through Seller Hub. Do not re-click a frozen **List it**
  button because the first submission may already have succeeded.

## Publish and verify

1. Submit only when publishing is authorized.
2. Capture the success dialog and resulting item ID, but do not treat the dialog as proof that edits
   landed.
3. Open the live `/itm/<itemId>` page in a fresh tab and verify the requested title, price, status, and
   other changed fields.
4. Write the item ID, URL, price, and browser driver used to `channels.ebay` without deleting unrelated
   channel metadata.
5. Propagate shared price/title/description changes to other active channels when the task includes
   cross-channel reconciliation.

## Maintain the workflow

Add only verified, reusable UI behavior to `references/field-map.md`. Keep platform-specific capability
notes in `references/native-surfaces.md` and Playwright mechanics in `references/playwright-fallback.md`.
Edit this canonical repository copy, then rebuild or reinstall the plugin so caches remain derived.
