from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from cache_wrapper import SquareCacheWrapper


@patch("cache_wrapper.MongoClient")
def test_get_status_uses_counts_and_last_sync(mock_mongo_client):
    client = MagicMock()
    db = MagicMock()
    items = MagicMock()
    changes = MagicMock()
    sync_log = MagicMock()

    mock_mongo_client.return_value = client
    client.__getitem__.return_value = db
    db.__getitem__.side_effect = [items, changes, sync_log]

    items.count_documents.return_value = 15
    changes.count_documents.return_value = 4
    sync_log.count_documents.return_value = 8
    sync_log.find_one.return_value = {
        "timestamp": datetime(2026, 2, 14, 23, 0, tzinfo=timezone.utc),
        "items_processed": 15,
        "changes_detected": 2,
    }

    wrapper = SquareCacheWrapper("mongodb://test")
    status = wrapper.get_status()

    assert status["mongodb_running"] is True
    assert status["items_count"] == 15
    assert status["changes_count"] == 4
    assert status["sync_count"] == 8
    assert status["last_sync"]["status"] == "success"
    assert status["last_sync"]["items_processed"] == 15


@patch("cache_wrapper.MongoClient")
def test_search_items_shapes_response_fields(mock_mongo_client):
    client = MagicMock()
    db = MagicMock()
    items = MagicMock()
    changes = MagicMock()
    sync_log = MagicMock()

    mock_mongo_client.return_value = client
    client.__getitem__.return_value = db
    db.__getitem__.side_effect = [items, changes, sync_log]

    items.find.return_value = [
        {
            "id": "ITEM_1",
            "item_data": {
                "name": "Vintage Bowl",
                "description": "Iridescent",
                "image_ids": ["IMG_1"],
                "variations": [{"id": "VAR_1"}],
            },
            "updated_at": "2026-02-14T00:00:00Z",
            "version": 123,
        }
    ]

    wrapper = SquareCacheWrapper("mongodb://test")
    results = wrapper.search_items("bowl", limit=5)

    assert len(results) == 1
    assert results[0]["id"] == "ITEM_1"
    assert results[0]["name"] == "Vintage Bowl"
    assert results[0]["has_variations"] is True
    items.find.assert_called_once()
    _, kwargs = items.find.call_args
    assert kwargs["limit"] == 5
