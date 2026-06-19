from item_model.channel_registry import (
    REGISTRY_CHANNEL_KEYS, LISTED_STATUSES, listed_on_from_registry, sold_from_label,
)
from item_model.models import Channel

def test_registry_keys_map_sales_channels_only():
    assert REGISTRY_CHANNEL_KEYS["square"] is Channel.SQUARE
    assert REGISTRY_CHANNEL_KEYS["whatnot"] is Channel.WHATNOT
    assert "github_page" not in REGISTRY_CHANNEL_KEYS

def test_listed_on_derives_from_listed_status():
    channels = {
        "square": {"status": "listed", "object_id": "X"},
        "whatnot": {"status": "not_listed"},
        "github_page": {"status": "listed"},
    }
    assert listed_on_from_registry(channels) == [Channel.SQUARE]

def test_listed_status_aliases_and_case_insensitive():
    channels = {"square": {"status": "Active"}, "ebay": {"status": "LIVE"}}
    assert set(listed_on_from_registry(channels)) == {Channel.SQUARE, Channel.EBAY}

def test_sold_from_state():
    assert sold_from_label({"state": "Sold"}, status_json=None) is True
    assert sold_from_label({"state": "Archived"}, status_json=None) is True
    assert sold_from_label({"state": "Listed"}, status_json=None) is False

def test_sold_from_channel_status():
    assert sold_from_label({"channels": {"square": {"status": "sold"}}}, status_json=None) is True

def test_sold_from_status_json_wins():
    assert sold_from_label({}, status_json={"status": "sold"}) is True

def test_no_signals_not_sold():
    assert sold_from_label({"channels": {"square": {"status": "listed"}}}, status_json=None) is False
