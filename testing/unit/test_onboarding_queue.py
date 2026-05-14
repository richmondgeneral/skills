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
