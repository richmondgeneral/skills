---
name: ebay-browser
description: >
  Create, revise, and verify Richmond General eBay listings through an authenticated browser session.
  Prefer the current agent's native Chrome integration or computer-use surface: Claude in Chrome,
  Codex Chrome control, or Gemini Spark Chrome auto-browse. Use the existing Playwright seller-agent
  profile only when native browser control is unavailable, disconnected, blocked, or cannot complete a
  required interaction. Use for "list on eBay", "revise eBay", "edit eBay listing", "eBay Seller Hub",
  seller drafts, end/relist, and browser-created eBay listings. Route Inventory API-managed listings to
  `ebay-lister` instead.
metadata:
  version: "3.0"
  author: scottybe
  updated: "2026-07-16"
  changelog: |
    v3.0 - Agent UX/UI reliability upgrade (plan 2026-07-16):
    - Mandatory settle→edit→verify→live-page protocol elevated into SKILL body
    - Recipes for Active search, CREATE, REVISE, photos, shipping combobox, batch revise
    - New references: failure-matrix.md, combobox.md, seller-hub-map.md
    - Explicit false-success rule: revise/list dialogs never prove field writes landed
    v2.0 - Agent-neutral: native authenticated Chrome first; Playwright fallback.
---

# eBay Browser Listing

Drive eBay Seller Hub through the best authenticated browser surface available to the current agent.
Keep field knowledge independent of the browser driver.

**References (load as needed):**

| File | Use when |
|---|---|
| `references/field-map.md` | CREATE/REVISE field locations, values, session learnings |
| `references/failure-matrix.md` | Something failed — symptom → action |
| `references/combobox.md` | Shipping policy, brand, country React comboboxes |
| `references/seller-hub-map.md` | Navigation sitemap, safe vs hang URLs, drafts/end/relist |
| `references/native-surfaces.md` | Pick Claude / Codex / Gemini / Grok Chrome route |
| `references/playwright-fallback.md` | Native route unavailable — `ops/seller-agent` |

---

## ⚠️ Mandatory Field Edit Protocol

eBay Seller Hub **swallows keystrokes** for several seconds after a form or search box renders.
The **"Your listing has been revised" / "Your listing is now live" dialog is not proof** that edits
landed — verified 2026-07-15: five price revises all showed the dialog; **zero** prices changed on
the live item page.

**For EVERY field write (title, SKU, price, description, shipping, …):**

1. **Screenshot** first (forces settle + supplies real coordinates).
2. **Focus** the field — prefer host `find`/`form_input`; if the value does not take, **coordinate-click**
   the field (ref-clicks often fail to focus).
3. **Type or select** the value (`cmd+a` → clear → type for text inputs).
4. **Read back** — zoom the field region or read the exact control; if stale, click + retype (2nd try
   usually lands).
5. Only after **all** intended fields verify, click **Revise it** / **List it**.
6. **Prove on live `/itm/<itemId>`** in a fresh tab (title, `US $…` price, status).  
   Never trust: success dialog · Active-listings row price · action log alone.

**Submit clicks:** `"Revise it"` ref-clicks frequently do not fire. Scroll into view, then
**coordinate-click the blue button**. Wait ~7s for the dialog; if none, click once more — then still
verify live.

**Frozen tab:** open a **fresh tab** and re-enter via Seller Hub. **Never** re-click **List it** /
**Revise it** on a frozen renderer (submission may already have succeeded → duplicates).

---

## Route before acting

1. Read `items/RG-XXXX/label.json` → `channels.ebay`.
2. If `offer_id` exists or the note says Sell Inventory API, **stop** and use `ebay-lister` (API
   listings cannot be revised in Seller Hub).
3. Select driver via `references/native-surfaces.md` (native Chrome first).
4. Use `references/playwright-fallback.md` only after native is unavailable or fails one fresh-tab retry.

---

## Prepare

- Load title, SKU, price, condition, description, item specifics, shipping intent, photo paths.
- Confirm **publish authorization**. Without it: prepare the form and stop for review.
- **CREATE:** search **Active** and **Drafts** for SKU/title before starting (idempotency).
- Read `references/field-map.md` for the form you are about to drive.

---

## Recipes

### A. Open Seller Hub Active listings (safe)

1. Navigate to plain `https://www.ebay.com/sh/lst/active` — **never** `?keyword=…` (hangs).
2. Screenshot. Find search box **"Search by title, SKU, or item number"**.
3. Click → type item number or `RG-XXXX` → Return.  
   After a confirmation **Done**, the first type is often swallowed — **re-click and retype**;
   screenshot-verify the box before Edit.

### B. Revise an existing listing (price / title / SKU / description)

1. Recipe A → find the row → **Edit** (do not deep-link ReviseItem URLs).
2. Screenshot. Apply Mandatory Protocol per field:
   - **Title** — plain input, 80-char max
   - **Custom label (SKU)** — plain input → `RG-XXXX`
   - **Item price** — PRICING input; ignore eBay recommended price
   - **Description** — REVISE uses iframe `id=se-rte-frame__summary` (**not** the page textarea —
     that is **Condition description**)
3. Coordinate-click **Revise it** → optional Done on dialog.
4. Fresh tab → `https://www.ebay.com/itm/<itemId>` → verify fields.
5. Write `channels.ebay` (item_id, url, price, driver) without wiping other channel keys.

### C. CREATE a new listing (pickup-only used goods default)

Full step detail: `field-map.md` CREATE section. Short path:

1. Active + Drafts search → 0 hits.
2. **Create listing** → prelist search phrase → **Continue without match** (or pick category).
3. Condition modal → **Used** (or correct) → Continue.
4. Photos: host file upload; **first file = Main**; batches &lt; ~10 MB.
5. Title, SKU, item specifics (prefer individual checkboxes over blind "Apply all"), condition desc.
6. **Description:** CREATE = **inline contenteditable RTE** on the page (not the revise iframe).
7. Price, qty 1, payment policy; shipping policy combobox → often **"Local Pickup Only"** (verify —
   default is last-used). See `combobox.md`.
8. Preferences → return policy (e.g. No Returns for as-found pickup).
9. **List it** only if authorized. Capture item ID from dialog; **still** open live `/itm/…`.
10. Write `channels.ebay` status `listed`.

⚠️ Tab may crash mid-CREATE; draft auto-saves → resume via **Drafts**, do not start a second CREATE.

### D. Photo upload

- Prefer native direct `input[type=file]` / host upload action with **absolute workspace paths**.
- Order matters: index 0 = main.
- Split large sets; reacquire the file input between batches.
- Reorder/remove via drag is **not** fully mapped — upload correct order when possible.

### E. Shipping / brand React combobox

See `references/combobox.md`. Never treat these as native `<select>`.

### F. Batch revise (N listings)

For each SKU/item_id, **sequentially**:

1. Fresh tab if the previous submit froze anything.
2. Recipe A → Edit → Mandatory Protocol → Revise it → live `/itm` verify.
3. Do not open N revise forms in parallel.
4. After **Done**, re-search with double-type protocol (search swallow).

---

## Publish and verify checklist

1. Submit only when publishing/revising is authorized.
2. Dialog = soft signal only (may capture item ID).
3. Live `/itm/<id>` must show intended title, price, and status.
4. Persist `channels.ebay` without deleting unrelated channel metadata.
5. Propagate shared price/title when the task includes cross-channel reconciliation.
6. If outcome is ambiguous → `reconcile_required` mindset: inventory search, **do not** re-click List/Revise.

---

## Account surfaces beyond create/revise

See `references/seller-hub-map.md` for Drafts resume, End listing, Sell similar, Offers, and hang-prone URLs.
Expand that map only with **live-verified** steps.

---

## Maintain the workflow

- Add verified UI behavior to `field-map.md` / `failure-matrix.md` / `seller-hub-map.md`.
- Keep host capability notes in `native-surfaces.md`; Playwright in `playwright-fallback.md`.
- Edit the **canonical** repo copy under `richmondgeneral/skills/plugins/richmondgeneral/skills/ebay-browser/`,
  then rebuild or reinstall the plugin so marketplace caches stay derived.
