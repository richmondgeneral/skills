"""Tests for the centralized onboarding queue."""
import pytest
from onboarding_queue import OnboardingQueue, QueueEntry
from item_state import ItemStatus
from pathlib import Path
import json


def test_queue_add_entry(tmp_path):
    """Adding an entry shows up in the queue file."""
    queue_file = tmp_path / "queue.json"
    q = OnboardingQueue(queue_path=str(queue_file))
    q.upsert(QueueEntry(sku="RG-0099", status=ItemStatus.QUEUED.value))
    q.save()
    data = json.loads(queue_file.read_text())
    assert any(e["sku"] == "RG-0099" for e in data["entries"])


def test_queue_upsert_updates_existing(tmp_path):
    """Upserting same SKU twice updates rather than duplicates."""
    queue_file = tmp_path / "queue.json"
    q = OnboardingQueue(queue_path=str(queue_file))
    q.upsert(QueueEntry(sku="RG-0099", status="queued"))
    q.upsert(QueueEntry(sku="RG-0099", status="processing"))
    q.save()
    data = json.loads(queue_file.read_text())
    matching = [e for e in data["entries"] if e["sku"] == "RG-0099"]
    assert len(matching) == 1
    assert matching[0]["status"] == "processing"


def test_queue_remove(tmp_path):
    """Removing by SKU drops the entry."""
    queue_file = tmp_path / "queue.json"
    q = OnboardingQueue(queue_path=str(queue_file))
    q.upsert(QueueEntry(sku="RG-0099", status="queued"))
    q.upsert(QueueEntry(sku="RG-0100", status="queued"))
    q.remove("RG-0099")
    q.save()
    data = json.loads(queue_file.read_text())
    assert not any(e["sku"] == "RG-0099" for e in data["entries"])
    assert any(e["sku"] == "RG-0100" for e in data["entries"])


def test_queue_load_missing_file(tmp_path):
    """Loading a non-existent queue file yields an empty queue."""
    queue_file = tmp_path / "does-not-exist.json"
    q = OnboardingQueue(queue_path=str(queue_file))
    assert q.entries == []


def test_queue_entry_from_item_state(tmp_path):
    """QueueEntry.from_item_state populates fields from a live ItemState."""
    from item_state import ItemState, ItemStatus, PhaseStatus
    (tmp_path / "RG-0099").mkdir()
    state = ItemState(sku="RG-0099", items_dir=str(tmp_path))
    state.start_phase("phase_0")
    state.complete_phase("phase_0", outputs={})
    entry = QueueEntry.from_item_state(state)
    assert entry.sku == "RG-0099"
    assert entry.status == state.status.value
    assert entry.phases_completed == 1
    assert entry.phases_total == 10


def test_queue_get_active_excludes_completed_and_failed(tmp_path):
    q = OnboardingQueue(queue_path=str(tmp_path / "queue.json"))
    q.upsert(QueueEntry(sku="RG-0001", status="queued"))
    q.upsert(QueueEntry(sku="RG-0002", status="processing"))
    q.upsert(QueueEntry(sku="RG-0003", status="completed"))
    q.upsert(QueueEntry(sku="RG-0004", status="failed"))
    q.upsert(QueueEntry(sku="RG-0005", status="blocked"))
    active = q.get_active()
    skus = {e.sku for e in active}
    assert skus == {"RG-0001", "RG-0002", "RG-0005"}  # blocked stays active for resume


def test_queue_get_blocked(tmp_path):
    q = OnboardingQueue(queue_path=str(tmp_path / "queue.json"))
    q.upsert(QueueEntry(sku="RG-0001", status="queued"))
    q.upsert(QueueEntry(sku="RG-0002", status="blocked"))
    blocked = q.get_blocked()
    assert len(blocked) == 1
    assert blocked[0].sku == "RG-0002"
