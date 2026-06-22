---
name: rg-reprice
description: Change the price of an already-listed Richmond General item in one command — cascade the new price across every surface (Square catalog variation, Square payment link, qr-buy.png, label.json, the GitHub Pages item page, and the gallery card). Use when an item is live and only the PRICE is changing. Triggers on "reprice RG-XXXX to $Y", "change the price of RG-XXXX", "drop the price", "mark down RG-XXXX", "rg-reprice". NOT for a brand-new listing from a label.json (use rg-square-list), NOT for full onboarding from a raw photo (use rg-full-auto), NOT for sold items (use rg-item-mark-sold). Always preview with --dry-run before a live run; live runs mutate the production Square catalog AND recreate the payment link.
metadata:
  version: "1.0"
  author: scottybe
  updated: "2026-06-21"
  changelog: |
    v1.0 - Initial: one-command price-change cascade (Phase D).
    - reprice.py: Square variation fetch-patch-upsert, payment-link delete+recreate
      at the new price, qr-buy regenerate, label.json (price/price_status/
      channels.square/refinement_log), item-page + gallery-card rebuild, pricing-
      report reminder. Remote-first ordering so the local builders pick up the new
      price + buy link.
    - Reuses rg-square-list/scripts/square_client.py cross-skill (token, transport,
      build_payment_link_body, create/delete_payment_link, dollars_to_cents,
      gen_qr_png) — no reimplementation.
---

# rg-reprice

One command to change a **listed** item's price everywhere it lives. It reuses the shared Square client from `rg-square-list` and follows the same fetch-patch-upsert + payment-link-recreate patterns, so a price change never drifts between Square, the buy link, the QR, the item page, and the gallery card.

This is the dedicated path for a **price-only** change on an item that is already live on Square (it requires `channels.square.object_id` + `variation_id`). For a first-time listing use `rg-square-list`; for full onboarding use `rg-full-auto`; for a sale use `rg-item-mark-sold`.

## Usage

```bash
# Always dry-run first — prints the full plan, makes ZERO calls, writes nothing:
uv run --with "qrcode[pil]" python \
  skills/plugins/richmondgeneral/skills/rg-reprice/scripts/reprice.py \
  RG-XXXX 65 --dry-run

# Live (mutates the production Square catalog + recreates the payment link):
uv run --with "qrcode[pil]" python \
  skills/plugins/richmondgeneral/skills/rg-reprice/scripts/reprice.py \
  RG-XXXX 65

# --date stamps price_status + the refinement_log entry (default: today, ISO):
... reprice.py RG-XXXX 65 --date 2026-06-21
```

Price accepts `65`, `65.00`, `$65`, `$1,234.56` (parsed by `square_client.dollars_to_cents`). Over the Cowork osascript bridge, invoke by absolute interpreter path — the module is stdlib-only at import; `qrcode[pil]` is needed only for the QR step.

## The cascade (remote first, then local — in order)

1. **(a) Square variation price** — `GET /v2/catalog/object/{variation_id}`, patch only `item_variation_data.price_money` to the new cents, then `POST /v2/catalog/batch-upsert` with the object carrying its **fetched version** (the safe fetch-patch-upsert — sku and pricing_type are preserved). Raises on a non-2xx.
2. **(b) Payment link** — a Square payment link's amount is fixed at creation, so a price change is a **recreate**: `delete_payment_link(old_id)` **then** `create_payment_link(...)` at the new price (catalog-linked to the variation; `ask_for_shipping_address` is off when the item is `local_pickup_only`). Delete-before-create means there is never a window with two chargeable links. **If the delete succeeds but the recreate then fails, the item has the new catalog price but NO live buy link** — just **re-run `rg-reprice` (it's idempotent and recovers)**: the now-missing old link is a no-op delete and a fresh link is minted at the (already-correct) catalog price.
3. **(c) QR** — regenerate `qr-buy.png` for the new checkout URL (a missing `qrcode` dep warns, doesn't crash the cascade).
4. **(d) label.json** — set `price` + `price_status` ("final — $NEW (repriced from $OLD on DATE)"), update `channels.square.{price, buy_link, payment_link_id, order_id}`, and append a dated `{date, note:"Repriced $OLD -> $NEW."}` entry to `estimates.refinement_log` (created if absent). Written with 2-space indent, `ensure_ascii=False`, trailing newline — same contract as `rg-square-list`.
5. **(e) Item page** — `items/scripts/build_item_page.py RG-XXXX` (cwd = the **workspace root**, located at runtime via `_find_repo_root` by searching cwd then this file's ancestors for `items/scripts/build_item_page.py` — so the dual-copy cache anchors to the real workspace, never `~/.claude/plugins/cache`) so the printed/visible price + buy link refresh. `check=False`: a protected / living-test / sold page is a deliberate skip, not a failure, so the cascade does not hard-fail on it — but a **non-zero builder exit prints a loud STALE-price warning to stderr** (and `main()` exits non-zero) so a genuine build failure isn't silently swallowed.
6. **(f) Gallery card** — `items/scripts/build_gallery.py --update-card RG-XXXX` so the landing-grid card price updates.
7. **(g) Reminder** — prints `⚠ Update ops/pricing/RG-XXXX-pricing.md with the new comp basis + date.` (the private pricing report is not auto-edited — record the reasoning behind the new price yourself).

Steps 1–3 run against Square **before** the label write so steps 5–6 read the just-written new price + new buy link out of `label.json`.

## Reuse of `square_client` (no reimplementation)

`reprice.py` adds the sibling `rg-square-list/scripts` to `sys.path` (relative to its own `__file__`) and imports `square_client`, reusing: `resolve_token` (env → macOS Keychain → workspace `.env`, bridge-portable), `square_request` (stdlib-urllib transport), `build_payment_link_body`, `create_payment_link`, `delete_payment_link`, `dollars_to_cents`, `gen_qr_png`, and the canonical constants (location, API version, category/tax ids). It does **not** re-implement any of these. Network + QR + subprocess are the only seams; the test suite monkeypatches them so nothing hits Square or spawns a builder.

## Dry-run-first guard

`--dry-run` builds and prints the full plan (old price, new price, every step, the redirect URL, pickup-only flag) and returns it **without** resolving a token, calling Square, writing `label.json`, generating a QR, or spawning the page/gallery builders. Run it first on every reprice; the live run mutates the production catalog and **recreates the chargeable payment link**, so preview before you commit.

## Tests

`uv run --with "qrcode[pil]" pytest skills/rg-reprice/tests/ -q` — all seams monkeypatched (Square transport, payment-link create/delete, QR, and `subprocess.run`); no test makes a live call, writes a PNG, or spawns a builder. Covers: the variation upsert carries the fetched version + new cents; delete-before-create ordering; the full label patch incl. the dated refinement_log entry; page-then-gallery cascade ordering after the label write; and the dry-run no-side-effects guarantee (zero calls, byte-identical label.json).
