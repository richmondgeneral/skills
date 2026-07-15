import json

import pytest

import ebay_lister


def _config(name):
    values = {
        "EBAY_MARKETPLACE": "EBAY_US",
        "EBAY_FULFILLMENT_POLICY_ID": "fulfillment",
        "EBAY_PAYMENT_POLICY_ID": "payment",
        "EBAY_RETURN_POLICY_ID": "return",
        "EBAY_LOCATION_KEY": "richmond-il",
    }
    return values.get(name)


def test_condition_mapping_prefers_specific_phrases():
    assert ebay_lister._map_condition("Like New") == "LIKE_NEW"
    assert ebay_lister._map_condition("Very Good") == "USED_VERY_GOOD"
    assert ebay_lister._map_condition("New without box") == "NEW_OTHER"
    assert ebay_lister._map_condition("For parts or not working") == "FOR_PARTS_OR_NOT_WORKING"


def test_sku_validation_blocks_path_traversal():
    assert ebay_lister._normalize_sku("rg-0032") == "RG-0032"
    with pytest.raises(ValueError, match="RG-XXXX"):
        ebay_lister._normalize_sku("../../secrets")


def test_payload_contains_publish_requirements(tmp_path, monkeypatch):
    item_dir = tmp_path / "RG-0032"
    item_dir.mkdir()
    (item_dir / "hero.png").write_bytes(b"image")
    monkeypatch.setattr(ebay_lister, "ITEMS_DIR", tmp_path)
    monkeypatch.setattr(ebay_lister.auth, "resolve", _config)
    label = {
        "product_name": "Like-new reference book",
        "attributes": "Hardcover • Illustrated",
        "price": "14.00",
        "condition": "Like New",
        "condition_notes": "Clean copy with light shelf wear.",
        "channels": {"square": {"categories": ["Books & Paper"]}},
    }

    payloads = ebay_lister.build_payloads("RG-0032", label, None, [], None)

    assert payloads["inventory_item"]["condition"] == "LIKE_NEW"
    assert payloads["inventory_item"]["conditionDescription"] == label["condition_notes"]
    assert payloads["offer"]["listingDuration"] == "GTC"
    assert ebay_lister._missing_requirements(payloads) == []


def test_missing_requirements_rejects_invalid_price_and_images(monkeypatch):
    monkeypatch.setattr(ebay_lister.auth, "resolve", _config)
    payloads = ebay_lister.build_payloads(
        "RG-0032",
        {
            "product_name": "Book",
            "attributes": "Hardcover",
            "price": "free",
            "condition": "Good",
            "condition_notes": "Used copy.",
            "channels": {"square": {"categories": ["Books"]}},
        },
        None,
        [],
        None,
    )

    missing = ebay_lister._missing_requirements(payloads)
    assert "price" in missing
    assert "product.imageUrls" in missing


def test_publish_is_blocked_without_explicit_live_flag(monkeypatch):
    monkeypatch.setattr(ebay_lister, "_live_writes_enabled", lambda: False)

    with pytest.raises(SystemExit, match="live eBay API writes are disabled"):
        ebay_lister.cmd_list("RG-0032", False, True, None, [], None)


def test_dry_run_never_calls_ebay(tmp_path, monkeypatch, capsys):
    item_dir = tmp_path / "RG-0032"
    item_dir.mkdir()
    (item_dir / "hero.png").write_bytes(b"image")
    (item_dir / "label.json").write_text(
        json.dumps(
            {
                "product_name": "Reference Book",
                "attributes": "Hardcover",
                "price": "14.00",
                "condition": "Good",
                "condition_notes": "Used copy.",
                "channels": {"square": {"categories": ["Books"]}},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(ebay_lister, "ITEMS_DIR", tmp_path)
    monkeypatch.setattr(ebay_lister.auth, "resolve", _config)
    monkeypatch.setattr(
        ebay_lister.auth,
        "get_access_token",
        lambda: pytest.fail("dry-run requested an access token"),
    )

    assert ebay_lister.cmd_list("RG-0032", True, False, None, [], None) == 0
    assert '"dry_run": true' in capsys.readouterr().out


def test_published_offer_is_updated_without_republishing(tmp_path, monkeypatch):
    item_dir = tmp_path / "RG-0032"
    item_dir.mkdir()
    (item_dir / "hero.png").write_bytes(b"image")
    label_path = item_dir / "label.json"
    label_path.write_text(
        json.dumps(
            {
                "product_name": "Reference Book",
                "attributes": "Hardcover",
                "price": "14.00",
                "condition": "Good",
                "condition_notes": "Used copy.",
                "channels": {
                    "square": {"categories": ["Books"]},
                    "ebay": {"preserve_me": True},
                },
            }
        ),
        encoding="utf-8",
    )

    class Response:
        def __init__(self, status_code, payload=None, text=""):
            self.status_code = status_code
            self._payload = payload or {}
            self.text = text

        def json(self):
            return self._payload

    put_urls = []

    def fake_put(url, **kwargs):
        put_urls.append(url)
        return Response(204)

    monkeypatch.setattr(ebay_lister, "ITEMS_DIR", tmp_path)
    monkeypatch.setattr(ebay_lister, "_live_writes_enabled", lambda: True)
    monkeypatch.setattr(ebay_lister.auth, "resolve", _config)
    monkeypatch.setattr(ebay_lister.auth, "get_access_token", lambda: "token")
    monkeypatch.setattr(
        ebay_lister.auth,
        "hosts",
        lambda: {
            "api": "https://api.example.test",
            "itm": "https://www.example.test/itm/",
        },
    )
    monkeypatch.setattr(ebay_lister.auth, "_env_mode", lambda: "sandbox")
    monkeypatch.setattr(ebay_lister.requests, "put", fake_put)
    monkeypatch.setattr(
        ebay_lister.requests,
        "get",
        lambda *args, **kwargs: Response(
            200,
            {
                "offers": [
                    {
                        "offerId": "offer-1",
                        "format": "FIXED_PRICE",
                        "marketplaceId": "EBAY_US",
                        "status": "PUBLISHED",
                        "listing": {"listingId": "listing-1"},
                    }
                ]
            },
        ),
    )
    monkeypatch.setattr(
        ebay_lister.requests,
        "post",
        lambda *args, **kwargs: pytest.fail("published offer was republished"),
    )

    assert ebay_lister.cmd_list("RG-0032", False, True, None, [], None) == 0
    assert put_urls == [
        "https://api.example.test/sell/inventory/v1/inventory_item/RG-0032",
        "https://api.example.test/sell/inventory/v1/offer/offer-1",
    ]
    written = json.loads(label_path.read_text(encoding="utf-8"))
    assert written["channels"]["ebay"]["preserve_me"] is True
    assert written["channels"]["ebay"]["item_id"] == "listing-1"


def test_new_offer_is_created_then_published(tmp_path, monkeypatch):
    item_dir = tmp_path / "RG-0032"
    item_dir.mkdir()
    (item_dir / "hero.png").write_bytes(b"image")
    label_path = item_dir / "label.json"
    label_path.write_text(
        json.dumps(
            {
                "product_name": "Reference Book",
                "attributes": "Hardcover",
                "price": "14.00",
                "condition": "Good",
                "condition_notes": "Used copy.",
                "channels": {"square": {"categories": ["Books"]}},
            }
        ),
        encoding="utf-8",
    )

    class Response:
        def __init__(self, status_code, payload=None):
            self.status_code = status_code
            self._payload = payload or {}
            self.text = ""

        def json(self):
            return self._payload

    post_urls = []

    def fake_post(url, **kwargs):
        post_urls.append(url)
        if url.endswith("/offer"):
            return Response(201, {"offerId": "offer-1"})
        if url.endswith("/offer/offer-1/publish"):
            return Response(200, {"listingId": "listing-1"})
        pytest.fail(f"unexpected POST {url}")

    monkeypatch.setattr(ebay_lister, "ITEMS_DIR", tmp_path)
    monkeypatch.setattr(ebay_lister, "_live_writes_enabled", lambda: True)
    monkeypatch.setattr(ebay_lister.auth, "resolve", _config)
    monkeypatch.setattr(ebay_lister.auth, "get_access_token", lambda: "token")
    monkeypatch.setattr(
        ebay_lister.auth,
        "hosts",
        lambda: {
            "api": "https://api.example.test",
            "itm": "https://www.example.test/itm/",
        },
    )
    monkeypatch.setattr(ebay_lister.auth, "_env_mode", lambda: "sandbox")
    monkeypatch.setattr(ebay_lister.requests, "put", lambda *args, **kwargs: Response(204))
    monkeypatch.setattr(
        ebay_lister.requests,
        "get",
        lambda *args, **kwargs: Response(200, {"offers": []}),
    )
    monkeypatch.setattr(ebay_lister.requests, "post", fake_post)

    assert ebay_lister.cmd_list("RG-0032", False, True, None, [], None) == 0
    assert post_urls == [
        "https://api.example.test/sell/inventory/v1/offer",
        "https://api.example.test/sell/inventory/v1/offer/offer-1/publish",
    ]
    written = json.loads(label_path.read_text(encoding="utf-8"))
    assert written["channels"]["ebay"]["offer_id"] == "offer-1"
    assert written["channels"]["ebay"]["item_id"] == "listing-1"
