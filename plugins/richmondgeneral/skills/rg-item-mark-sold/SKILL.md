---
name: rg-item-mark-sold
description: Mark a Richmond General item as sold across all surfaces — migrate the GitHub Pages item card (and the matching gallery grid card on the landing page) to the sold-archive pattern (brown SOLD badge, "Sold · $X" front price, sold-status-panel back footer replacing the QR + buy button), write status.json with sold metadata, delete the Square payment link via API so the printed QR / bookmarked checkout URL can no longer charge a phantom sale, validate, and commit/push. Use this skill whenever the user says any of "mark RG-XXXX as sold", "mark as sold", "this sold", "[item] sold for $X", "RG-XXXX sold on Square", "buyer paid", "this item sold", "update RG-XXXX to sold", "set RG-XXXX status to sold", "deactivate the buy link", "kill the payment link for X", "retire this listing", or otherwise indicates that a unique inventory item has been purchased and needs the listing taken down without being deleted. Do NOT use for inventory loss/giveaways/damage (use square-inventory-loss instead), description or price edits on still-available items (use rg-item-update), or new item onboarding (use rg-full-auto).
metadata:
  version: "1.2"
  author: scottybe
  updated: "2026-06-20"
  changelog: |
    v1.2 - Payment-link discovery gap (RG-0014 phantom-charge fix):
    - delete_payment_link.py: --id now deletes directly from the full
      account-wide link list instead of filtering *within* the SKU matches,
      so it reaches a link whose description AND payment_note are both null
      (the case that left RG-0014's link 2PE4WMYVYB6TXE2V live after sale).
    - Added --url (short-slug or full URL) and --order-id selectors, both of
      which also bypass the SKU metadata match.
    - Empty SKU match no longer reports "all clear" when live links exist:
      it lists every live link and exits 5 so a caller can't treat an
      unseen null-metadata link as handled.
    - Added --audit: read-only sweep flagging every live link whose item is
      already marked sold (CRITICAL) or maps to no item (WARN).
    - Step 7 doc rewritten: --id no longer "disambiguates within the SKU";
      records the deleted link id/order_id/slug into status.json for audit.
    - Regression test: tests/test_delete_payment_link.py.
    v1.1 - Gallery-card surface:
    - Added Step 5 "Migrate the gallery card in items/index.html" — the
      landing-page grid card is a separate GitHub Pages surface that does
      NOT auto-update; missing it left RG-0002 showing as available (green
      "New" badge, live price) after its item page was migrated. Fixed in
      richmondgeneral/items commit f05c330.
    - Step 1 "already on clean sold pattern" row now routes through the
      gallery step instead of skipping straight to status.json.
    - The commit step's git add now also stages index.html (the gallery);
      renumbered status.json/Square/validate/commit to Steps 6-9 and
      corrected the stale "Step 5/6" numbering in the workflow intro.
---

# Richmond General — Mark Item as Sold

End-to-end "this item just sold" workflow. One skill, every surface kept consistent: the GitHub Pages item card flips into the sold-archive presentation, the matching card in the landing-page gallery grid is flipped to the sold treatment, a `status.json` records what happened, and the Square payment link is destroyed so neither the short URL (`square.link/u/...`) nor the long checkout URL (`checkout.square.site/...`) can still take a payment from someone with a stale bookmark, a printed QR label, or an old marketing post.

**Why this exists separately from rg-item-update:** updating a listing's price or description leaves it for sale. Marking it sold is a *terminal* state change with side effects across three systems (GitHub Pages, status ledger, Square checkout). Conflating the two led to sold items with live payment links — exactly the bug this skill prevents.

## Constants

- **Site repo (GitHub Pages):** `/Users/scottybe/workspace/richmondgeneral/items` (git remote: `git@github.com:richmondgeneral/items.git`, branch `main` auto-deploys)
- **Square location:** `B87BAEZ0NWV34` (Richmond General — only location)
- **Square merchant_id:** `7MM9AFJAD0XHW`
- **Workspace `.env`:** `/Users/scottybe/workspace/richmondgeneral/.env` — reads `SQUARE_ACCESS_TOKEN` and `SQUARE_ENVIRONMENT` (`production` for live merchant)
- **Square-Version header:** `2026-04-21` (current pinned version — match `square-image-upload-cowork`)
- **Reference sold pages (canonical pattern):** `items/RG-0003/index.html`, `items/RG-0005/index.html`
- **Helper script:** `scripts/delete_payment_link.py` (stdlib-only)
- **Validator:** `items/validate-item.sh RG-XXXX` (already recognizes sold archive items)

## Inputs to gather before touching anything

Confirm these with the user up front. If anything is missing or ambiguous, ask — guessing wrong here is expensive (a real PR / push, plus an irreversible API delete).

| Input | Example | If unknown |
|---|---|---|
| SKU | `RG-0002` | Ask — sold workflow can't start without one |
| Sold price (USD) | `35` (numeric, no `$`) | Ask — needed for both HTML and `status.json` |
| Listed price (USD) | `35` or `55` if different from sold | Default to the price currently shown on the item card if not stated |
| Sold date (YYYY-MM-DD) | `2026-05-20` | Default to today; offer the user the option to omit the date line entirely if they don't remember |
| Sales channel | "Square checkout", "Facebook Marketplace", "in-store cash" | Capture in `status.json` `notes`, not in the page copy |

**One question worth asking proactively when it's ambiguous:** *"Does the Square payment link still exist for this item, or did you already cancel it?"* — saves an API round-trip if the answer is "already gone".

## The workflow

Execute in order. Steps 1–6 are local-only and trivially reversible. Step 7 (Square delete) is irreversible — confirm with the user before running it. Step 9 is the push.

### Step 1 — Read the current state of the item card

```
Read items/RG-XXXX/index.html
```

Then classify what you're looking at:

| Current state | Primary signal | Migration scope |
|---|---|---|
| **Active listing** (clean active pattern) | `<a … class="buy-button">Buy Now</a>` linking to `square.link/u/...` is present in the back-footer. (QR section presence is *not* a reliable signal — some legacy items omit it.) | Full migration: front badge + price, back footer, CSS additions |
| **Old sold pattern** (pre-RG-0005 style) | `<span class="sold-ribbon">SOLD</span>` diagonal banner on the hero, plus strikethrough `item-price`, `.buy-button.sold` disabled span, `.qr-section.sold` grayscale | Same full migration, plus *remove* the old `.sold-ribbon` / `.buy-button.sold` / `.qr-section.sold` / `.price-wrap` CSS blocks. RG-0002 was the last instance — if you find another, the migration in [commit `5d93566` on richmondgeneral/items](https://github.com/richmondgeneral/items/commit/5d93566) (RG-0002/index.html + RG-0002/status.json) is the model |
| **Already on clean sold pattern** | `sku-badge sold-badge`, `item-price sold-price`, `sold-status-panel` present | Item-page HTML needs no changes — but the **gallery card may still be stale** (this is exactly how RG-0002 slipped through). Still do Step 5 (gallery card), then Step 6 (status.json) and Step 7 (Square). |

### Step 2 — Edit the front face

Two edits inside `<div class="card-face card-front">`:

**2a. SKU badge.** Replace:
```html
<span class="sku-badge">RG-XXXX</span>
```
with:
```html
<span class="sku-badge sold-badge">RG-XXXX · SOLD</span>
```

If the old pattern also had `<span class="sold-ribbon">SOLD</span>` directly after the badge, delete that whole line.

**2b. Front price.** Replace the entire `<div class="front-footer">` price half with a single span:
```html
<span class="item-price sold-price">Sold · $X.00</span>
```
Always write the price with `.00` in source — the existing `PRICE_DISPLAY_FORMATTER` script at the bottom of every item page strips trailing `.00` at render time, so `$35.00` displays as `$35` to users but stays canonical in the file.

If the old pattern had `<span class="price-wrap">…</span>` wrapping a strikethrough price + separate "Sold" pill, the wrapper goes too — collapse to the single span above.

### Step 3 — Edit the back footer

Inside `<div class="card-face card-back">`, replace the entire `<div class="back-footer">` body with:

```html
<div class="back-footer">
    <div class="sold-status-panel">
        <span class="sold-status">Sold on <Month D, YYYY></span>
        <span class="sold-meta">Final sale price: $X.00</span>
        <a href="../" class="archive-link">Browse available items</a>
    </div>
</div>
```

The user-facing month-name format is `Sold on August 24, 2025` (see RG-0005). If the user opted out of a specific date, drop the entire `<span class="sold-status">…</span>` line and keep just the "Final sale price" + browse link.

**Conditional cleanup — remove the inactive `buy-button` click handler** at the bottom of the inline `<script>` block, but **only if it's actually present in the file**. This block ships with the active-listing template (so items migrating from "Active listing" state will have it), and it shipped with the RG-0002 old-sold-pattern as well (port artifact, never cleaned up). It does NOT exist in items that were authored sold from day one (RG-0003, RG-0005) — for those, skip this sub-step.

```javascript
// DELETE THIS BLOCK if present (grep for `.buy-button` in the script tag):
document.querySelector('.buy-button')?.addEventListener('click', (e) => {
    e.stopPropagation();
    trackEvent('buy_button_click', { sku: 'RG-XXXX', price: NN });  // use the page's real SKU
});
```

> **Note about the price formatter:** every item page ends with a `PRICE_DISPLAY_FORMATTER` `<script>` that strips trailing `.00` at render time. It targets `.item-price` and `.sold-meta` only — NOT `.sold-status`. So `Sold on August 24, 2025` in `.sold-status` is fine, but don't put dollar amounts into that element or the `.00` will reach the user.

Also append `(sold)` to the flip-card's `aria-label` and prepend `Sold archive: ` to the `<meta name="description">` and `og:description` for honest SEO.

### Step 4 — CSS surgery

Look for the CSS block tagged `/* SOLD STATE */` in the file's `<style>` section.

If you find the **old pattern** (RG-0002 style), delete these rules entirely: `.sold-ribbon`, `.price-wrap`, `.item-price.sold-price` (the strikethrough version), `.sold-meta` (the uppercase-brown version), `.buy-button.sold`, `.buy-button.sold:hover`, `.qr-section.sold`. Then add the clean pattern from [`references/sold-pattern.css`](references/sold-pattern.css) (also reproduced inline below for context):

```css
/* SOLD STATE */
.sku-badge.sold-badge { background: #8A5A3B; }

.item-price.sold-price {
    font-size: 1.05rem;
    color: #8A5A3B;
    font-weight: 700;
}

.sold-status-panel {
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
    width: 100%;
}

.sold-status {
    font-size: 0.8rem;
    font-weight: 700;
    color: var(--rg-charcoal);
    letter-spacing: 0.3px;
}

.sold-meta { font-size: 0.72rem; color: #666; }

.archive-link {
    display: inline-flex;
    width: fit-content;
    margin-top: 0.15rem;
    font-size: 0.78rem;
    font-weight: 600;
    color: var(--rg-brown);
    text-decoration: none;
}

.archive-link:hover { text-decoration: underline; }
```

If the page was an active listing with no sold-state rules at all, just append the block above before the `.brand-strip` rule.

> **Leave the existing `.buy-button` and `.buy-button:hover` CSS rules in place** even after the buy-button element is removed from the markup. They're dead but harmless, the validator does not flag them, and this matches the convention on RG-0005 (which kept them after sale). RG-0003 stripped them, but RG-0005 is the more recent reference — when the two disagree, follow RG-0005. Removing dead CSS is a separate cleanup pass, not part of mark-sold.

### Step 5 — Migrate the gallery card in `items/index.html`

The item's own page (Steps 2–4) is **not** the only GitHub Pages surface. The curated landing-page grid in `items/index.html` has its own card for the item, and it does **not** update automatically. Skipping this is the gap that left RG-0002 showing as available in the grid (green "New" badge, live `$35` price, "View Story") long after its item page was migrated — and it also inflated the header's available-item counter (`#item-count`, computed near the bottom of `index.html` via `document.querySelectorAll('.item-card:not([data-status="sold"])')`). Fixed in richmondgeneral/items commit `f05c330`.

Find the item's card block (search `items/index.html` for `RG-XXXX`) and transform it to match the canonical sold cards — `RG-0003` (~line 660) and `RG-0005` (~line 706):

| Element | From | To |
|---|---|---|
| `.item-card` anchor | `<a href="./RG-XXXX/" class="item-card" data-category="…">` | add ` data-status="sold"` |
| Badge | `<span class="item-badge">New</span>` | `<span class="item-badge sold">Sold</span>` |
| Category | `<p class="item-category">Books & Paper</p>` | append ` · Archive` → `…Books & Paper · Archive</p>` |
| Era line | `<p class="item-era">1892 Victorian • …</p>` | append ` • Sold <Month D, YYYY>` (date from `status.json` `sold_at`) |
| Price | `<span class="item-price">$X</span>` | `<span class="item-price sold">Sold · $X.00</span>` |
| CTA | `View Story` | `View Archive` |

Write the price with `.00` in source — the gallery has its **own** `PRICE_DISPLAY_FORMATTER` at the bottom of `index.html` (targets `.item-price, .sold-meta`) that strips trailing `.00` at render, exactly like the item page. So `Sold · $35.00` displays as `Sold · $35`.

The required CSS (`.item-badge.sold`, `.item-price.sold`, `.item-card[data-status="sold"]`) **already exists** in `items/index.html` — no CSS changes needed here.

If the user opted out of a specific sold date (Step 3), drop the ` • Sold …` suffix from the era line and keep the rest.

> **Not covered by `validate-item.sh`.** The validator (Step 8) checks the `RG-XXXX/` folder, not the root `index.html`. Verify this edit by hand: `cd items && grep -n 'RG-XXXX' index.html` should now show `data-status="sold"`, `item-badge sold`, `· Archive`, and `item-price sold` on that card. (Optional: serve locally and confirm the card renders with the brown SOLD badge and the available-item count dropped by one.)

### Step 6 — Write `items/RG-XXXX/status.json`

```json
{
  "sku": "RG-XXXX",
  "status": "sold",
  "listed_price": <listed_price_number>,
  "sold_price": <sold_price_number>,
  "sold_currency": "USD",
  "sold_at": "YYYY-MM-DD",
  "notes": "<sales channel + any context — e.g., 'Sold via Square checkout. Payment link deactivated post-sale.'>"
}
```

Prices are JSON numbers (not strings, no `$`). If `listed_price === sold_price`, write both anyway — downstream reporting expects both keys present. See `RG-0003/status.json` (sold below ask) and `RG-0005/status.json` (sold at ask) for canonical examples.

### Step 7 — Delete the Square payment link

This is the irreversible step. **Confirm with the user before running** unless they've already explicitly said "deactivate it" in this session.

Use the helper script — it does a discovery-then-delete with a confirmation print:

```bash
python3 skills/rg-item-mark-sold/scripts/delete_payment_link.py RG-XXXX
```

The script:
1. Sources `SQUARE_ACCESS_TOKEN` from the workspace `.env` (override with `--env-file`)
2. Lists all payment links and matches the SKU against each link's `description` or `payment_note` (e.g. `"RG-0002 - 1892 Kings of the Forest"`)
3. Prints what it found (id, url, description, created_at) for visual confirmation
4. Refuses to proceed if multiple links match — pass `--id <PAYMENT_LINK_ID>` to pick exactly one. `--id` deletes that link **directly, from the full account-wide list** (not "within the SKU matches"), so it also reaches a link the SKU search can't see.
5. **Does NOT report "all clear" when the SKU matches nothing but live links still exist** (exit 5). The SKU search has a blind spot: a link whose `description` *and* `payment_note` are both null is invisible to it — this is exactly the RG-0014 phantom-charge gap (2026-06-20), where the helper printed "no payment link found" and would have left a live link able to charge. When this happens the script prints every live link and tells you to re-run with a precise selector. Only a genuinely empty account (zero links anywhere) is a clean "nothing to delete" (exit 0).
6. Deletes via `DELETE /v2/online-checkout/payment-links/{id}` once you pass `--yes`
7. Returns the cancelled `order_id` from Square — capture it for the commit message **and record the deleted link's id + cancelled `order_id` + short slug in `status.json` `notes`** (Step 6). That recorded identifier is what lets a later `--audit` (below) confirm the dead link belonged to this sold item even when its Square metadata was null.

**Reaching a link the SKU can't match.** If `description`/`payment_note` are null (or wrong), select the link explicitly — any one of these works, with or without a SKU argument:

```bash
python3 skills/rg-item-mark-sold/scripts/delete_payment_link.py --id 2PE4WMYVYB6TXE2V --yes        # by payment_link_id
python3 skills/rg-item-mark-sold/scripts/delete_payment_link.py --url WYk1Yl12 --yes               # by short-URL slug (or full URL)
python3 skills/rg-item-mark-sold/scripts/delete_payment_link.py --order-id Td1qji0tORadRLBNfgZGWR0WIjFZY --yes   # by order_id
```

**Audit sweep (read-only)** — catch this whole class proactively across the catalog:

```bash
python3 skills/rg-item-mark-sold/scripts/delete_payment_link.py --audit
```

It lists every live payment link, maps each to an item (by SKU in metadata, or by finding the link's id/slug/order_id in the item's `status.json` / `label.json` / `index.html`), and flags any link whose item is already marked **sold** (`CRITICAL`) or that maps to **no item at all** (`WARN` — possibly a sold item's null-metadata link). It never deletes; exit code is 6 if any `CRITICAL` is found, else 0. Run it after a batch of sales or whenever reconciling.

After the delete, verify both URL forms 404:

```bash
curl -sI https://square.link/u/<short-slug> -o /dev/null -w "short: %{http_code}\n"
curl -sI https://checkout.square.site/merchant/7MM9AFJAD0XHW/order/<order_id> -o /dev/null -w "long: %{http_code}\n"
```

Expected: short URL `303` (Square's "link gone" redirect page), long URL `404`.

**If the user reports they already deleted the link via Square Dashboard**, re-running by SKU will report no SKU match. If the account has no other live links that's a clean exit 0 — note it in the commit message. But if it exits 5 (other live links still exist), do **not** assume *this* item's link is the one that's gone: confirm with `--url <slug>` / `--order-id <id>` (or run `--audit`) before treating the link as deleted. A null-metadata link survives a SKU miss — that is the exact failure this guard exists to stop.

### Step 8 — Validate

```bash
cd items && ./validate-item.sh RG-XXXX
```

The validator is sold-aware — when `status.json` says `status: sold`, it does NOT flag the missing Square payment link as an error. It outputs `✓ Sold archive item intentionally has no Square payment link`. Any other error or warning means step 2/3/4 left something broken — fix before continuing.

**Two specific validator outputs to know:**

- **`⚠ Square payment link present on sold archive item`** — the migration left a stale `square.link/u/...` or `checkout.square.site/...` string somewhere in the file (often in a meta tag, an analytics comment, or an aria-label that referenced the buy button). The validator's grep doesn't distinguish active markup from leftover references. Search the file for both URL forms and delete any matches, then re-run the validator.

- **`✓ qr-code.png`** — `qr-code.png` stays in the folder. The validator still expects it, RG-0003 and RG-0005 both keep theirs, and the file is just a static PNG encoding a now-dead URL. It's a harmless archival artifact — do NOT `git rm` it as part of marking sold. (If you ever decide to clean these up, that's a separate audit pass across all sold items, and the validator would need updating in the same PR.)

### Step 9 — Commit and push

From `items/`:

```bash
git add index.html RG-XXXX/index.html RG-XXXX/status.json
git commit -m "chore(RG-XXXX): mark sold and migrate to clean sold-archive pattern" -m "[multi-line body — see template below]"
git push origin main
```

Commit message body template (substitute every `{{…}}` before committing; always include the `Co-Authored-By` line per workspace convention):

```
Aligns {{SKU}} with the RG-0003/RG-0005 sold pattern: brown SOLD badge,
"Sold · ${{PRICE}}" front price (no strikethrough), sold-status-panel on
the back footer, and the matching sold treatment on the gallery grid card
in index.html (data-status="sold", brown "Sold" badge, "Sold · ${{PRICE}}"
price, "View Archive" CTA). Adds status.json (sold_at {{DATE}}, ${{PRICE}}). Square
payment link {{LINK_ID}} deleted via API (cancelled_order_id:
{{ORDER_ID}}) — buy button removed rather than disabled.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

GitHub Pages auto-deploys from `main` in 1–2 minutes. No further action.

## After-action confirmation to the user

State, in this shape:
- Which item was marked sold (SKU + name) and the sold price / date written
- That **both** GitHub Pages surfaces were flipped — the item's own card *and* the gallery grid card on the landing page (so it no longer shows as available in the grid, and the available-item count is correct)
- That the Square payment link was deleted (include the link id and the returned `cancelled_order_id`) — or note "already deleted" if step 7 found no match
- The commit SHA and that it has been pushed to `main` (so they know GitHub Pages will redeploy)
- A reminder that the printed thermal label on the physical item (if any) still carries the now-dead QR — the customer-facing card flip ALREADY shows "SOLD", but the physical label may need to be physically removed or marked over if the item is still on display

## Edge cases worth knowing

- **Items where Square inventory `track_inventory: true`** — payment-link deletion is independent from inventory state. Square Online auto-decrements inventory at checkout; payment links don't. If the item is also in the Square Catalog and inventory matters, that's `rg-item-update`'s job (set quantity to 0 separately) — this skill doesn't touch the Catalog object.
- **Items sold off-channel (cash, Facebook Marketplace, etc.) where no Square payment link ever existed** — skip Step 7 (no link to delete), but still write the `status.json` and migrate **both** HTML surfaces (item page + gallery card). The skill is the source of truth for "this listing is retired", not just for Square-sourced sales.
- **Multiple payment links for the same SKU** — happens occasionally when someone regenerated a link mid-listing. The script will refuse to auto-delete and print all matches with their `created_at`. Confirm with the user which to delete (usually all of them).
- **Already-sold items with stale live links** — discovered during the 2026-05-20 audit: RG-0002, RG-0003, RG-0005 were all marked SOLD on the site but had live `square.link/u/...` URLs. All three were cleaned up in commit `5d93566` and the API DELETE in the same session. If you find another, treat it exactly like a fresh sale — run this skill end-to-end. The item page may already be on the clean pattern, but the **gallery card is often the surface still left stale** (Step 1 detects the clean item page and routes you to Step 5 for exactly this). RG-0002 is the canonical example: item page migrated in `5d93566`, gallery card missed until `f05c330`. **Find these proactively with `delete_payment_link.py --audit`** (read-only) — it flags every live link whose item is already sold. RG-0014 (2026-06-20) extended this class: its link had **null `description` and `payment_note`**, so a SKU search couldn't see it at all and the helper said "no payment link found" — `--audit`, or a precise `--url` / `--order-id` / `--id`, is the only way to catch a null-metadata straggler.
- **User wants to "un-sell" an item** — out of scope for this skill. The Square payment link is gone permanently; regenerating one requires the `rg-item-update` flow (or a fresh listing) plus a manual `git revert` on the sold-state commit.

## Related skills

| Skill | When to use instead |
|---|---|
| `rg-item-update` | Price changes, description edits, image swaps on items that are STILL FOR SALE |
| `square-inventory-loss` | Items that left inventory without being sold (giveaway, damage, spoilage, theft) |
| `rg-full-auto` | Brand-new items being onboarded — never sold yet |
| `square-image-upload-cowork` | Replacing the hero image on an active listing (e.g., better photo) |
