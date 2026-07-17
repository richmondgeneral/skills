# Seller Hub surface map

Sitemap for agent navigation of the **seller account**. Prefer plain URLs listed as **SAFE**.
Never use URLs marked **HANG**.

Last updated: 2026-07-17 (headed smoke: End listings / Sell similar / Drafts href).

---

## Safe vs hang URLs

| URL / pattern | Status | Notes |
|---|---|---|
| `https://www.ebay.com/sh/lst/active` | **SAFE** | Active listings home |
| `https://www.ebay.com/sh/lst/active?keyword=…` | **HANG** | Renderer freezes; type into search box instead |
| `…/lstng?…&mode=ReviseItem&itemId=…` | **HANG** | Deep-link revise; use Active → Edit |
| `https://www.ebay.com/sl/prelist/home` | **SAFE** | Create listing prelist (via **Create listing** button) |
| `https://www.ebay.com/sl/sell` | **SAFE-ish** | CREATE entry used by Playwright; prefer Seller Hub Create button when native |
| `https://www.ebay.com/itm/<itemId>` | **SAFE** | Public live page — **verification source of truth** |
| Drafts / Scheduled / Inactive | **SAFE via left rail** | Click left rail on Active page; avoid untested deep-links |

---

## Surfaces

### Active listings (P0 — verified)

- **Path:** Seller Hub → Listings → Active, or SAFE URL above.
- **Search:** "Search by title, SKU, or item number" — double-type after confirmation dialogs.
- **Row actions:** **Edit** opens revise form. Other row menus vary by listing state.
- **Stale data:** row price/title can lag; verify on `/itm/`.

### Drafts (P0 — verified link 2026-07-17)

- **Path:** left rail **Drafts** → href `/sh/lst/drafts` (SAFE relative URL under Seller Hub).
- Body text on Active page mentions Drafts; the rail link may be **off-screen / not visible** until the
  left nav is expanded — prefer `https://www.ebay.com/sh/lst/drafts` if the rail control is not
  visible (smoke 2026-07-17: locator found but not visible).
- **When:** CREATE crash mid-form auto-saves a draft.
- **Resume:** open matching title/SKU draft → continue "Complete your listing" → List it only if authorized.
- **Idempotency:** before a new CREATE, scan Drafts for the same title/SKU so you do not create a second draft/listing.

### CREATE prelist + complete form (P0 — verified)

See `field-map.md` CREATE section and `SKILL.md` recipe C.

### Revise form (P0 — verified)

See `field-map.md` Revise section and `SKILL.md` recipe B.

### End listing (P1 — live-probed 2026-07-17)

**Verified on Active listings** (`ebay_smoke_probe.py`, Seller Hub title "Manage active listings"):

| Control (visible text) | Tag | Notes |
|---|---|---|
| **End listings** | `BUTTON` | Bulk/toolbar action name is plural — select row(s) first, then click |
| **Sell similar** | `BUTTON` | Present on Active toolbar/row actions |
| **Edit** | `BUTTON` / `A` | Opens revise form |
| **Edit selected** / **Edit all N listings** | bulk | Multi-select editing |
| **Send offers** / **Send offers - eligible** | `BUTTON` | Promotional offers to watchers |
| **Edit Best Offer** | `BUTTON` | Per-listing Best Offer settings |
| **Promote** / **Promoted Listings** | `BUTTON` | Ads — not End |
| **Add/edit note** | `BUTTON` | Seller notes |
| **Assign/edit automation rule** | `BUTTON` | Automation |

**Agent path to end one listing (still confirm reason dialog on first real end):**

1. Active → search item number/SKU (double-type protocol) → **select the row checkbox**.
2. Click toolbar **End listings** (do not deep-link).
3. Complete reason/confirm modal if shown (document exact reason options on first live end).
4. Verify row gone from Active; live `/itm/<id>` shows ended; update `channels.ebay` / sold flow.
5. **Never** click End on a frozen tab; never bulk-end without an explicit multi-SKU authorization.

> Confirmation dialog reason codes were **not** exercised in the smoke probe (non-destructive).
> First production end should capture reason labels into this table.

### Sell similar / Create similar (P1 — live-probed toolbar)

- Active toolbar: **Sell similar** button (2026-07-17).
- Post-create/revise success dialog also offers **Create similar listing**.
- Still run Mandatory Protocol + Active/Drafts idempotency (similar ≠ automatic SKU).

### Best Offer / Offers (P1 — partial)

- Active: **Send offers**, **Edit Best Offer** buttons present (2026-07-17).
- CREATE **Allow offers** toggle; min/auto-accept thresholds not fully mapped.

### Orders / labels / messages (P2 — out of default listing scope)

Not required for list/revise. Document only when a task needs them.

### Business policies (P2 — partial)

- Shipping / payment / return policies appear as dropdowns/comboboxes on CREATE.
- Capture **exact account policy names** when selecting; do not invent policy IDs here (API skill owns IDs).

---

## Left-rail inventory (Active page)

Typical Seller Hub Listings rail (labels may shift):

- Active
- Drafts
- Scheduled
- Inactive / Unsold / Ended (naming varies)

Prefer clicking rail items over guessing query-string URLs.

---

## Live verification checklist (any mutating task)

1. Intended item ID known (from dialog, `channels.ebay`, or Active search).
2. Fresh tab → `https://www.ebay.com/itm/<id>`.
3. Title contains expected keywords; price shows expected `US $…`; listing is active (or ended, if that was the goal).
4. Only then write success to `label.json`.
