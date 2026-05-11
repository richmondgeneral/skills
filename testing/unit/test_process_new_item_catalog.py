"""
Tests for process_new_item.py — covers the catalog-payload construction
and top-level-room behavior. Pre-fix bugs covered:
  - line 257 used the deprecated `description` field where v3.2 mandates
    `description_html` with <p> tags
  - Apothecary Cabinet (a top-level room) triggered the "not in ROOM_BY_TYPE"
    warning, because the script treated it as a missing TYPE→ROOM mapping
"""
import os
import sys
from unittest.mock import patch

import pytest

# The script reads SQUARE_ACCESS_TOKEN and REMOVEBG_API_KEY at constructor
# time and refuses to run without them. Set placeholders before import.
os.environ.setdefault("SQUARE_ACCESS_TOKEN", "test-token")
os.environ.setdefault("REMOVEBG_API_KEY", "test-key")

from process_new_item import RGItemProcessor  # noqa: E402


@pytest.fixture
def processor():
    return RGItemProcessor(interactive=False)


@pytest.fixture
def base_item_data():
    return {
        "title": "Test Item",
        "description": "<p>A short description.</p>",
        "sku": "RG-9999",
        "era": "1970s",
        "price": 19.99,
        "condition": "Very Good",
        "maker": "Test Maker",
        "origin": "USA",
        "seo_title": "Test SEO",
        "seo_description": "Test SEO description.",
        "permalink": "test-item",
    }


def test_catalog_uses_description_html_not_description(processor, base_item_data):
    """Regression: v3.2 mandates description_html; plain `description`
    renders raw HTML on richmondgeneral.com."""
    obj = processor._build_catalog_object(base_item_data, price_cents=1999,
                                          sku="RG-9999")
    item_data = obj["item_data"]
    assert "description_html" in item_data
    assert item_data["description_html"] == "<p>A short description.</p>"
    assert "description" not in item_data, (
        "deprecated `description` field must not be emitted")


def test_top_level_room_type_does_not_emit_warning(processor, base_item_data, capsys):
    """When the TYPE is itself a top-level room (Apothecary Cabinet, Gallery,
    etc.), no ROOM upcast is needed and the script must NOT print the
    'not in ROOM_BY_TYPE' warning."""
    base_item_data["type_category_id"] = "QIPW32HGKMU5BDPU3A7YZCM4"  # Apothecary Cabinet
    processor._build_catalog_object(base_item_data, price_cents=1999, sku="RG-9999")
    captured = capsys.readouterr()
    assert "not in ROOM_BY_TYPE" not in captured.out, (
        f"top-level room triggered spurious warning: {captured.out!r}")


def test_regular_type_attaches_room(processor, base_item_data):
    """A normal TYPE under a room (e.g. Books & Paper under General Store)
    should attach BOTH the type and the room to categories."""
    base_item_data["type_category_id"] = "CLZCJ62H4TTHDQ3ZBYMZQASQ"  # Books & Paper
    obj = processor._build_catalog_object(base_item_data, price_cents=1999, sku="RG-9999")
    cat_ids = [c["id"] for c in obj["item_data"]["categories"]]
    assert "CLZCJ62H4TTHDQ3ZBYMZQASQ" in cat_ids  # type
    assert "QLM2GZ643LOCYHB653YIDJWT" in cat_ids  # The General Store room
    # reporting_category must be the TYPE (per square-catalog.md)
    assert obj["item_data"]["reporting_category"]["id"] == "CLZCJ62H4TTHDQ3ZBYMZQASQ"


def test_unknown_type_emits_warning_and_ships_with_just_type_and_tier(
        processor, base_item_data, capsys):
    """A type that's neither in ROOM_BY_TYPE nor a top-level room should
    warn but still ship the item (defensive: better incomplete nav than
    no item at all)."""
    base_item_data["type_category_id"] = "UNKNOWN_FAKE_ID_NEVER_REAL_XX"
    obj = processor._build_catalog_object(base_item_data, price_cents=1999, sku="RG-9999")
    captured = capsys.readouterr()
    assert "not in ROOM_BY_TYPE" in captured.out
    cat_ids = [c["id"] for c in obj["item_data"]["categories"]]
    assert "UNKNOWN_FAKE_ID_NEVER_REAL_XX" in cat_ids
    # Tier should still be present.
    assert processor.categories["new_finds"] in cat_ids


def test_no_type_category_falls_back_to_tier_only(processor, base_item_data, capsys):
    """If the caller omits type_category_id entirely, the item ships with
    just the tier (warning logged) so it's at least discoverable."""
    obj = processor._build_catalog_object(base_item_data, price_cents=1999, sku="RG-9999")
    captured = capsys.readouterr()
    assert "no type_category_id provided" in captured.out
    cat_ids = [c["id"] for c in obj["item_data"]["categories"]]
    assert cat_ids == [processor.categories["new_finds"]]
