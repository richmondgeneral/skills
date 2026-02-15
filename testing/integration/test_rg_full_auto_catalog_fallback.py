from unittest.mock import patch

import requests

from process_new_item import RGItemProcessor


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


def _item_data(sku: str = "RG-9999"):
    return {
        "sku": sku,
        "title": "Test Item",
        "description": "Test Description",
        "seo_title": "Test SEO",
        "seo_description": "Test SEO Description",
        "permalink": "test-item",
        "price": 19.99,
    }


def test_phase3_catalog_falls_back_to_upsert_and_sets_inventory(monkeypatch):
    monkeypatch.setenv("SQUARE_ACCESS_TOKEN", "test-square-token")
    monkeypatch.setenv("REMOVEBG_API_KEY", "test-removebg-token")

    processor = RGItemProcessor(interactive=False)

    call_log = []

    batch_fail = FakeResponse(400, {"errors": [{"detail": "schema mismatch"}]})
    upsert_success = FakeResponse(
        200,
        {
            "id_mappings": [
                {"client_object_id": "#RG-9999", "object_id": "ITEM_REAL_123"},
                {"client_object_id": "#RG-9999-var", "object_id": "VAR_REAL_123"},
            ],
            "catalog_object": {
                "id": "ITEM_REAL_123",
                "item_data": {"variations": [{"id": "VAR_REAL_123"}]},
            },
        },
    )
    inventory_success = FakeResponse(200, {"counts": []})

    responses = [batch_fail, upsert_success, inventory_success]

    def fake_post(url, headers=None, json=None, **kwargs):
        call_log.append({"url": url, "json": json, "headers": headers})
        return responses.pop(0)

    with patch("process_new_item.requests.post", side_effect=fake_post):
        result = processor.phase3_catalog(_item_data())

    assert result["item_id"] == "ITEM_REAL_123"
    assert result["variation_id"] == "VAR_REAL_123"

    assert call_log[0]["url"].endswith("/catalog/batch-upsert")
    assert call_log[1]["url"].endswith("/catalog/object")
    assert call_log[2]["url"].endswith("/inventory/batch-change")

    assert "batches" in call_log[0]["json"]
    assert "object" in call_log[1]["json"]
    assert call_log[0]["json"]["idempotency_key"] == call_log[1]["json"]["idempotency_key"]


def test_extract_catalog_ids_uses_object_fallback_when_no_mappings(monkeypatch):
    monkeypatch.setenv("SQUARE_ACCESS_TOKEN", "test-square-token")
    monkeypatch.setenv("REMOVEBG_API_KEY", "test-removebg-token")

    processor = RGItemProcessor(interactive=False)

    payload = {
        "objects": [
            {
                "id": "ITEM_OBJ_1",
                "item_data": {
                    "variations": [
                        {"id": "VAR_OBJ_1"},
                    ]
                },
            }
        ]
    }

    ids = processor._extract_catalog_ids(payload, "RG-5555")
    assert ids == {"item_id": "ITEM_OBJ_1", "variation_id": "VAR_OBJ_1"}
