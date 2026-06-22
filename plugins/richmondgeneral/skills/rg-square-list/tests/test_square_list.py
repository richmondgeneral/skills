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
    # reporting_category is the TYPE (Collectibles).
    assert data["reporting_category"] == {"id": sc.CAT_COLLECTIBLES}
    # categories == [Collectibles (type), New Arrivals (tier)].
    assert data["categories"] == [
        {"id": sc.CAT_COLLECTIBLES},
        {"id": sc.CAT_NEW_ARRIVALS},
    ]
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
        if path == "/v2/online-checkout/payment-links":
            return 200, {"payment_link": {
                "id": "PL_REAL",
                "url": "https://square.link/u/abc",
                "order_id": "ORD_REAL",
            }}
        raise AssertionError(f"unexpected request: {method} {path}")

    calls = _patch_request(monkeypatch, handler)
    uploads = _patch_image(monkeypatch)

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

    summary = sl.list_item(str(item_dir), dry_run=False, force=False)

    # NO create.
    assert not any(c["path"] == "/v2/catalog/batch-upsert" for c in calls)
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
        if path == "/v2/online-checkout/payment-links":
            return 200, {"payment_link": {
                "id": "PL_REAL",
                "url": "https://square.link/u/abc",
                "order_id": "ORD_REAL",
            }}
        raise AssertionError(f"unexpected: {method} {path}")

    _patch_request(monkeypatch, handler)
    _patch_image(monkeypatch)

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
    # File ends with a trailing newline (formatting contract).
    assert label_path.read_text(encoding="utf-8").endswith("\n")
