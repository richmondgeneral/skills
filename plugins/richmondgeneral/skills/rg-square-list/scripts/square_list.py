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
    LOCATION_ID,
    TAX_ID,
    build_payment_link_body,
    create_payment_link,
    delete_payment_link,
    dollars_to_cents,
    resolve_token,
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

def build_catalog_object(sku: str, label: dict) -> dict:
    """Build the ITEM upsert object for ``catalog/batch-upsert`` (CREATE path).

    Mirrors rg-full-auto's ``_build_catalog_object`` exactly for the rg-square-list
    case: TYPE = Collectibles, TIER = New Arrivals (the intake default), plus the
    ROOM = The Vintage Market (Collectibles' parent room per ROOM_BY_TYPE), so
    ``categories = [type, tier, room]`` and ``reporting_category = type``. The
    room category is required or the item is missing from the room-level Shop All
    grid. One FIXED_PRICING ITEM_VARIATION priced from ``label["price"]``.
    ``#``-prefixed temp ids (``#RG-XXXX`` / ``#RG-XXXX-var``) are resolved to real
    ids from the response ``id_mappings``.
    """
    price_cents = dollars_to_cents(label["price"])
    name = label["product_name"]
    notes = label.get("condition_notes") or ""

    item_data = {
        "name": name,
        "categories": [
            {"id": CAT_COLLECTIBLES},     # TYPE
            {"id": CAT_NEW_ARRIVALS},     # TIER (intake default)
            {"id": CAT_VINTAGE_MARKET},   # ROOM (Collectibles' parent, ROOM_BY_TYPE)
        ],
        "reporting_category": {"id": CAT_COLLECTIBLES},
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
        # Plain `description` plus an HTML mirror (`<p>…</p>`) — the storefront
        # renders description_html; the plain field is kept for API consumers.
        item_data["description"] = notes
        item_data["description_html"] = f"<p>{notes}</p>"

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


def _get_object_version(token: str, object_id: str) -> int:
    """Fetch an object's current ``version`` (required for a sparse update)."""
    status, parsed = square_request(
        "GET", f"/v2/catalog/object/{object_id}", token
    )
    if not (200 <= status < 300):
        raise RuntimeError(
            f"GET catalog object {object_id} failed: {status}: "
            f"{json.dumps(parsed)}"
        )
    obj = parsed.get("object") or {}
    version = obj.get("version")
    if version is None:
        raise RuntimeError(
            f"No version on fetched object {object_id}: {json.dumps(parsed)}"
        )
    return version


def _sparse_update_item(token: str, object_id: str, label: dict) -> None:
    """Issue a sparse ITEM update — ONLY name/description, preserving everything
    else (variation, price, categories, images)."""
    version = _get_object_version(token, object_id)
    name = label["product_name"]
    notes = label.get("condition_notes") or ""
    item_data = {"name": name}
    if notes:
        item_data["description"] = notes
        item_data["description_html"] = f"<p>{notes}</p>"

    body = {
        "idempotency_key": str(uuid.uuid4()),
        "object": {
            "type": "ITEM",
            "id": object_id,
            "version": version,
            "item_data": item_data,
        },
    }
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
    price_str = f"{price_cents / 100:.2f}"
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


# -----------------------------------------------------------------------------
# Orchestrator.
# -----------------------------------------------------------------------------

def list_item(item_dir: str, dry_run: bool = False, force: bool = False) -> dict:
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

    if dry_run:
        return {
            "dry_run": True,
            "sku": sku,
            "action": "update" if existing_object_id else "create",
            "price": price_str,
            "object_id": existing_object_id,
            "would_upload_image": (not existing_object_id) or force,
            "local_pickup_only": _local_pickup_only(label),
        }

    token = resolve_token()

    # --- Item: CREATE vs sparse UPDATE (never duplicate) ---------------------
    if existing_object_id:
        _sparse_update_item(token, existing_object_id, label)
        item_id = existing_object_id
        variation_id = square.get("variation_id")
        created = False
    else:
        item_id, variation_id = _create_item(token, sku, label)
        created = True

    # --- Image: only on create, or on an explicit --force update -------------
    image_uploaded = False
    if created or force:
        img = _find_image(item_path)
        if img is not None:
            _create_catalog_image(
                token, str(img), object_id=item_id,
                name=sku, caption=label.get("product_name"),
                is_primary=True,
            )
            image_uploaded = True

    # --- Payment link: idempotent on price -----------------------------------
    link = _ensure_payment_link(
        token, sku, label, variation_id, price_cents, square
    )
    payment_link_id = link.get("id")
    buy_link = link.get("url")
    order_id = link.get("order_id")

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
    label_path.write_text(
        json.dumps(label, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

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
    args = parser.parse_args(argv)

    summary = list_item(args.item_dir, dry_run=args.dry_run, force=args.force)

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
