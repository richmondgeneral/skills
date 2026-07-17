---
name: rg-square-list
description: List a Richmond General item on Square in one command — create (or idempotently update) the catalog ITEM from its label.json, set inventory, upload square.png as the primary image, mint a payment link, generate qr-buy.png + qr-info.png (BOTH QR codes, recorded in label.json → qr_codes), and write all IDs back into label.json. Use when an item is already intake-complete (priced + photographed, has items/RG-XXXX/label.json) and needs to go live on Square. Triggers on "list this on Square", "create the Square item", "push RG-XXXX to Square", "rg-square-list". NOT for full onboarding from a raw photo (use rg-full-auto), NOT for price changes on an already-listed item (use rg-reprice), NOT for sold items (use rg-item-mark-sold). Always preview with --dry-run before a live run; live runs mutate the production Square catalog.
metadata:
  version: "1.5"
  author: scottybe
  updated: "2026-07-15"
  changelog: |
    v1.5 - CREATE also uploads detail-*.jpeg as non-primary images (photo SET on Square;
    26 listings had 1 image vs 2-19 local details, 2026-07-15 audit). --skip-details opt-out;
    details >3.5MB skipped with a web_prep warning.

    v1.4 - Store description = brand voice: composed from label.json page.story (+ Condition
    line); CREATE warns when page.story is empty (store copy was shipping as bare condition
    notes — RG-0061 etc., 2026-07-15). _sparse_update_item latent 400 FIXED: /v2/catalog/object
    replaces item_data wholesale, so the update now GETs the full object and re-sends it with
    the patched fields (variations preserved — regression-tested).

    v1.3 - Processed-image gate: only the pipeline square.png uploads by default; raw
    square.jpg/hero.* refused (--allow-raw-image override). Dry-run reports image +
    image_processed.

    v1.2 - Emits BOTH QRs (qr-info.png added; was buy-only) and persists the resolved
    categories (type/tier/room/reporting) into channels.square.categories on CREATE
    (2026-07-15 RG-0071 run flagged both gaps).

    v1.1 - TYPE from label.json reporting_category_note (TYPE_CATEGORIES/ROOM_BY_TYPE); blocking Hero QA gate on CREATE (--skip-hero-qa override)

    v1.0 - Initial: one-command Square listing from label.json.
    - square_client.py: token (env->Keychain->.env), stdlib-urllib transport,
      constants, payment-link create/delete, set_inventory_count, gen_qr_png.
    - square_list.py: idempotent create-vs-sparse-update, inventory=1 on create,
      primary image, payment-link keep/recreate, qr-buy, write-back (object_id,
      variation_id, buy_link, payment_link_id, order_id, price, top-level state).
---

# rg-square-list

One command to take an intake-complete item live on Square. Replaces the ad-hoc per-call Square API python the postmortem flagged.

## Usage

```bash
# Always dry-run first — prints the plan, makes ZERO calls, writes nothing:
uv run --with "qrcode[pil]" python \
  skills/plugins/richmondgeneral/skills/rg-square-list/scripts/square_list.py \
  items/RG-XXXX --dry-run

# Live (mutates the production Square catalog):
uv run --with "qrcode[pil]" python \
  skills/plugins/richmondgeneral/skills/rg-square-list/scripts/square_list.py \
  items/RG-XXXX

# --force re-uploads the primary image on an UPDATE (otherwise image is create-only).
```

Over the Cowork osascript bridge, invoke by absolute interpreter path (the module is stdlib-only at import; `qrcode[pil]` is needed only for the QR step).

## What it does (in order)

1. Reads `items/RG-XXXX/label.json` (price, product_name, condition_notes, fulfillment, photos).
2. **Create vs update (idempotent):**
   - If `channels.square.object_id` is already set → **sparse-update** the item (name + description_html) — never creates a duplicate.
   - Else → `catalog/batch-upsert` create. **Write the brand-voice story FIRST.** The Square store description is composed from
`label.json → page.story` (the "curated mercantile" voice — see square-online:brand-voice)
plus a plain Condition line; with no story it degrades to spec-style notes and warns. eBay/
Marketplace copy is a DIFFERENT register (attributes/condition via seller-agent) — don't reuse
store prose there or vice versa.

**A CREATE first passes TWO image gates** — the pre-publish Hero QA gate — refused unless `label.json → hero_qa.status == "pass"` (or `photo_overrides.status == "approved"`); `--skip-hero-qa` = conscious override — AND the processed-image gate: the upload must be the
pipeline product `square.png` (matte.py or the flat-goods profile); a raw `square.jpg`/`hero.*`
is REFUSED (`--allow-raw-image` = conscious override). Raw in-situ shots reaching the storefront
(RG-0062/0064/0068, 2026-07-15) is the failure class this blocks. Item carries 3 categories `[TYPE, New Arrivals (tier), room]` — **TYPE resolves from `label.json → reporting_category_note`** (name match, e.g. "Books & Paper"; defaults to Collectibles WITH a warning when absent) and the room is the type's parent per ROOM_BY_TYPE — `reporting_category = TYPE`, one FIXED_PRICING variation at the label price, the tax id, `ecom_visibility: VISIBLE`. **IDs are persisted to label.json immediately after create** (before image/paylink) so a mid-flow failure never double-creates on re-run.
3. **Inventory:** sets the new variation to `IN_STOCK` quantity 1 (create path only) — without this the item lists "Sold out" and the payment link can't complete.
4. **Image:** uploads `square.png` as the **primary** catalog image (create path, or update + `--force`).
5. **Payment link (idempotent):** keeps the existing link if its recorded price matches; deletes + recreates on a price change (or an orphaned link with no recorded price); creates one if none. `ask_for_shipping_address` is set unless the item is `local_pickup_only`.
6. **QR:** renders `qr-buy.png` from the buy link and records it under `qr_codes.buy`.
7. **Write-back:** `channels.square` gets `object_id, variation_id, buy_link, payment_link_id, order_id, price, status:"listed"`, and the top-level lifecycle `state` becomes `"Listed"` (never downgrades `Sold`/`Archived`).

## Constants (canonical source: `scripts/square_client.py`)

Location `B87BAEZ0NWV34`, API version `2026-04-21`, tier New Arrivals `TGWDFETSQPR6BF67YJCTOLW6`, tax `LPKEJF7H27NOPK7EE6A5CA7V`; the full TYPE→id and TYPE→room maps live in `square_client.py` (`TYPE_CATEGORIES` / `ROOM_BY_TYPE`, mirroring rg-full-auto's square-catalog reference). Token resolves env → macOS Keychain → workspace `.env` (bridge-portable).

## Idempotency contract

Safe to re-run. It will never create a second catalog item for an item that already has an `object_id`, never duplicate the primary image on a plain re-run, and never leave two chargeable payment links at once (recreate is delete-then-create). `rg-reprice` reuses `square_client` for the price-change cascade.

## Tests

`uv run --with "qrcode[pil]" pytest skills/rg-square-list/tests/ -q` — all monkeypatch the HTTP seam; no test makes a live call.
