# eBay form field-map (grow this every session)

The accumulating knowledge base of eBay's Seller Hub / "Revise your listing" form: where each field is,
how to set it, and (for dropdowns) the allowed values. **Append as you learn.** Mirrors the role
`whatnot-catalog` plays for Whatnot. Each entry: what it is → how to reach/set it → values/notes.

Last updated: 2026-06-20 (seeded from the RG-0023 Weiss brooch revise).

---

## Navigation

| Target | URL / how | Notes |
|---|---|---|
| Active listings | `https://www.ebay.com/sh/lst/active` | Seller Hub → Listings → Active |
| Inactive / Drafts / Scheduled | left rail on the Active page | |
| Find a listing | search box "Search by title, SKU, or item number" → type item number → Return | returns the single row |
| Open Revise | the row's **Edit** button | lands on "Revise your listing" |
| ❌ Deep-link | `…/lstng?...&mode=ReviseItem&itemId=…` | DON'T — hangs at `document_idle`. Enter via Seller Hub. |

## "Revise your listing" — fields (top → bottom)

| Field | Type | How to set | Values / notes |
|---|---|---|---|
| Photos | tile grid, "5/25", main slot + Add | not yet automated here | up to 24 photos + 1 video; main = first |
| **Item title** | `<input>` | click → `cmd+a` → `Backspace` → type | **80-char max**, live `NN/80` counter |
| Subtitle (optional) | `<input>` | — | +$2.00 paid; 0/55; usually skip |
| **Custom label (SKU)** | `<input>` | click → type | set to `RG-XXXX` |
| Item category | link "Brooches & Pins" + Edit | not changed here | e.g. Jewelry & Watches > Vintage & Antique Jewelry |
| Variations | — | n/a for single items | "not available because the original listing did not include them" |
| Item specifics | dropdowns + chips + "Apply all" | optional | see Item specifics table below |
| **Description** | **RTE iframe** `id=se-rte-frame__summary` | scrollIntoView → click body → `cmd+a` → `Backspace` → type | syncs on save; **NOT** a page textarea |
| Condition description | `<textarea>` | click → type | separate 1000-char box; `textarea[name*=escription]` resolves to THIS, not the body |
| **Item price** | `<input>` (PRICING) | click → `cmd+a` → type | ignore eBay "Recommended price" suggestion |
| Quantity | `<input>` | — | usually 1 |
| **Submit** | button **"Revise it"** | `find` → click | → dialog "Your listing has been revised" → **Done** |

## Item specifics seen (Jewelry / brooch category)

Prefilled "Required": **Brand** (e.g. `Weiss`), **Type** (e.g. `Brooch`).
Suggested (via "Apply all" or individually) — observed values offered:

- Antique: No · Customized: No · Department: Women · Era: `Retro (1935-1950)` · Handmade: No
- Materials sourced from: United States · Occasion: Anniversary,Birthday · Secondary Stone: `Glass`
- Seller Warranty: No · Setting Style: `Prong` · Signed: `Yes`
- Main Stone Shape: suggested `Cabochon` · plus many empty optional dropdowns (Cut Grade, Certification,
  Total Carat Weight, Base Metal, Shape, Main Stone Treatment, etc.)

(Capture concrete dropdown option lists here as we open them.)

## Gotchas / lessons

- **Description iframe vs textarea:** the visible body is the `se-rte-frame__summary` iframe; the only
  page-level `textarea` matching `*description*` is the **Condition description** box. Verify the body
  visually, not via that textarea.
- **JS value reads are unreliable** for title/SKU here — broad selectors returned `"on"` (matched a
  checkbox). Read by the exact `ref` from `read_page`/`find`, or just screenshot.
- **No permission churn on eBay** (unlike facebook.com) — `browser_batch` sequences ran without per-action
  approval prompts. Batch aggressively.
- **Confirmation dialog** buttons: View listing / Create new listing / Create similar listing / Share
  listing / **Feedback** / **Done**.

## CREATE a new listing — end-to-end (mapped 2026-06-21, RG-0055 Kreamer tin → live item 298439755483)

The full browser CREATE flow. No Gemini, no permission churn — `browser_batch` the whole thing.

1. **Idempotency first.** Seller Hub → Active (`/sh/lst/active`): search the maker/title in "Search by
   title, SKU, or item number" → expect **0 results**. Then left-rail **Drafts** → scan titles (the
   create form auto-saves a draft on a crash, so a half-done one may already exist). Only then create.
2. **Start:** click **Create listing** → lands on `…/sl/prelist/home`. Type a descriptive phrase
   (brand + form + material) in **"Enter brand, model, description, etc."** → Search.
3. **Find a match** page: eBay suggests a **category** (breadcrumb, e.g. *Collectibles › Kitchen & Home ›
   Kitchen Storage & Organization › Canisters & Jars*) and shows related listings (handy live comps).
   For a one-off, click **"Continue without match"** (bottom center) to take the suggested category.
4. **Confirm details** modal: **Select the condition** (New / New other / Seller refurbished / **Used** /
   For parts) → **Continue to listing**. Lands on **"Complete your listing"** (`/lstng?draftId=…&mode=AddItem`).
5. **Photos** — do NOT click "Upload from computer" (opens a native picker you can't see). `find`
   "photo file upload input element" → returns the **`<input type=file>`** ref → `file_upload` with
   **workspace absolute paths** (`/Users/.../items/RG-XXXX/hero.jpeg`, …). **First file = Main.** Keep each
   `file_upload` call **< 10 MB** (≈4–5 jpegs); split into batches, re-`find` the input ref between batches.
6. **Title** — plain `<input>`, click → `cmd+a` → `Backspace` → type (80-char max; tab title echoes it).
7. **Custom label (SKU)** — plain `<input>`; type `RG-XXXX`.
8. **Item specifics** — a **"Suggested item specifics"** card (eBay.ai, from photos+title) with checkboxes
   (Set Includes, Size, Material, Vintage, Original, etc.); review for accuracy → **"Apply all"**. Then a
   **Required** block (here: Item Height/Length/Width — free-text, type e.g. `18 in`). Then **Additional
   (optional)** dropdowns: **Type** (prefilled), **Brand** (combobox → search box → "Add custom value: +
   Kreamer" since brand often isn't in the list), **Color** (combobox → type → pick), Country of Origin
   (combobox → "United States"), and **Yes/No** chips (Antique = Yes). Ignore wrong AI suggestions (it
   suggested Brand "Unbranded" + Color "Green" — both overridden).
9. **Condition** — Item condition shows from step 4; **Condition description** = plain `<textarea>`
   (1000-char) → type the as-found note.
10. **Description** — for CREATE this is an **inline contenteditable RTE** (toolbar: Arial / size / B / I /
    lists / Custom template / **Show HTML Code**) directly on the page — **NOT** the `se-rte-frame__summary`
    iframe that Revise uses. Click into the body and type (newlines make paragraphs). "Show HTML Code" for raw.
11. **Pricing** — **Item price** `<input>` (type `65.00`); **Quantity** 1; **Payment policy** dropdown;
    **Allow offers** toggle = Best Offer (was already ON). **Schedule** toggle off = goes live now.
12. **Shipping** — **Shipping policy** dropdown lists your business policies; for pickup-only items pick
    **"Local Pickup Only"** (the create default may be "Local Pickup + Calculated Ship + International" —
    change it!). Package weight/dims can be left blank for pickup-only.
13. **Preferences → Your settings** (pencil edit): Item location (ZIP/City/State) + **Return policy**
    dropdown → for as-found pickup goods pick **"No Returns"** → **Done**.
14. **Charity / Promote / Item disclosures** — optional, leave off.
15. **List it** (blue button at bottom; also Save for later / Preview). Success modal **"Your listing is
    now live"** shows the title + **`ID-<itemId>`** and View/Create-new/Create-similar/Share/Done. The
    public URL is `https://www.ebay.com/itm/<itemId>`. Click **Done**.
16. **After:** write `item_id` + `url` into `items/RG-XXXX/label.json → channels.ebay` (status `listed`),
    commit, and confirm price/pickup consistent with the other channels.

⚠️ eBay's create form can crash the tab mid-listing — the draft auto-saves, so resume via Seller Hub → Drafts.

## Not yet mapped (TODO — fill in next sessions)

- Photo **reorder/remove** via the extension (upload + main-slot are mapped; drag-reorder is not).
- Auction (Starting bid) format — only Buy It Now mapped.
- Best Offer **auto-accept / auto-decline** thresholds (Minimum offer / Auto accept fields).
- Oversize package handling on CREATE (only relevant when shipping, not pickup-only).
- Full dropdown option lists for the jewelry Item specifics.
