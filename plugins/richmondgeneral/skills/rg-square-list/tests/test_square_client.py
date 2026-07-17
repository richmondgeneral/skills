"""Tests for square_client.py — the shared Square API client for the
rg-square-list and rg-reprice tools (Phase C1).

TDD: written before the module. No live network — every test that exercises a
request monkeypatches square_client._http (the sole network seam), so the suite
NEVER hits Square. Run under the plugin uv env with qrcode available:

    cd plugins/richmondgeneral && uv run --with "qrcode[pil]" pytest \
        skills/rg-square-list/tests/test_square_client.py -q

Mirrors the import convention of skills/rg-item-mark-sold/tests: put scripts/ on
sys.path and import the module by name (stdlib-only script → stdlib-only test).
"""

import importlib.util
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import square_client as sc  # noqa: E402


# ---------------------------------------------------------------------------
# Constants — the canonical source for the new tools.
# ---------------------------------------------------------------------------

def test_constants():
    assert sc.LOCATION_ID == "B87BAEZ0NWV34"
    assert sc.API_VERSION == "2026-04-21"
    assert sc.MERCHANT_ID == "7MM9AFJAD0XHW"
    assert sc.TAX_ID == "LPKEJF7H27NOPK7EE6A5CA7V"
    assert sc.CAT_COLLECTIBLES == "YQWBSOJDENMXDGUUQ3TGI3HF"
    assert sc.CAT_NEW_ARRIVALS == "TGWDFETSQPR6BF67YJCTOLW6"
    assert sc.CAT_VINTAGE_MARKET == "TX6SBQLJDMZOCVXBUD3KT3CL"
    assert sc.BASE == "https://connect.squareup.com"


# ---------------------------------------------------------------------------
# dollars_to_cents — shared money parsing both tools need.
# ---------------------------------------------------------------------------

def test_dollars_to_cents():
    assert sc.dollars_to_cents("65.00") == 6500
    assert sc.dollars_to_cents("$65.00") == 6500
    assert sc.dollars_to_cents("$1,234") == 123400
    assert sc.dollars_to_cents(65) == 6500
    assert sc.dollars_to_cents(65.5) == 6550
    # A couple of extra rounding/whitespace cases the tools will rely on.
    assert sc.dollars_to_cents("  $1,234.56 ") == 123456
    assert sc.dollars_to_cents(65.0) == 6500


# ---------------------------------------------------------------------------
# build_payment_link_body — EXACT shape (charges real money downstream).
# ---------------------------------------------------------------------------

def test_payment_link_body_shape():
    body = sc.build_payment_link_body(
        name="RG-0099 - Test Widget",
        variation_id="VARIATION123",
        price_cents=6500,
        sku="RG-0099",
        redirect_url="https://richmondgeneral.example/RG-0099",
        ask_shipping=True,
        idempotency_key="idem-key-abc",
    )

    assert body["idempotency_key"] == "idem-key-abc"
    assert body["description"] == "RG-0099"

    order = body["order"]
    assert order["location_id"] == sc.LOCATION_ID
    assert order["reference_id"] == "RG-0099"

    line_items = order["line_items"]
    assert len(line_items) == 1
    li = line_items[0]
    assert li["catalog_object_id"] == "VARIATION123"
    assert li["quantity"] == "1"
    assert li["item_type"] == "ITEM"
    # Price comes from the catalog variation — no inline price_money on the line.
    assert "price_money" not in li

    co = body["checkout_options"]
    assert co["redirect_url"] == "https://richmondgeneral.example/RG-0099"
    assert co["ask_for_shipping_address"] is True
    assert isinstance(co["ask_for_shipping_address"], bool)


def test_payment_link_body_ask_shipping_coerced_to_bool():
    body = sc.build_payment_link_body(
        name="n",
        variation_id="V",
        price_cents=100,
        sku="RG-0001",
        redirect_url="https://x/y",
        ask_shipping=0,  # falsy non-bool → must serialize as a real bool
        idempotency_key="k",
    )
    val = body["checkout_options"]["ask_for_shipping_address"]
    assert val is False
    assert isinstance(val, bool)


# ---------------------------------------------------------------------------
# square_request — header construction + dispatch through _http.
# ---------------------------------------------------------------------------

def test_square_request_headers_and_dispatch(monkeypatch):
    captured = {}

    def fake_http(method, url, headers, data):
        captured["method"] = method
        captured["url"] = url
        captured["headers"] = headers
        captured["data"] = data
        return 200, b'{"ok": true}'

    monkeypatch.setattr(sc, "_http", fake_http)

    status, parsed = sc.square_request(
        "POST",
        "/v2/online-checkout/payment-links",
        "T",
        body={"hello": "world"},
    )

    assert status == 200
    assert parsed == {"ok": True}
    assert captured["method"] == "POST"
    assert captured["url"] == sc.BASE + "/v2/online-checkout/payment-links"
    assert captured["headers"]["Authorization"] == "Bearer T"
    assert captured["headers"]["Square-Version"] == sc.API_VERSION
    assert captured["headers"]["Content-Type"] == "application/json"
    # Body round-trips as JSON.
    assert json.loads(captured["data"].decode("utf-8")) == {"hello": "world"}


def test_square_request_get_sends_no_content_type(monkeypatch):
    captured = {}

    def fake_http(method, url, headers, data):
        captured["headers"] = headers
        captured["data"] = data
        return 200, b"{}"

    monkeypatch.setattr(sc, "_http", fake_http)

    status, parsed = sc.square_request("GET", "/v2/locations", "T")

    assert status == 200
    assert parsed == {}
    assert captured["data"] is None
    assert "Content-Type" not in captured["headers"]
    assert captured["headers"]["Authorization"] == "Bearer T"
    assert captured["headers"]["Square-Version"] == sc.API_VERSION


def test_square_request_parses_error_body(monkeypatch):
    err = {"errors": [{"code": "BAD_REQUEST", "detail": "nope"}]}

    def fake_http(method, url, headers, data):
        return 400, json.dumps(err).encode("utf-8")

    monkeypatch.setattr(sc, "_http", fake_http)

    status, parsed = sc.square_request("POST", "/v2/x", "T", body={"a": 1})
    assert status == 400
    assert parsed == err  # returned, NOT raised


def test_square_request_empty_body_parses_to_empty_dict(monkeypatch):
    monkeypatch.setattr(sc, "_http", lambda *a, **k: (200, b""))
    status, parsed = sc.square_request("DELETE", "/v2/x/1", "T")
    assert status == 200
    assert parsed == {}


# ---------------------------------------------------------------------------
# create_payment_link / delete_payment_link — through the monkeypatched seam.
# ---------------------------------------------------------------------------

def test_create_payment_link_returns_object(monkeypatch):
    link_obj = {
        "id": "PL123",
        "url": "https://square.link/u/abc",
        "order_id": "ORD123",
    }

    def fake_http(method, url, headers, data):
        assert method == "POST"
        assert url == sc.BASE + "/v2/online-checkout/payment-links"
        return 200, json.dumps({"payment_link": link_obj}).encode("utf-8")

    monkeypatch.setattr(sc, "_http", fake_http)

    out = sc.create_payment_link("T", {"idempotency_key": "k", "order": {}})
    assert out == link_obj
    assert out["id"] == "PL123"
    assert out["url"] == "https://square.link/u/abc"
    assert out["order_id"] == "ORD123"


def test_create_payment_link_raises_on_error(monkeypatch):
    def fake_http(method, url, headers, data):
        return 400, json.dumps({"errors": [{"code": "X"}]}).encode("utf-8")

    monkeypatch.setattr(sc, "_http", fake_http)

    with pytest.raises(Exception) as ei:
        sc.create_payment_link("T", {"idempotency_key": "k"})
    assert "X" in str(ei.value) or "400" in str(ei.value)


def test_delete_payment_link_200_returns_status(monkeypatch):
    def fake_http(method, url, headers, data):
        assert method == "DELETE"
        assert url == sc.BASE + "/v2/online-checkout/payment-links/PL123"
        return 200, b"{}"

    monkeypatch.setattr(sc, "_http", fake_http)
    assert sc.delete_payment_link("T", "PL123") == 200


def test_delete_payment_link_404_ok(monkeypatch):
    def fake_http(method, url, headers, data):
        return 404, json.dumps({"errors": [{"code": "NOT_FOUND"}]}).encode("utf-8")

    monkeypatch.setattr(sc, "_http", fake_http)
    # 404 == already gone → treated as OK (returns the status, does not raise).
    assert sc.delete_payment_link("T", "GONE") == 404


# ---------------------------------------------------------------------------
# set_inventory_count — PHYSICAL_COUNT to make the item purchasable (C1).
# ---------------------------------------------------------------------------

def test_set_inventory_count_body_shape(monkeypatch):
    captured = {}

    def fake_http(method, url, headers, data):
        captured["method"] = method
        captured["url"] = url
        captured["data"] = data
        return 200, json.dumps({"counts": [{"quantity": "1"}]}).encode("utf-8")

    monkeypatch.setattr(sc, "_http", fake_http)

    out = sc.set_inventory_count("T", "VAR123", qty=1)
    assert out == {"counts": [{"quantity": "1"}]}

    assert captured["method"] == "POST"
    assert captured["url"] == sc.BASE + "/v2/inventory/batch-change"

    body = json.loads(captured["data"].decode("utf-8"))
    assert "idempotency_key" in body
    assert len(body["changes"]) == 1
    change = body["changes"][0]
    assert change["type"] == "PHYSICAL_COUNT"
    pc = change["physical_count"]
    assert pc["catalog_object_id"] == "VAR123"
    assert pc["state"] == "IN_STOCK"
    assert pc["location_id"] == sc.LOCATION_ID
    assert pc["quantity"] == "1"
    # occurred_at is a UTC ISO-8601 timestamp ending in Z.
    assert pc["occurred_at"].endswith("Z")
    assert "T" in pc["occurred_at"]


def test_set_inventory_count_default_qty_is_one(monkeypatch):
    captured = {}

    def fake_http(method, url, headers, data):
        captured["data"] = data
        return 200, b"{}"

    monkeypatch.setattr(sc, "_http", fake_http)
    sc.set_inventory_count("T", "VAR123")  # qty defaults to 1
    body = json.loads(captured["data"].decode("utf-8"))
    assert body["changes"][0]["physical_count"]["quantity"] == "1"


def test_set_inventory_count_raises_on_error(monkeypatch):
    def fake_http(method, url, headers, data):
        return 400, json.dumps(
            {"errors": [{"code": "BAD_REQUEST"}]}).encode("utf-8")

    monkeypatch.setattr(sc, "_http", fake_http)
    with pytest.raises(Exception) as ei:
        sc.set_inventory_count("T", "VAR123", qty=1)
    assert "BAD_REQUEST" in str(ei.value) or "400" in str(ei.value)


# ---------------------------------------------------------------------------
# resolve_token — copied resolver. env path is deterministic & network-free.
# ---------------------------------------------------------------------------

def test_resolve_token_prefers_env(monkeypatch):
    monkeypatch.setenv("SQUARE_ACCESS_TOKEN", "tok-from-env")
    assert sc.resolve_token() == "tok-from-env"


def test_resolve_token_legacy_env_name(monkeypatch):
    monkeypatch.delenv("SQUARE_ACCESS_TOKEN", raising=False)
    monkeypatch.setenv("SQUARE_TOKEN", "tok-legacy")
    assert sc.resolve_token() == "tok-legacy"


# ---------------------------------------------------------------------------
# gen_qr_png — only if qrcode is importable (the run command provides it).
# ---------------------------------------------------------------------------

def test_gen_qr_png_writes_file(tmp_path):
    if importlib.util.find_spec("qrcode") is None:
        pytest.skip("qrcode not installed")
    out = tmp_path / "qr.png"
    sc.gen_qr_png("https://richmondgeneral.example/RG-0099", str(out))
    assert out.exists()
    assert out.stat().st_size > 0
    # PNG magic number.
    assert out.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
