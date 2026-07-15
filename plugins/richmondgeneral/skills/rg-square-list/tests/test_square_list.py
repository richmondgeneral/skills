"""Tests for square_list.py — the rg-square-list CLI (Phase C2).

TDD: written before the module. **No live network and no disk-to-Square.** Every
test that would otherwise touch Square monkeypatches the transport seam
(``square_client.square_request``) and the image-upload seam
(``square_list._create_catalog_image``) with capture/fakes, so the suite NEVER
hits Square and NEVER uploads a byte.

Run under the plugin uv env:

    cd plugins/richmondgeneral && uv run --with "qrcode[pil]" pytest \
        skills/rg-square-list/tests/test_square_list.py -q

Mirrors the import convention of test_square_client.py: put scripts/ on sys.path
and import the module by name.
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import square_client as sc  # noqa: E402
import square_list as sl  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures — a tmp item dir with a minimal label.json + a placeholder square.png.
# ---------------------------------------------------------------------------

def _write_label(item_dir, **overrides):
    """Write a minimal label.json into item_dir and return (path, dict)."""
    label = {
        "sku": "RG-0099",
        "product_name": "RG-0099 — Test Widget",
        "price": "65.00",
        "condition_notes": "Gently used; minor shelf wear.",
        "channels": {},
        "hero_qa": {"status": "pass"},
    }
    label.update(overrides)
    path = item_dir / "label.json"
    path.write_text(json.dumps(label, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    return path, label


@pytest.fixture
def item_dir(tmp_path):
    d = tmp_path / "RG-0099"
    d.mkdir()
    # Placeholder image asset so the upload path finds square.png.
    (d / "square.png").write_bytes(b"")
    return d


# ---------------------------------------------------------------------------
# Stub installers — record calls without touching the network.
# ---------------------------------------------------------------------------

def _patch_request(monkeypatch, handler):
    """Install a fake square_request that records every call.

    ``handler(method, path, body) -> (status, parsed)`` produces the response.
    Returns the shared ``calls`` list (one dict per call, in order).
    """
    calls = []

    def fake_request(method, path, token, version=sc.API_VERSION, body=None):
        calls.append({"method": method, "path": path, "body": body})
        return handler(method, path, body)

    monkeypatch.setattr(sc, "square_request", fake_request)
    # square_list imports the symbol into its own namespace.
    monkeypatch.setattr(sl, "square_request", fake_request)
    return calls


def _patch_image(monkeypatch):
    """Install a fake image uploader; returns the list of upload-call kwargs."""
    uploads = []

    def fake_upload(access_token, image_path, object_id=None, name=None,
                    caption=None, is_primary=False, api_version=sc.API_VERSION):
        uploads.append({
            "image_path": image_path,
            "object_id": object_id,
            "is_primary": is_primary,
        })
        return {"image": {"id": "IMG123"}}

    monkeypatch.setattr(sl, "_create_catalog_image", fake_upload)
    return uploads


def _patch_token(monkeypatch):
    monkeypatch.setattr(sl, "resolve_token", lambda: "T")


def _patch_qr(monkeypatch):
    """Install a fake gen_qr_png; returns the list of (url, out_path) calls.

    Monkeypatched so the suite never needs the real `qrcode` image lib and
    never writes a PNG.
    """
    qr_calls = []

    def fake_qr(url, out_path):
        qr_calls.append({"url": url, "out_path": out_path})

    monkeypatch.setattr(sl, "gen_qr_png", fake_qr)
    return qr_calls


# ---------------------------------------------------------------------------
# build_catalog_object — EXACT shape (mirrors process_new_item).
# ---------------------------------------------------------------------------

def test_build_catalog_object_shape():
    _, label = _write_label_dummy()
    obj = sl.build_catalog_object("RG-0099", label)

    assert obj["type"] == "ITEM"
    assert obj["id"] == "#RG-0099"
    assert obj["present_at_location_ids"] == [sc.LOCATION_ID]

    data = obj["item_data"]
    assert data["name"] == "RG-0099 — Test Widget"
    # reporting_category is the TYPE (Collectibles) — unchanged by the room add.
    assert data["reporting_category"] == {"id": sc.CAT_COLLECTIBLES}
    # categories == [Collectibles (type), New Arrivals (tier), Vintage Market
    # (room)] — the room category is required for room-level Shop All visibility.
    assert data["categories"] == [
        {"id": sc.CAT_COLLECTIBLES},
        {"id": sc.CAT_NEW_ARRIVALS},
        {"id": sc.CAT_VINTAGE_MARKET},
    ]
    # All THREE categories present, and the room id specifically is included.
    assert len(data["categories"]) == 3
    assert {"id": sc.CAT_VINTAGE_MARKET} in data["categories"]
    assert data["tax_ids"] == [sc.TAX_ID]
    assert data["ecom_visibility"] == "VISIBLE"

    variations = data["variations"]
    assert len(variations) == 1
    var = variations[0]
    assert var["type"] == "ITEM_VARIATION"
    vd = var["item_variation_data"]
    assert vd["pricing_type"] == "FIXED_PRICING"
    assert vd["price_money"]["amount"] == sc.dollars_to_cents(label["price"])
    assert vd["price_money"]["amount"] == 6500
    assert vd["price_money"]["currency"] == "USD"
    assert vd["sku"] == "RG-0099"
    assert vd["track_inventory"] is True
    assert vd["sellable"] is True
    assert vd["stockable"] is True
    assert var["present_at_location_ids"] == [sc.LOCATION_ID]


def _write_label_dummy():
    """A label dict (no disk) for pure shape tests."""
    return None, {
        "sku": "RG-0099",
        "product_name": "RG-0099 — Test Widget",
        "price": "65.00",
        "condition_notes": "Gently used; minor shelf wear.",
        "channels": {},
        "hero_qa": {"status": "pass"},
    }


# ---------------------------------------------------------------------------
# CREATE path — batch-upsert + ONE primary image + ONE payment-link create.
# ---------------------------------------------------------------------------

def test_create_path_calls(monkeypatch, item_dir):
    _write_label(item_dir)  # no channels.square.object_id → CREATE
    _patch_token(monkeypatch)

    def handler(method, path, body):
        if path == "/v2/catalog/batch-upsert":
            return 200, {
                "id_mappings": [
                    {"client_object_id": "#RG-0099", "object_id": "ITEM_REAL"},
                    {"client_object_id": "#RG-0099-var",
                     "object_id": "VAR_REAL"},
                ],
            }
        if path == "/v2/inventory/batch-change":
            return 200, {"counts": [{"quantity": "1"}]}
        if path == "/v2/online-checkout/payment-links":
            return 200, {"payment_link": {
                "id": "PL_REAL",
                "url": "https://square.link/u/abc",
                "order_id": "ORD_REAL",
            }}
        raise AssertionError(f"unexpected request: {method} {path}")

    calls = _patch_request(monkeypatch, handler)
    uploads = _patch_image(monkeypatch)
    _patch_qr(monkeypatch)

    summary = sl.list_item(str(item_dir), dry_run=False)

    # Exactly one create (batch-upsert) and one payment-link create.
    upserts = [c for c in calls if c["path"] == "/v2/catalog/batch-upsert"]
    paylinks = [c for c in calls
                if c["path"] == "/v2/online-checkout/payment-links"
                and c["method"] == "POST"]
    assert len(upserts) == 1
    assert upserts[0]["method"] == "POST"
    assert len(paylinks) == 1

    # Exactly one image upload, as PRIMARY, attached to the real item id.
    assert len(uploads) == 1
    assert uploads[0]["is_primary"] is True
    assert uploads[0]["object_id"] == "ITEM_REAL"

    # Ordering: create item BEFORE image BEFORE payment link (data deps).
    assert calls[0]["path"] == "/v2/catalog/batch-upsert"
    assert calls[-1]["path"] == "/v2/online-checkout/payment-links"

    # Returned ids.
    assert summary["object_id"] == "ITEM_REAL"
    assert summary["variation_id"] == "VAR_REAL"
    assert summary["payment_link_id"] == "PL_REAL"
    assert summary["buy_link"] == "https://square.link/u/abc"
    assert summary["created"] is True


# ---------------------------------------------------------------------------
# UPDATE path — sparse ITEM update, NO duplicate create, NO re-upload.
# ---------------------------------------------------------------------------

def test_idempotent_update_no_duplicate_create(monkeypatch, item_dir):
    _write_label(item_dir, channels={"square": {
        "object_id": "ITEM_EXISTING",
        "variation_id": "VAR_EXISTING",
        "payment_link_id": "PL_EXISTING",
        "price": "65.00",  # same as current → keep link
    }})
    _patch_token(monkeypatch)

    def handler(method, path, body):
        if method == "GET" and path == "/v2/catalog/object/ITEM_EXISTING":
            return 200, {"object": {
                "type": "ITEM", "id": "ITEM_EXISTING", "version": 42,
            }}
        if method == "POST" and path == "/v2/catalog/object":
            return 200, {"catalog_object": {
                "id": "ITEM_EXISTING", "version": 43,
            }}
        raise AssertionError(f"unexpected request: {method} {path}")

    calls = _patch_request(monkeypatch, handler)
    uploads = _patch_image(monkeypatch)
    _patch_qr(monkeypatch)

    summary = sl.list_item(str(item_dir), dry_run=False, force=False)

    # NO create.
    assert not any(c["path"] == "/v2/catalog/batch-upsert" for c in calls)
    # NO inventory call on a re-run/UPDATE (create-only).
    assert not any(c["path"] == "/v2/inventory/batch-change" for c in calls)
    # A sparse single-object upsert (POST /v2/catalog/object) was issued.
    upserts = [c for c in calls
               if c["method"] == "POST" and c["path"] == "/v2/catalog/object"]
    assert len(upserts) == 1
    sent = upserts[0]["body"]["object"]
    assert sent["type"] == "ITEM"
    assert sent["id"] == "ITEM_EXISTING"
    assert sent["version"] == 42  # fetched current version echoed back
    # Sparse: item_data carries ONLY name/description fields.
    assert set(sent["item_data"].keys()) <= {
        "name", "description", "description_html"}
    assert "variations" not in sent["item_data"]
    assert "categories" not in sent["item_data"]

    # NO image re-upload on a plain (force=False) update.
    assert uploads == []
    # No payment-link create OR delete (price unchanged).
    assert not any(c["path"] == "/v2/online-checkout/payment-links"
                   for c in calls)
    assert summary["created"] is False


# ---------------------------------------------------------------------------
# Payment-link recreated when the price changed.
# ---------------------------------------------------------------------------

def test_paylink_recreated_on_price_change(monkeypatch, item_dir):
    _write_label(item_dir, price="48.00", channels={"square": {
        "object_id": "ITEM_EXISTING",
        "variation_id": "VAR_EXISTING",
        "payment_link_id": "PL_OLD",
        "price": "65.00",  # recorded link price DIFFERS from current 48.00
    }})
    _patch_token(monkeypatch)

    def handler(method, path, body):
        if method == "GET" and path == "/v2/catalog/object/ITEM_EXISTING":
            return 200, {"object": {
                "type": "ITEM", "id": "ITEM_EXISTING", "version": 7}}
        if method == "POST" and path == "/v2/catalog/object":
            return 200, {"catalog_object": {
                "id": "ITEM_EXISTING", "version": 8}}
        if (method == "DELETE"
                and path == "/v2/online-checkout/payment-links/PL_OLD"):
            return 200, {}
        if (method == "POST"
                and path == "/v2/online-checkout/payment-links"):
            return 200, {"payment_link": {
                "id": "PL_NEW",
                "url": "https://square.link/u/new",
                "order_id": "ORD_NEW",
            }}
        raise AssertionError(f"unexpected request: {method} {path}")

    calls = _patch_request(monkeypatch, handler)
    _patch_image(monkeypatch)
    _patch_qr(monkeypatch)

    summary = sl.list_item(str(item_dir), dry_run=False, force=False)

    deletes = [c for c in calls if c["method"] == "DELETE"
               and c["path"] == "/v2/online-checkout/payment-links/PL_OLD"]
    creates = [c for c in calls if c["method"] == "POST"
               and c["path"] == "/v2/online-checkout/payment-links"]
    assert len(deletes) == 1
    assert len(creates) == 1
    # Delete the OLD link BEFORE creating the new one.
    del_idx = calls.index(deletes[0])
    new_idx = calls.index(creates[0])
    assert del_idx < new_idx

    assert summary["payment_link_id"] == "PL_NEW"
    assert summary["buy_link"] == "https://square.link/u/new"


# ---------------------------------------------------------------------------
# Orphan-link hardening — a recorded payment_link_id WITHOUT a sibling price
# (foreign / hand-edited label) must NOT blind-create a second live link. The
# old link's price is unknown → delete it THEN create, never leave two
# chargeable links side by side.
# ---------------------------------------------------------------------------

def test_paylink_orphan_no_recorded_price_deletes_then_creates(
        monkeypatch, item_dir):
    # object_id + payment_link_id present, but NO `price` in channels.square.
    _write_label(item_dir, channels={"square": {
        "object_id": "ITEM_EXISTING",
        "variation_id": "VAR_EXISTING",
        "payment_link_id": "PL_ORPHAN",
        # intentionally NO "price" key
    }})
    _patch_token(monkeypatch)

    def handler(method, path, body):
        if method == "GET" and path == "/v2/catalog/object/ITEM_EXISTING":
            return 200, {"object": {
                "type": "ITEM", "id": "ITEM_EXISTING", "version": 11}}
        if method == "POST" and path == "/v2/catalog/object":
            return 200, {"catalog_object": {
                "id": "ITEM_EXISTING", "version": 12}}
        if (method == "DELETE"
                and path == "/v2/online-checkout/payment-links/PL_ORPHAN"):
            return 200, {}
        if (method == "POST"
                and path == "/v2/online-checkout/payment-links"):
            return 200, {"payment_link": {
                "id": "PL_FRESH",
                "url": "https://square.link/u/fresh",
                "order_id": "ORD_FRESH",
            }}
        raise AssertionError(f"unexpected request: {method} {path}")

    calls = _patch_request(monkeypatch, handler)
    _patch_image(monkeypatch)
    _patch_qr(monkeypatch)

    summary = sl.list_item(str(item_dir), dry_run=False, force=False)

    deletes = [c for c in calls if c["method"] == "DELETE"
               and c["path"] == "/v2/online-checkout/payment-links/PL_ORPHAN"]
    creates = [c for c in calls if c["method"] == "POST"
               and c["path"] == "/v2/online-checkout/payment-links"]
    # Exactly one delete (of the OLD id) THEN exactly one create.
    assert len(deletes) == 1
    assert len(creates) == 1
    del_idx = calls.index(deletes[0])
    new_idx = calls.index(creates[0])
    assert del_idx < new_idx  # delete the old link BEFORE creating the new one

    assert summary["payment_link_id"] == "PL_FRESH"
    assert summary["buy_link"] == "https://square.link/u/fresh"


# ---------------------------------------------------------------------------
# Dry run — ZERO calls, ZERO writes.
# ---------------------------------------------------------------------------

def test_dry_run_makes_zero_calls(monkeypatch, item_dir):
    label_path, _ = _write_label(item_dir)
    before = label_path.read_bytes()

    # Any real call through these seams must blow up — proving none happen.
    def boom_request(*a, **k):
        raise AssertionError("square_request called during dry-run")

    def boom_image(*a, **k):
        raise AssertionError("image upload called during dry-run")

    def boom_token():
        raise AssertionError("resolve_token called during dry-run")

    monkeypatch.setattr(sc, "square_request", boom_request)
    monkeypatch.setattr(sl, "square_request", boom_request)
    monkeypatch.setattr(sl, "_create_catalog_image", boom_image)
    monkeypatch.setattr(sl, "resolve_token", boom_token)

    summary = sl.list_item(str(item_dir), dry_run=True)

    # Nothing written to label.json.
    assert label_path.read_bytes() == before
    # A plan summary is still returned.
    assert summary["dry_run"] is True


# ---------------------------------------------------------------------------
# Write-back — channels.square is populated + status listed after a create.
# ---------------------------------------------------------------------------

def test_writeback(monkeypatch, item_dir):
    label_path, _ = _write_label(item_dir)
    _patch_token(monkeypatch)

    def handler(method, path, body):
        if path == "/v2/catalog/batch-upsert":
            return 200, {"id_mappings": [
                {"client_object_id": "#RG-0099", "object_id": "ITEM_REAL"},
                {"client_object_id": "#RG-0099-var", "object_id": "VAR_REAL"},
            ]}
        if path == "/v2/inventory/batch-change":
            return 200, {"counts": [{"quantity": "1"}]}
        if path == "/v2/online-checkout/payment-links":
            return 200, {"payment_link": {
                "id": "PL_REAL",
                "url": "https://square.link/u/abc",
                "order_id": "ORD_REAL",
            }}
        raise AssertionError(f"unexpected: {method} {path}")

    _patch_request(monkeypatch, handler)
    _patch_image(monkeypatch)
    _patch_qr(monkeypatch)

    sl.list_item(str(item_dir), dry_run=False)

    written = json.loads(label_path.read_text(encoding="utf-8"))
    sq = written["channels"]["square"]
    assert sq["object_id"] == "ITEM_REAL"
    assert sq["variation_id"] == "VAR_REAL"
    assert sq["buy_link"] == "https://square.link/u/abc"
    assert sq["payment_link_id"] == "PL_REAL"
    assert sq["order_id"] == "ORD_REAL"
    assert sq["price"] == "65.00"
    assert sq["status"] == "listed"
    # I2: top-level lifecycle state promoted to "Listed" on success.
    assert written["state"] == "Listed"
    # File ends with a trailing newline (formatting contract).
    assert label_path.read_text(encoding="utf-8").endswith("\n")


# ---------------------------------------------------------------------------
# C1 — CREATE sets inventory to 1 (item must be purchasable, not "Sold out").
# A plain re-run / UPDATE issues ZERO inventory calls.
# ---------------------------------------------------------------------------

def _create_handler(method, path, body):
    """Shared CREATE-path response handler (upsert + inventory + paylink)."""
    if path == "/v2/catalog/batch-upsert":
        return 200, {"id_mappings": [
            {"client_object_id": "#RG-0099", "object_id": "ITEM_REAL"},
            {"client_object_id": "#RG-0099-var", "object_id": "VAR_REAL"},
        ]}
    if path == "/v2/inventory/batch-change":
        return 200, {"counts": [{"quantity": "1"}]}
    if path == "/v2/online-checkout/payment-links":
        return 200, {"payment_link": {
            "id": "PL_REAL",
            "url": "https://square.link/u/abc",
            "order_id": "ORD_REAL",
        }}
    raise AssertionError(f"unexpected request: {method} {path}")


def test_create_sets_inventory(monkeypatch, item_dir):
    _write_label(item_dir)  # no object_id → CREATE
    _patch_token(monkeypatch)
    calls = _patch_request(monkeypatch, _create_handler)
    _patch_image(monkeypatch)
    _patch_qr(monkeypatch)

    sl.list_item(str(item_dir), dry_run=False)

    inv = [c for c in calls if c["path"] == "/v2/inventory/batch-change"]
    # Exactly ONE inventory batch-change on create.
    assert len(inv) == 1
    assert inv[0]["method"] == "POST"
    change = inv[0]["body"]["changes"][0]
    assert change["type"] == "PHYSICAL_COUNT"
    pc = change["physical_count"]
    # Set quantity 1 IN_STOCK for the NEW variation.
    assert pc["catalog_object_id"] == "VAR_REAL"
    assert pc["quantity"] == "1"
    assert pc["state"] == "IN_STOCK"
    assert pc["location_id"] == sc.LOCATION_ID


def test_update_makes_zero_inventory_calls(monkeypatch, item_dir):
    _write_label(item_dir, channels={"square": {
        "object_id": "ITEM_EXISTING",
        "variation_id": "VAR_EXISTING",
        "payment_link_id": "PL_EXISTING",
        "price": "65.00",  # unchanged → keep link
    }})
    _patch_token(monkeypatch)

    def handler(method, path, body):
        if method == "GET" and path == "/v2/catalog/object/ITEM_EXISTING":
            return 200, {"object": {
                "type": "ITEM", "id": "ITEM_EXISTING", "version": 5}}
        if method == "POST" and path == "/v2/catalog/object":
            return 200, {"catalog_object": {
                "id": "ITEM_EXISTING", "version": 6}}
        raise AssertionError(f"unexpected request: {method} {path}")

    calls = _patch_request(monkeypatch, handler)
    _patch_image(monkeypatch)
    _patch_qr(monkeypatch)

    sl.list_item(str(item_dir), dry_run=False)

    # ZERO inventory calls on a plain re-run (create-only behavior).
    assert not any(c["path"] == "/v2/inventory/batch-change" for c in calls)


# ---------------------------------------------------------------------------
# I1 — ids are persisted to label.json IMMEDIATELY after a successful create,
# BEFORE the image/inventory/paylink steps, so a later failure can't strand the
# run into double-creating on re-run.
# ---------------------------------------------------------------------------

def test_create_persists_ids_before_paylink(monkeypatch, item_dir):
    label_path, _ = _write_label(item_dir)  # CREATE path
    _patch_token(monkeypatch)
    _patch_image(monkeypatch)
    _patch_qr(monkeypatch)

    def handler(method, path, body):
        if path == "/v2/catalog/batch-upsert":
            return 200, {"id_mappings": [
                {"client_object_id": "#RG-0099", "object_id": "ITEM_REAL"},
                {"client_object_id": "#RG-0099-var", "object_id": "VAR_REAL"},
            ]}
        if path == "/v2/inventory/batch-change":
            return 200, {"counts": [{"quantity": "1"}]}
        if path == "/v2/online-checkout/payment-links":
            # Simulate the paylink CREATE blowing up AFTER the item was created.
            raise RuntimeError("simulated paylink failure")
        raise AssertionError(f"unexpected request: {method} {path}")

    _patch_request(monkeypatch, handler)

    # The run errors out at the paylink step...
    with pytest.raises(RuntimeError, match="simulated paylink failure"):
        sl.list_item(str(item_dir), dry_run=False)

    # ...but label.json on disk ALREADY has the catalog ids, so a re-run resumes
    # in the UPDATE branch and never double-creates.
    written = json.loads(label_path.read_text(encoding="utf-8"))
    sq = written["channels"]["square"]
    assert sq["object_id"] == "ITEM_REAL"
    assert sq["variation_id"] == "VAR_REAL"


# ---------------------------------------------------------------------------
# I3 — UPDATE path with a MISSING variation_id (foreign/hand-edited label):
# recover it from the fetched catalog object BEFORE touching the payment link;
# never delete-then-create a paylink with a None line item.
# ---------------------------------------------------------------------------

def test_update_recovers_missing_variation_id_before_paylink(
        monkeypatch, item_dir):
    # object_id present, payment_link_id present + price CHANGED → recreate, but
    # variation_id is ABSENT from channels.square.
    _write_label(item_dir, price="48.00", channels={"square": {
        "object_id": "ITEM_EXISTING",
        "payment_link_id": "PL_OLD",
        "price": "65.00",  # differs from 48.00 → recreate the link
        # intentionally NO "variation_id"
    }})
    _patch_token(monkeypatch)

    def handler(method, path, body):
        if method == "GET" and path == "/v2/catalog/object/ITEM_EXISTING":
            # The fetched object carries the variation id we must recover.
            return 200, {"object": {
                "type": "ITEM", "id": "ITEM_EXISTING", "version": 9,
                "item_data": {"variations": [{"id": "VAR_FETCHED"}]},
            }}
        if method == "POST" and path == "/v2/catalog/object":
            return 200, {"catalog_object": {
                "id": "ITEM_EXISTING", "version": 10}}
        if (method == "DELETE"
                and path == "/v2/online-checkout/payment-links/PL_OLD"):
            return 200, {}
        if (method == "POST"
                and path == "/v2/online-checkout/payment-links"):
            return 200, {"payment_link": {
                "id": "PL_NEW",
                "url": "https://square.link/u/new",
                "order_id": "ORD_NEW",
            }}
        raise AssertionError(f"unexpected request: {method} {path}")

    calls = _patch_request(monkeypatch, handler)
    _patch_image(monkeypatch)
    _patch_qr(monkeypatch)

    summary = sl.list_item(str(item_dir), dry_run=False, force=False)

    # The recreated paylink uses the FETCHED variation id (never None).
    creates = [c for c in calls if c["method"] == "POST"
               and c["path"] == "/v2/online-checkout/payment-links"]
    assert len(creates) == 1
    li = creates[0]["body"]["order"]["line_items"][0]
    assert li["catalog_object_id"] == "VAR_FETCHED"
    # The summary + write-back carry the recovered id.
    assert summary["variation_id"] == "VAR_FETCHED"


def test_update_missing_variation_unresolvable_raises_before_delete(
        monkeypatch, item_dir):
    # variation_id absent from the label AND absent from the fetched object →
    # must raise BEFORE deleting any payment link.
    _write_label(item_dir, price="48.00", channels={"square": {
        "object_id": "ITEM_EXISTING",
        "payment_link_id": "PL_OLD",
        "price": "65.00",
    }})
    _patch_token(monkeypatch)

    def handler(method, path, body):
        if method == "GET" and path == "/v2/catalog/object/ITEM_EXISTING":
            # No variations on the fetched object → unresolvable.
            return 200, {"object": {
                "type": "ITEM", "id": "ITEM_EXISTING", "version": 9,
                "item_data": {},
            }}
        raise AssertionError(f"unexpected request: {method} {path}")

    calls = _patch_request(monkeypatch, handler)
    _patch_image(monkeypatch)
    _patch_qr(monkeypatch)

    with pytest.raises(RuntimeError, match="variation_id"):
        sl.list_item(str(item_dir), dry_run=False, force=False)

    # The old link was NEVER deleted (we raised before touching it).
    assert not any(c["method"] == "DELETE" for c in calls)


# ---------------------------------------------------------------------------
# M2 — the buy QR is rendered and recorded (the "two QR codes" contract).
# ---------------------------------------------------------------------------

def test_create_generates_qr_buy(monkeypatch, item_dir):
    label_path, _ = _write_label(item_dir)  # CREATE path
    _patch_token(monkeypatch)
    _patch_request(monkeypatch, _create_handler)
    _patch_image(monkeypatch)
    qr_calls = _patch_qr(monkeypatch)

    sl.list_item(str(item_dir), dry_run=False)

    # gen_qr_png invoked for BOTH QRs: buy link first, then the info QR
    # (price tag -> GitHub item page) — the full two-QR contract.
    assert len(qr_calls) == 2
    assert qr_calls[0]["url"] == "https://square.link/u/abc"
    assert qr_calls[0]["out_path"].endswith("qr-buy.png")
    assert qr_calls[1]["url"] == "https://richmondgeneral.github.io/items/RG-0099/"
    assert qr_calls[1]["out_path"].endswith("qr-info.png")

    # Recorded in label.json -> qr_codes.buy.
    written = json.loads(label_path.read_text(encoding="utf-8"))
    buy = written["qr_codes"]["buy"]
    assert buy["file"] == "qr-buy.png"
    assert buy["url"] == "https://square.link/u/abc"
    assert "scan to buy" in buy["use"].lower()


def test_qr_missing_dep_degrades_not_crash(monkeypatch, item_dir):
    # If qrcode is absent, gen_qr_png raises ImportError — the listing must
    # still succeed (warn, don't crash) and just not record qr_codes.buy.
    label_path, _ = _write_label(item_dir)
    _patch_token(monkeypatch)
    _patch_request(monkeypatch, _create_handler)
    _patch_image(monkeypatch)

    def boom_qr(url, out_path):
        raise ImportError("No module named 'qrcode'")

    monkeypatch.setattr(sl, "gen_qr_png", boom_qr)

    summary = sl.list_item(str(item_dir), dry_run=False)

    # The listing still completed (ids written, status listed).
    assert summary["created"] is True
    written = json.loads(label_path.read_text(encoding="utf-8"))
    assert written["channels"]["square"]["status"] == "listed"
    # No qr_codes.buy recorded (generation failed gracefully).
    assert "buy" not in (written.get("qr_codes") or {})


# ---------------------------------------------------------------------------
# I2 — never DOWNGRADE a Sold/Archived item's top-level state to "Listed".
# ---------------------------------------------------------------------------

def test_state_not_downgraded_from_sold(monkeypatch, item_dir):
    _write_label(item_dir, state="Sold", channels={"square": {
        "object_id": "ITEM_EXISTING",
        "variation_id": "VAR_EXISTING",
        "payment_link_id": "PL_EXISTING",
        "price": "65.00",
    }})
    _patch_token(monkeypatch)

    def handler(method, path, body):
        if method == "GET" and path == "/v2/catalog/object/ITEM_EXISTING":
            return 200, {"object": {
                "type": "ITEM", "id": "ITEM_EXISTING", "version": 5}}
        if method == "POST" and path == "/v2/catalog/object":
            return 200, {"catalog_object": {
                "id": "ITEM_EXISTING", "version": 6}}
        raise AssertionError(f"unexpected request: {method} {path}")

    _patch_request(monkeypatch, handler)
    _patch_image(monkeypatch)
    _patch_qr(monkeypatch)

    label_path = item_dir / "label.json"
    sl.list_item(str(item_dir), dry_run=False)

    written = json.loads(label_path.read_text(encoding="utf-8"))
    # Top-level state stays "Sold" (not clobbered to "Listed").
    assert written["state"] == "Sold"
    # But the channel status still reflects the sparse update ran.
    assert written["channels"]["square"]["status"] == "listed"


# ---------------------------------------------------------------------------
# Hero QA gate + TYPE category resolution (audit 2026-07-15).
# ---------------------------------------------------------------------------

def test_create_refused_without_hero_qa_pass(item_dir):
    _write_label(item_dir, hero_qa={"status": "fail"})
    with pytest.raises(SystemExit, match="REFUSED"):
        sl.list_item(str(item_dir))


def test_create_allowed_via_photo_overrides_approval(item_dir):
    _write_label(item_dir, hero_qa={"status": "fail"},
                 photo_overrides={"status": "approved", "reason": "radial symmetry"})
    assert sl.hero_qa_ok(json.loads((item_dir / "label.json").read_text()))


def test_skip_hero_qa_flag_overrides_gate(item_dir):
    _write_label(item_dir, hero_qa={"status": "fail"})
    summary = sl.list_item(str(item_dir), dry_run=True)
    assert summary["hero_qa_ok"] is False  # dry-run reports, never blocks


def test_type_category_resolved_from_reporting_note(item_dir):
    _, label = _write_label(item_dir, reporting_category_note="Books & Paper")
    obj = sl.build_catalog_object("RG-0099", label)
    cats = [c["id"] for c in obj["item_data"]["categories"]]
    assert cats[0] == "CLZCJ62H4TTHDQ3ZBYMZQASQ"          # Books & Paper TYPE
    assert obj["item_data"]["reporting_category"]["id"] == "CLZCJ62H4TTHDQ3ZBYMZQASQ"
    assert cats[2] == "QLM2GZ643LOCYHB653YIDJWT"          # General Store room


def test_type_category_defaults_to_collectibles_without_note(item_dir):
    _, label = _write_label(item_dir)
    obj = sl.build_catalog_object("RG-0099", label)
    cats = [c["id"] for c in obj["item_data"]["categories"]]
    assert cats[0] == sl.CAT_COLLECTIBLES
    assert cats[2] == sl.CAT_VINTAGE_MARKET


def test_create_writes_info_qr_and_categories(item_dir, monkeypatch):
    _write_label(item_dir, reporting_category_note="Books & Paper")
    _patch_token(monkeypatch)

    def handler(method, path, body):
        if path == "/v2/catalog/batch-upsert":
            return 200, {"id_mappings": [
                {"client_object_id": "#RG-0099", "object_id": "ITEM_REAL"},
                {"client_object_id": "#RG-0099-var", "object_id": "VAR_REAL"}]}
        if path == "/v2/inventory/batch-change":
            return 200, {"counts": [{"quantity": "1"}]}
        if path == "/v2/online-checkout/payment-links":
            return 200, {"payment_link": {"id": "PL", "url": "https://square.link/u/abc",
                                          "order_id": "ORD"}}
        raise AssertionError(f"unexpected request: {method} {path}")

    _patch_request(monkeypatch, handler)
    _patch_image(monkeypatch)
    _patch_qr(monkeypatch)
    sl.list_item(str(item_dir))
    label = json.loads((item_dir / "label.json").read_text())
    qr = label.get("qr_codes", {})
    assert qr.get("info", {}).get("file") == "qr-info.png"
    assert "richmondgeneral.github.io/items/RG-0099/" in qr["info"]["url"]
    assert qr.get("buy", {}).get("file") == "qr-buy.png"
    cats = label["channels"]["square"].get("categories", {})
    assert cats.get("type") == "CLZCJ62H4TTHDQ3ZBYMZQASQ"
    assert cats.get("reporting_category") == "CLZCJ62H4TTHDQ3ZBYMZQASQ"
    assert cats.get("tier") == sc.CAT_NEW_ARRIVALS


# ---------------------------------------------------------------------------
# Raw-image gate (RG-0062/0064/0068 in-situ shots shipped raw, 2026-07-15).
# ---------------------------------------------------------------------------

def test_create_refuses_raw_image(item_dir, monkeypatch):
    (item_dir / "square.png").unlink()          # fixture ships square.png; remove it
    (item_dir / "hero.jpg").write_bytes(b"")    # only a raw hero remains
    _write_label(item_dir)
    _patch_token(monkeypatch)
    _patch_request(monkeypatch, _create_handler)
    _patch_image(monkeypatch)
    _patch_qr(monkeypatch)
    with pytest.raises(SystemExit, match="RAW"):
        sl.list_item(str(item_dir))


def test_create_allows_raw_image_with_flag(item_dir, monkeypatch):
    (item_dir / "square.png").unlink()
    (item_dir / "hero.jpg").write_bytes(b"")
    _write_label(item_dir)
    _patch_token(monkeypatch)
    _patch_request(monkeypatch, _create_handler)
    uploads = _patch_image(monkeypatch)
    _patch_qr(monkeypatch)
    sl.list_item(str(item_dir), allow_raw_image=True)
    assert len(uploads) == 1


def test_dry_run_reports_image_processed_state(item_dir):
    _write_label(item_dir)
    s = sl.list_item(str(item_dir), dry_run=True)
    assert s["image"] == "square.png" and s["image_processed"] is True
