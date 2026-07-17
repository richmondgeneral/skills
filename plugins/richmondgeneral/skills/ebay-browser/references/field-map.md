# eBay browser form field map

Driver-neutral knowledge for eBay Seller Hub and its create/revise forms: where each field is, how to set
it, and the allowed values observed. Translate these operations into the current host's native browser
tools; see `native-surfaces.md`. Add only behavior verified on the live form.

**Protocol:** Mandatory settle→edit→verify→live-page rules live in `../SKILL.md` and
`failure-matrix.md`. Combobox steps: `combobox.md`. Account sitemap: `seller-hub-map.md`.

Last updated: 2026-07-16 (v3 skill cross-links; field detail still from 2026-06/07 sessions).

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
- **No permission churn was observed on eBay** (unlike facebook.com) — native Chrome action batches ran
  without per-action approval prompts. Batch when the active host supports it.
- **Confirmation dialog** buttons: View listing / Create new listing / Create similar listing / Share
  listing / **Feedback** / **Done**.

## CREATE a new listing — end-to-end (first verified 2026-06-21: RG-0054 → live item 298439625952; field-map refined same day on RG-0055 Kreamer tin → 298439755483)

The full browser CREATE flow. Batch native browser actions where the active host supports it.

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
5. **Photos** — target the **`<input type=file>`** with the host's direct upload action and pass
   **workspace absolute paths** (`/Users/.../items/RG-XXXX/hero.jpeg`, …). **First file = Main.** Keep each
   upload batch **< 10 MB** (≈4–5 jpegs); split batches and reacquire the input between them.
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

## Session learnings 2026-07-15 (5 revisions + 2 creates: wrestling DVDs 298507094521, Knoll fabric 298507111449)

### Navigation / Seller Hub
- **❌ `/sh/lst/active?keyword=…` deep-link hangs the tab** (same failure class as the ReviseItem
  deep-link — renderer freezes, every CDP call times out). Navigate the PLAIN `/sh/lst/active`,
  then type into the search box. If a tab is frozen, don't fight it: create a fresh tab.
- **Post-"Done" search box swallow:** after the revise-confirmation "Done" click, Seller Hub
  re-renders async — the FIRST click+type into "Search by title, SKU, or item number" is often
  swallowed. Re-click and retype; screenshot-verify the box shows your number before clicking Edit.
- **Stale row prices:** the Active-listings row can show the OLD price right after a successful
  revise (dialog confirmed, row still stale). Trust the "Your listing has been revised" dialog or
  re-read the live item; never re-revise off the row price.

### Revise form
- **"Revise it" ref-clicks don't fire.** `find` → click-by-ref scrolls but doesn't submit;
  `scroll_to` the ref, then **coordinate-click the visible blue button** (≈(643,572) @ ~1290px
  viewport). Success signal = the dialog; absence after 7s = click again once.

### Create form
- Prelist may **skip "Find a match"** and jump straight to the condition modal (e.g. Crafts >
  Fabric: only New/Used offered).
- **Shipping policy is a React combobox, NOT a native `<select>`** — safe to click open. Observed
  options: Local Pickup Only / Local Pickup + Calculated Ship + International (elS) / Standard
  Small Item / Default Shipping. Create default = last-used (verify every time).
- Suggested item specifics: check individually rather than "Apply all" when one is wrong
  (eBay.ai offered "Actor: John Cena" for a DVD lot stack photo).
- **"List it" can freeze the renderer AFTER the submit succeeds.** Don't retry-click a frozen tab
  (duplicate risk) — open a FRESH tab → `/sh/lst/active` → confirm the new listing exists.

### Cross-channel: FB photos → eBay
- FB-only listings (no items/RG-XXXX dir): `apps/seller-agent/save_item_photos.py <fb_item_url>
  <out_dir>` downloads the listing photos via the logged-in Playwright profile (headless +
  `--disable-blink-features=AutomationControlled`; a HEADED launch over the osascript bridge dies
  with TargetClosedError; clear stale `playwright_profile/Singleton*` locks first).
- Filter the grab: real product photos are **720×960 portraits**; 526/540/565 squares are
  recommendation-thumbnail junk. FB CDN URLs are signed → blocked from native-browser output; the
  Playwright context fetch keeps them browser-side (clipboard hand-off also freezes the tab — don't).
- **Revise-form field typing can also be swallowed** (like the Seller Hub search box) right after
  the form loads — a title retype visually "succeeded" per the action log but the field kept the
  old value and the revise saved the OLD title. Verify with `zoom` on the field or the tab-title
  echo BEFORE clicking Revise it; if stale, click the field again and retype.
- Package weight/dims inputs (calculated-ship policies): plain inputs to the right of the policy
  dropdown — lbs / oz / L×W×H in. Type after selecting the policy; live-verified 7 lb 15×8×6 →
  calculated $9.04 ground quote on the item page.

## ⚠️ CRITICAL — the revise confirmation dialog does NOT prove your edits saved (2026-07-15)
"Your listing has been revised" appears even when every keystroke was swallowed — Revise submits
whatever the form actually holds. A batch of 5 price revisions all showed the dialog; ZERO price
changes had landed (verified on the live item pages). The swallow hits any field for ~the first
seconds after the form (or the Seller Hub search box) renders, and can recur; ref-clicks from
`find` often don't focus the field either. **Mandatory protocol for EVERY field edit:**
1. `screenshot` first (forces a settle + gives real coordinates), then coordinate-click the field.
2. Type, then `zoom` the field region and READ the value. If stale, click+retype (2nd try lands).
3. Only then submit — and verify the live `/itm/<id>` page after (`innerText` match on `US $…`),
   never the Seller Hub row (stale) and never the dialog (lies).
