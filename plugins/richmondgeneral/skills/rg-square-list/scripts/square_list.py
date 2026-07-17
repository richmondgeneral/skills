#!/usr/bin/env python3
"""rg-square-list — create or update a Square catalog item from a label.json (Phase C2).

Single CLI that takes an item directory (``items/RG-XXXX/``), reads its
``label.json``, and brings the item live on Square **idempotently**:

  * **First run (no ``channels.square.object_id``):** CREATE the catalog ITEM via
    ``catalog/batch-upsert`` (mirroring rg-full-auto's ``_build_catalog_object``
    shape exactly — type+tier categories, reporting_category, one FIXED_PRICING
    variation), upload ``square.png`` as the PRIMARY image, and create a
    catalog-linked payment link.
  * **Re-run (``object_id`` set):** never create a duplicate. Fetch the item's
    current version and issue a **sparse** ITEM update (only name/description),
    leaving the variation/price/categories untouched. Skip the image (re-upload
    would duplicate) unless ``--force``. Keep the existing payment link unless the
    price changed (then delete the old one and create a new one).

Then it writes the resolved Square ids back into ``channels.square`` and sets
``status:"listed"``. ``--dry-run`` makes ZERO network calls and ZERO writes.

Runtime deps: Python 3 **stdlib only**, plus the same-dir ``square_client`` (the
shared Phase C1 transport). The image upload reuses the already-built
``square-image-upload/scripts/upload_image.py`` ``create_catalog_image`` — added
to ``sys.path`` and imported lazily inside ``_create_catalog_image`` so importing
THIS module never requires ``requests`` (and tests can monkeypatch the seam).

Network goes through exactly two seams — ``square_request`` (imported from
``square_client``) and ``_create_catalog_image`` — both monkeypatched by the test
suite, so nothing ever hits Square in tests.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path
from typing import Optional

# Same-dir import (works when this script is run directly, from an orchestrator,
# or over the osascript bridge). Mirrors test_square_client's path convention.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from square_client import (  # noqa: E402
    CAT_COLLECTIBLES,
    CAT_NEW_ARRIVALS,
    CAT_VINTAGE_MARKET,
    ROOM_BY_TYPE,
    TYPE_CATEGORIES,
    LOCATION_ID,
    TAX_ID,
    build_payment_link_body,
    create_payment_link,
    delete_payment_link,
    dollars_to_cents,
    gen_qr_png,
    resolve_token,
    set_inventory_count,
    square_request,
)

# Public item-page base — payment-link redirect lands the buyer on the GitHub
# Pages card after checkout.
ITEM_PAGE_BASE = "https://richmondgeneral.github.io/items"

# Candidate primary-image filenames, in preference order.
_IMAGE_CANDIDATES = ("square.png", "square.jpg", "hero.png", "hero.jpg")


# -----------------------------------------------------------------------------
# Image-upload seam — lazily imports the real multipart uploader so this module
# loads without `requests`. Tests monkeypatch THIS function (never the real one).
# -----------------------------------------------------------------------------

def _create_catalog_image(access_token, image_path, object_id=None, name=None,
                          caption=None, is_primary=False, api_version=None):
    """Upload an image to Square and attach it to ``object_id``.

    Thin indirection over square-image-upload's ``create_catalog_image``. The
    import is INSIDE the function (not at module import time) so:
      * importing ``square_list`` never requires ``requests`` (kept stdlib-clean
        for the bridge), and
      * the test suite can monkeypatch ``square_list._create_catalog_image``
        without the real module — or ``requests`` — being present.
    """
    upload_dir = (
        Path(__file__).resolve().parents[2]
        / "square-image-upload" / "scripts"
    )
    if str(upload_dir) not in sys.path:
        sys.path.insert(0, str(upload_dir))
    from upload_image import create_catalog_image  # noqa: PLC0415

    kwargs = dict(object_id=object_id, name=name, caption=caption,
                  is_primary=is_primary)
    if api_version is not None:
        kwargs["api_version"] = api_version
    return create_catalog_image(access_token, image_path, **kwargs)


# -----------------------------------------------------------------------------
# Catalog object — mirrors rg-full-auto/process_new_item._build_catalog_object.
# -----------------------------------------------------------------------------

def _compose_description(story: str, notes: str) -> str:
    """Store description: brand-voice story first, condition stated plainly after.
    Falls back to notes-only when no story exists (with the CREATE-time warning)."""
    import html as _html
    parts = []
    if story:
        parts.append(f"<p>{_html.escape(story)}</p>")
    if notes:
        label_txt = "<strong>Condition:</strong> " if story else ""
        parts.append(f"<p>{label_txt}{_html.escape(notes)}</p>")
    return "".join(parts) or "<p></p>"


def resolve_type_category(label: dict) -> str:
    """Resolve the TYPE category id from ``label["reporting_category_note"]``.

    Name-matches (case-insensitive) against TYPE_CATEGORIES. When the note is
    absent or unrecognized, defaults to Collectibles and prints a warning —
    the wrong reporting category silently skews Square sales reports, so set
    the note in label.json (e.g. "Books & Paper") for non-Collectibles items.
    """
    note = (label.get("reporting_category_note") or "").strip().lower()
    if note in TYPE_CATEGORIES:
        return TYPE_CATEGORIES[note]
    if note:
        print(f"[warn] reporting_category_note {label.get('reporting_category_note')!r} "
              f"doesn't match a known TYPE category — defaulting to Collectibles",
              file=sys.stderr)
    else:
        print("[warn] label.json has no reporting_category_note — TYPE defaulting to "
              "Collectibles (set it if this item isn't a Collectible)", file=sys.stderr)
    return CAT_COLLECTIBLES


def hero_qa_ok(label: dict) -> bool:
    """Pre-publish Hero QA gate (canon: no hero publishes without a pass).

    Passes when ``hero_qa.status == "pass"`` OR ``photo_overrides.status ==
    "approved"`` (the documented visual-check override for e.g. the
    radially-symmetric level false-positive).
    """
    if ((label.get("hero_qa") or {}).get("status")) == "pass":
        return True
    return ((label.get("photo_overrides") or {}).get("status")) == "approved"


def build_catalog_object(sku: str, label: dict) -> dict:
    """Build the ITEM upsert object for ``catalog/batch-upsert`` (CREATE path).

    Mirrors rg-full-auto's ``_build_catalog_object``: TYPE resolved from
    ``label.json → reporting_category_note`` (name match against TYPE_CATEGORIES;
    defaults to Collectibles WITH A WARNING when absent/unknown), TIER = New
    Arrivals (the intake default), plus the ROOM = the type's parent room per
    ROOM_BY_TYPE, so ``categories = [type, tier, room]`` and
    ``reporting_category = type``. The room category is required or the item is
    missing from the room-level Shop All grid. One FIXED_PRICING ITEM_VARIATION priced from ``label["price"]``.
    ``#``-prefixed temp ids (``#RG-XXXX`` / ``#RG-XXXX-var``) are resolved to real
    ids from the response ``id_mappings``.
    """
    price_cents = dollars_to_cents(label["price"])
    name = label["product_name"]
    notes = label.get("condition_notes") or ""
    story = ((label.get("page") or {}).get("story") or "").strip()
    if not story:
        print("  [warn] page.story is EMPTY — the store description will be spec-style "
              "condition notes. Write the brand-voice story (square-online:brand-voice) "
              "in label.json -> page.story first for a store-quality listing.",
              file=sys.stderr)
    type_id = resolve_type_category(label)
    room_id = ROOM_BY_TYPE.get(type_id, CAT_VINTAGE_MARKET)

    item_data = {
        "name": name,
        "categories": [
            {"id": type_id},              # TYPE (from reporting_category_note)
            {"id": CAT_NEW_ARRIVALS},     # TIER (intake default)
            {"id": room_id},              # ROOM (type's parent, ROOM_BY_TYPE)
        ],
        "reporting_category": {"id": type_id},
        "tax_ids": [TAX_ID],
        "is_taxable": True,
        "ecom_visibility": "VISIBLE",
        "variations": [{
            "type": "ITEM_VARIATION",
            "id": f"#{sku}-var",
            "present_at_all_locations": False,
            "present_at_location_ids": [LOCATION_ID],
            "item_variation_data": {
                "item_id": f"#{sku}",
                "name": "Regular",
                "sku": sku,
                "pricing_type": "FIXED_PRICING",
                "price_money": {"amount": price_cents, "currency": "USD"},
                "track_inventory": True,
                "sellable": True,
                "stockable": True,
            },
        }],
    }
    if notes:
        # ONLY description_html (per process_new_item v3.2): the storefront
        # renders this; the deprecated plain `description` field would show raw
        # HTML tags on richmondgeneral.com, so it is intentionally NOT set.
        item_data["description_html"] = _compose_description(story, notes)

    return {
        "type": "ITEM",
        "id": f"#{sku}",
        "present_at_all_locations": False,
        "present_at_location_ids": [LOCATION_ID],
        "item_data": item_data,
    }


# -----------------------------------------------------------------------------
# Helpers.
# -----------------------------------------------------------------------------

def _local_pickup_only(label: dict) -> bool:
    """True when the item is pickup-only (so the payment link skips shipping)."""
    if label.get("fulfillment") == "local_pickup_only":
        return True
    shipping = label.get("shipping") or {}
    return bool(shipping.get("local_pickup_only"))


def _find_image(item_dir: Path) -> Optional[Path]:
    """Return the first existing primary-image candidate in ``item_dir``."""
    for name in _IMAGE_CANDIDATES:
        candidate = item_dir / name
        if candidate.exists():
            return candidate
    return None


def _image_is_processed(img: Optional[Path]) -> bool:
    """True only for the pipeline product (square.png from matte/flat-goods).

    Raw fallbacks (square.jpg, hero.*) are how RG-0062/0064/0068 shipped in-situ
    display-case shots with inverted rotations to the storefront (2026-07-15).
    """
    return img is not None and img.name == "square.png"


def _extract_catalog_ids(result: dict, sku: str) -> tuple[str, str]:
    """Resolve (item_id, variation_id) from a batch-upsert response.

    Prefers ``id_mappings`` (the reliable readback per process_new_item), then
    falls back to walking the returned objects.
    """
    temp_item = f"#{sku}"
    temp_var = f"#{sku}-var"

    mapped = {
        m.get("client_object_id"): m.get("object_id")
        for m in (result.get("id_mappings") or [])
        if m.get("client_object_id") and m.get("object_id")
    }
    item_id = mapped.get(temp_item)
    variation_id = mapped.get(temp_var)

    if not item_id or not variation_id:
        obj = result.get("catalog_object")
        if not obj:
            objs = result.get("objects") or []
            obj = objs[0] if objs else {}
        if not item_id:
            item_id = obj.get("id")
        if not variation_id:
            variations = (obj.get("item_data") or {}).get("variations") or []
            if variations:
                variation_id = variations[0].get("id")

    if not item_id or not variation_id:
        raise RuntimeError(
            "Could not resolve catalog item/variation ids from Square response: "
            f"{json.dumps(result)}"
        )
    return item_id, variation_id


def _get_catalog_object(token: str, object_id: str) -> dict:
    """GET a catalog object and return its parsed ``object`` dict.

    The single readback used both for the sparse-update version and to recover a
    missing variation id (so the UPDATE path needs only ONE GET, not two).
    """
    status, parsed = square_request(
        "GET", f"/v2/catalog/object/{object_id}", token
    )
    if not (200 <= status < 300):
        raise RuntimeError(
            f"GET catalog object {object_id} failed: {status}: "
            f"{json.dumps(parsed)}"
        )
    return parsed.get("object") or {}


def _get_object_version(token: str, object_id: str) -> int:
    """Fetch an object's current ``version`` (required for a sparse update)."""
    obj = _get_catalog_object(token, object_id)
    version = obj.get("version")
    if version is None:
        raise RuntimeError(
            f"No version on fetched object {object_id}: version missing"
        )
    return version


def _variation_id_from_object(obj: dict) -> Optional[str]:
    """Pull the first variation id out of a fetched catalog ITEM object."""
    variations = (obj.get("item_data") or {}).get("variations") or []
    if variations:
        return variations[0].get("id")
    return None


def _sparse_update_item(token: str, object_id: str, label: dict,
                        version: Optional[int] = None) -> None:
    """Update ONLY name/description, preserving variation/price/categories/images.

    ⚠️ `/v2/catalog/object` upserts item_data WHOLESALE at this API version — sending
    only {name, description} 400s with "must have at least one variation" (latent bug
    found live 2026-07-15). So: GET the full object, patch the fields inside its OWN
    item_data, and re-send the complete object (the safe GET-first full upsert).
    """
    status, parsed = square_request("GET", f"/v2/catalog/object/{object_id}", token)
    if status != 200:
        raise RuntimeError(
            f"fetch of {object_id} failed: {status}: {json.dumps(parsed)}"
        )
    obj = parsed["object"]
    obj.setdefault("type", "ITEM")
    obj.setdefault("item_data", {})
    story = ((label.get("page") or {}).get("story") or "").strip()
    notes = label.get("condition_notes") or ""
    obj["item_data"]["name"] = label["product_name"]
    # description_html only — plain `description` is deprecated (renders raw
    # HTML tags on the storefront). Matches build_catalog_object.
    obj["item_data"]["description_html"] = _compose_description(story, notes)
    obj["item_data"].pop("description", None)            # deprecated plain field
    obj["item_data"].pop("description_plaintext", None)  # server-derived, read-only

    body = {"idempotency_key": str(uuid.uuid4()), "object": obj}
    status, parsed = square_request("POST", "/v2/catalog/object", token, body=body)
    if not (200 <= status < 300):
        raise RuntimeError(
            f"Sparse update of {object_id} failed: {status}: {json.dumps(parsed)}"
        )


def _create_item(token: str, sku: str, label: dict) -> tuple[str, str]:
    """CREATE the catalog item via batch-upsert; return (item_id, variation_id)."""
    obj = build_catalog_object(sku, label)
    body = {
        "idempotency_key": str(uuid.uuid4()),
        "batches": [{"objects": [obj]}],
    }
    status, parsed = square_request(
        "POST", "/v2/catalog/batch-upsert", token, body=body
    )
    if not (200 <= status < 300):
        raise RuntimeError(
            f"batch-upsert create failed: {status}: {json.dumps(parsed)}"
        )
    return _extract_catalog_ids(parsed, sku)


def _ensure_payment_link(token: str, sku: str, label: dict, variation_id: str,
                         price_cents: int, existing: dict) -> dict:
    """Idempotently ensure a payment link at the current price.

    Keep the recorded link if its price matches; recreate (delete old → create
    new) if the price changed OR the recorded price is unknown; create one if
    none exists. Returns the live ``payment_link`` object (with
    ``id``/``url``/``order_id``) or, when kept, a dict echoing the recorded
    fields.
    """
    old_id = existing.get("payment_link_id")
    recorded_price = existing.get("price")

    if old_id:
        # A recorded link id whose price matches the current price → keep it.
        # Compare in cents so "65" / "65.0" / "65.00" / "$65.00" all match.
        if recorded_price is not None and \
                dollars_to_cents(recorded_price) == price_cents:
            return {
                "id": old_id,
                "url": existing.get("buy_link"),
                "order_id": existing.get("order_id"),
                "kept": True,
            }
        # Price changed OR is unknown (foreign/hand-edited label with a link id
        # but no sibling `price`) → kill the stale link before minting a fresh
        # one, never blind-create a SECOND live link beside a chargeable old one.
        delete_payment_link(token, old_id)

    body = build_payment_link_body(
        name=label["product_name"],
        variation_id=variation_id,
        price_cents=price_cents,
        sku=sku,
        redirect_url=f"{ITEM_PAGE_BASE}/{sku}/",
        ask_shipping=(not _local_pickup_only(label)),
        idempotency_key=str(uuid.uuid4()),
    )
    return create_payment_link(token, body)


def _write_label(label_path: Path, label: dict) -> None:
    """Write ``label`` to ``label_path`` as pretty JSON with a trailing newline.

    The single label.json writer — used both for the early post-create id
    persist (I1) and the final full write-back, so the formatting contract
    (2-space indent, ``ensure_ascii=False``, trailing ``\\n``) is identical for
    every write.
    """
    label_path.write_text(
        json.dumps(label, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


# -----------------------------------------------------------------------------
# Orchestrator.
# -----------------------------------------------------------------------------

def list_item(item_dir: str, dry_run: bool = False, force: bool = False,
              skip_hero_qa: bool = False, allow_raw_image: bool = False,
              skip_details: bool = False) -> dict:
    """Create or update the item's Square listing; return a summary dict.

    See the module docstring for the full idempotency contract. In ``dry_run``
    no token is resolved, NO network call is made, and label.json is NOT written
    — a planned-action summary is returned instead.
    """
    item_path = Path(item_dir)
    label_path = item_path / "label.json"
    label = json.loads(label_path.read_text(encoding="utf-8"))

    sku = label["sku"]
    price_cents = dollars_to_cents(label["price"])
    price_str = f"{price_cents / 100:.2f}"
    channels = label.get("channels") or {}
    square = channels.get("square") or {}
    existing_object_id = square.get("object_id")
    qa_ok = hero_qa_ok(label)

    if dry_run:
        return {
            "dry_run": True,
            "sku": sku,
            "action": "update" if existing_object_id else "create",
            "price": price_str,
            "object_id": existing_object_id,
            "would_upload_image": (not existing_object_id) or force,
            "image": (lambda i: i.name if i else None)(_find_image(item_path)),
            "image_processed": _image_is_processed(_find_image(item_path)),
            "local_pickup_only": _local_pickup_only(label),
            "hero_qa_ok": qa_ok,
        }

    # Pre-publish Hero QA gate: a CREATE puts the hero live on Square — refuse
    # without a hero_qa pass (or the documented photo_overrides approval).
    if not existing_object_id and not qa_ok and not skip_hero_qa:
        raise SystemExit(
            f"REFUSED: {sku} has no hero_qa pass (label.json hero_qa.status != 'pass' "
            f"and no photo_overrides approval). Run hero_qa.py, fix or approve the "
            f"hero, then retry — or pass --skip-hero-qa to override consciously."
        )

    token = resolve_token()

    # --- Item: CREATE vs sparse UPDATE (never duplicate) ---------------------
    if existing_object_id:
        # UPDATE path. Re-fetch the catalog object ONCE: it gives both the
        # version for the sparse update AND lets us recover a missing
        # variation_id (foreign / hand-edited label) BEFORE any payment-link
        # work — otherwise a paylink recreate would delete the old link and
        # build a new one with catalog_object_id=None (I3).
        obj = _get_catalog_object(token, existing_object_id)
        version = obj.get("version")
        if version is None:
            raise RuntimeError(
                f"No version on fetched object {existing_object_id}: "
                "version missing"
            )
        item_id = existing_object_id
        variation_id = square.get("variation_id")
        if not variation_id:
            variation_id = _variation_id_from_object(obj)
        if not variation_id:
            raise RuntimeError(
                f"Could not resolve variation_id for {existing_object_id} "
                "(missing from label.json AND from the fetched catalog object); "
                "refusing to touch the payment link without it."
            )
        _sparse_update_item(token, existing_object_id, label, version=version)
        created = False
    else:
        item_id, variation_id = _create_item(token, sku, label)
        created = True
        # I1: persist the new ids to label.json IMMEDIATELY — before the image /
        # inventory / paylink steps — so if any of those fail, a re-run resumes
        # in the UPDATE branch instead of double-creating the catalog item.
        square["object_id"] = item_id
        square["variation_id"] = variation_id
        channels["square"] = square
        label["channels"] = channels
        _write_label(label_path, label)
        # C1: a freshly-created item tracks inventory but lists at 0 → "Sold
        # out". Set the on-hand count to 1 so it's purchasable. Create path ONLY
        # (a re-run/UPDATE never re-stocks).
        set_inventory_count(token, variation_id, qty=1)

    # --- Image: only on create, or on an explicit --force update -------------
    image_uploaded = False
    details_uploaded = 0
    if created or force:
        img = _find_image(item_path)
        if img is not None and not _image_is_processed(img) and not allow_raw_image:
            raise SystemExit(
                f"REFUSED: {sku}'s only image is RAW ({img.name}) — the pipeline product "
                f"square.png is missing. Run the image pipeline first "
                f"(matte.py --item-dir items/{sku}, or the flat-goods deskew profile), "
                f"re-run hero_qa, then retry — or pass --allow-raw-image to override "
                f"consciously."
            )
        if img is not None:
            _create_catalog_image(
                token, str(img), object_id=item_id,
                name=sku, caption=label.get("product_name"),
                is_primary=True,
            )
            image_uploaded = True
        # Detail images: the photo SET sells the item — 26 listings shipped with a
        # single image while 2–19 details sat local (2026-07-15 audit). Uploaded
        # non-primary, in name order, on CREATE only (re-runs would duplicate).
        if created and not skip_details:
            for dpath in sorted(item_path.glob("detail-*.jp*g")) + sorted(item_path.glob("detail-*.png")):
                if dpath.stat().st_size > 3_500_000:
                    print(f"  [warn] {dpath.name} skipped: {dpath.stat().st_size//1_000_000}MB "
                          f"(web-prep it first: image-processor/scripts/web_prep.py)",
                          file=sys.stderr)
                    continue
                _create_catalog_image(
                    token, str(dpath), object_id=item_id,
                    name=f"{sku} {dpath.stem}", caption=label.get("product_name"),
                    is_primary=False,
                )
                details_uploaded += 1

    # --- Payment link: idempotent on price -----------------------------------
    link = _ensure_payment_link(
        token, sku, label, variation_id, price_cents, square
    )
    payment_link_id = link.get("id")
    buy_link = link.get("url")
    order_id = link.get("order_id")

    # --- M2: render the buy QR (the "two QR codes" contract) -----------------
    qr_buy_recorded = False
    if buy_link:
        qr_path = item_path / "qr-buy.png"
        try:
            gen_qr_png(buy_link, str(qr_path))
            qr_codes = label.get("qr_codes") or {}
            qr_codes["buy"] = {
                "url": buy_link,
                "file": "qr-buy.png",
                "use": "Square checkout — scan to buy",
            }
            label["qr_codes"] = qr_codes
            qr_buy_recorded = True
        except ImportError:
            # Optional dep (`qrcode[pil]`) absent → degrade with a clear note,
            # never crash a successful listing over a missing QR image.
            print(
                "  [warn] qr-buy.png NOT generated: the `qrcode` package is not "
                "installed (re-run under uv with --with \"qrcode[pil]\")."
            )

    # --- Info QR (price tag -> GitHub item page): the OTHER half of the two-QR
    # contract. rg-square-list used to emit only qr-buy (2026-07-15 RG-0071 run).
    qr_info_recorded = False
    info_url = f"https://richmondgeneral.github.io/items/{sku}/"
    info_path = item_path / "qr-info.png"
    try:
        if not info_path.exists():
            gen_qr_png(info_url, str(info_path))
        qr_codes = label.get("qr_codes") or {}
        info = qr_codes.get("info") or {}
        info.update({"url": info_url, "file": "qr-info.png",
                     "use": "price tag — scan for item card"})
        info.pop("status", None)  # clear any intake "stub" marker
        qr_codes["info"] = info
        label["qr_codes"] = qr_codes
        qr_info_recorded = True
    except ImportError:
        print("  [warn] qr-info.png NOT generated: the `qrcode` package is not "
              "installed (re-run under uv with --with \"qrcode[pil]\").")

    # --- Persist the resolved categories back into the record (Square had them,
    # label.json didn't — 2026-07-15 RG-0071 run) --------------------------------
    if created:
        type_id = resolve_type_category(label)
        square["categories"] = {
            "type": type_id,
            "tier": CAT_NEW_ARRIVALS,
            "room": ROOM_BY_TYPE.get(type_id, CAT_VINTAGE_MARKET),
            "reporting_category": type_id,
        }

    # --- Write back into channels.square -------------------------------------
    square.update({
        "object_id": item_id,
        "variation_id": variation_id,
        "buy_link": buy_link,
        "payment_link_id": payment_link_id,
        "order_id": order_id,
        "price": price_str,
        "status": "listed",
    })
    channels["square"] = square
    label["channels"] = channels
    # I2: the gallery gate + reconcile key off the TOP-LEVEL `state`. Promote to
    # "Listed" on success — but never DOWNGRADE a "Sold"/"Archived" item.
    if label.get("state") not in ("Sold", "Archived"):
        label["state"] = "Listed"
    _write_label(label_path, label)

    return {
        "dry_run": False,
        "sku": sku,
        "created": created,
        "object_id": item_id,
        "variation_id": variation_id,
        "buy_link": buy_link,
        "payment_link_id": payment_link_id,
        "order_id": order_id,
        "price": price_str,
        "image_uploaded": image_uploaded,
        "details_uploaded": details_uploaded,
        "qr_buy": qr_buy_recorded,
        "qr_info": qr_info_recorded,
    }


# -----------------------------------------------------------------------------
# CLI.
# -----------------------------------------------------------------------------

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Create or update a Square catalog item (+image +payment link) from "
            "an item's label.json. Idempotent: re-runs sparse-update, never "
            "duplicate."
        )
    )
    parser.add_argument("item_dir", help="Path to the item dir (items/RG-XXXX/)")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Plan only — zero network calls, no label.json write.",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="On an update, also re-upload the primary image.",
    )
    parser.add_argument(
        "--skip-hero-qa", action="store_true",
        help="Override the pre-publish Hero QA gate (conscious override only).",
    )
    parser.add_argument(
        "--skip-details", action="store_true",
        help="Skip uploading detail-*.jpeg images after the primary (CREATE only).",
    )
    parser.add_argument(
        "--allow-raw-image", action="store_true",
        help="Allow uploading a raw (non-pipeline) image — square.jpg/hero.* "
             "(conscious override; the default requires the matte/flat-goods square.png).",
    )
    args = parser.parse_args(argv)

    summary = list_item(args.item_dir, dry_run=args.dry_run, force=args.force,
                        skip_hero_qa=args.skip_hero_qa,
                        allow_raw_image=args.allow_raw_image,
                        skip_details=args.skip_details)

    if summary.get("dry_run"):
        print(f"[dry-run] {summary['sku']}: would {summary['action']} "
              f"at ${summary['price']} "
              f"(upload image: {summary['would_upload_image']}, "
              f"pickup-only: {summary['local_pickup_only']})")
    else:
        verb = "created" if summary["created"] else "updated"
        print(f"{summary['sku']}: {verb} Square item {summary['object_id']} "
              f"@ ${summary['price']}")
        print(f"  variation:    {summary['variation_id']}")
        print(f"  payment link: {summary['payment_link_id']}")
        print(f"  buy link:     {summary['buy_link']}")
        print(f"  image:        "
              f"{'uploaded' if summary['image_uploaded'] else 'unchanged'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
