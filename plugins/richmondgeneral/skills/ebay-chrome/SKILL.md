---
name: ebay-chrome
description: Chrome automation patterns for managing eBay (richmondgeneral) listings via the Claude-in-Chrome extension — Seller Hub navigation, the "Revise your listing" form, title/SKU/price fields, the description RTE iframe, item specifics, and the publish ("Revise it") flow. Use for ANY eBay listing create/revise/manage action driven through Claude in Chrome. Triggers on "revise ebay", "edit ebay listing", "update ebay title/description", "ebay seller hub", "fix the ebay listing", "ebay chrome". This is the sanctioned path for eBay browser writes — do NOT use the local seller-agent's Vision Agent for eBay (Gemini-billable, no deterministic fallback; it was hard-down on a 429 on 2026-06-20). For programmatic CREATE of an API-managed item use `ebay-lister` (Sell Inventory API); for allowed field/category values see the field-map reference below.
metadata:
  version: "1.0"
  author: scottybe
  updated: "2026-06-20"
  changelog: |
    v1.0 - Initial extraction from the RG-0023 reconcile (2026-06-20):
    - Seller Hub active-listings entry + search-by-item-number → Edit
    - "Revise your listing" form: title (80 char), Custom label (SKU), price
    - Description RTE iframe (se-rte-frame__summary) interaction + the
      page-level textarea trap (reads Condition description, not the body)
    - Item specifics overview, "Revise it" submit + confirmation dialog
    - Verification gotcha: JS value-reads of title/SKU return wrong nodes
    - Seeded reference/field-map.md (grow this every session)
---

# eBay Chrome Automation

Reusable Claude-in-Chrome primitives for managing Richmond General's eBay listings. This skill owns the
*how* — how to reach and drive eBay's Seller Hub and "Revise your listing" UI. Concrete field names,
selectors, and dropdown values live in **`reference/field-map.md`**, which we **append to every session**
as we learn more of the form (the goal: eventually know every box, dropdown, and what goes where).

## Why the extension (and not the seller-agent) for eBay

- The local **seller-agent** is the right tool for **Facebook Marketplace** (the extension write-path is on
  hold there for permission churn — see `ops/docs/RG-marketplace-chrome-extension-SOP.md`).
- For **eBay** it's the opposite: the Chrome extension drives the deterministic Revise form **with no
  Gemini and no per-action approval prompts** (verified 2026-06-20). The seller-agent's Vision Agent is
  Gemini-billable and was **hard-down on a 429** that day — so **eBay writes go through this skill**.
- `ebay-lister` (Sell **Inventory API**) remains the path for *programmatic create* of an API-managed item.
  Use this skill to **revise/manage listings that live in the browser UI** (most of our hand-created ones).

## Prerequisites

- Claude-in-Chrome MCP tools available; the user signed into eBay as **richmondgeneral**.
- A tab in the MCP group (`tabs_context_mcp{createIfEmpty:true}`).
- **⚠️ Tab IDs change between sessions — never cache them across conversations.**

## Reach the Revise form (do this, not the deep-link)

1. `navigate` → `https://www.ebay.com/sh/lst/active` (Seller Hub → Listings → Active).
2. `find` the search box ("Search by title, SKU, or item number"), click it, type the **item number**,
   press Return.
3. Click the row's **Edit** button → lands on "Revise your listing".

**Do NOT** open `https://www.ebay.com/lstng?...&mode=ReviseItem&itemId=...` directly — the deep-linked draft
has hung the extension at `document_idle` (every later action then times out). Always enter via Seller Hub.

## Editing fields

Standard inputs (title, SKU, price): **click → `cmd+a` → `Backspace` → `type`**. Real keystrokes via the
`computer` tool fire React's onChange; prefer them over JS `.value` assignment.

- **Title** — plain input, **80-char max**. Watch the `NN/80` counter.
- **Custom label (SKU)** — plain input; set to `RG-XXXX`.
- **Item price** — under PRICING; ignore eBay's "Recommended price" suggestion (use the BPO price).
- **Description** — an **eBay RTE iframe** (`id="se-rte-frame__summary"`, title "Description"), NOT a
  page-level textarea. Bring it on-screen (`document.getElementById('se-rte-frame__summary').scrollIntoView({block:'center'})`),
  click into the body, `cmd+a` → `Backspace` → `type`. It syncs to the listing on save.
  - **Trap:** `document.querySelector('textarea[name*=description]')` reads the *Condition description*
    box (a separate 1000-char textarea), not the body — don't verify the body that way.
  - There's a "Show HTML Code" toggle if you need raw HTML.
- **Item specifics** — Brand/Type are usually prefilled; a block of suggested specifics has an "Apply all"
  link. Optional SEO; leave unless asked.

See `reference/field-map.md` for the full, growing list of fields, refs, and dropdown values.

## Submit & verify

1. `find` the **"Revise it"** button → click it.
2. Confirmation dialog **"Your listing has been revised"** appears → click **Done**.
3. **Verify with a screenshot, not JS** — value-reads of the title/SKU inputs have returned wrong nodes
   (e.g. `"on"`). Trust the visible field + the browser tab title, or read the specific input by `ref`
   from `read_page`/`find`. Optionally `read_item.py` (seller-agent, prompt-free) re-reads the live
   detail page to confirm price/title/active.

## After the write (cross-channel hygiene)

Record any title/price/description change back into `items/RG-XXXX/label.json → channels.ebay.note`, and
propagate to every other live channel (Square live price + reporting category, GitHub `label.json` **and**
the `$` in `index.html`, FB/Whatnot) — a change isn't done until it's consistent across all active channels.
Keep required tokens consistent per the title/keyword template (form phrase + maker + center-stone/material).

## Update protocol for this skill (important)

When you learn a new field, selector, dropdown value, or gotcha, **append it to `reference/field-map.md`**
and bump this SKILL.md changelog. Treat the field-map like the seller-agent's fast-path cache: it
accumulates so future sessions drive the form deterministically. Sync both copies (source +
`~/.claude/plugins/cache/.../ebay-chrome/`) and re-sync via the Skills UI to activate in Cowork.
