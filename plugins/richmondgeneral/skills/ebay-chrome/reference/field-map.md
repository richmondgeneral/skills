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

## Not yet mapped (TODO — fill in next sessions)

- Photo add/remove/reorder via the extension (tile grid + hidden file input).
- The **Create listing** (new) flow end-to-end (this skill has only covered Revise so far).
- Shipping / package dimensions section refs + oversize handling.
- Best Offer / auto-accept-decline thresholds.
- Full dropdown option lists for the jewelry Item specifics.
