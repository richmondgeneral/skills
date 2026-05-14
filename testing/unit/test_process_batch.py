"""Tests for the batch orchestrator (PR #2)."""
import json
from pathlib import Path

import pytest

from process_batch import BatchOrchestrator
from item_state import ItemState, ItemStatus, PhaseStatus, PendingQuestion


def test_orchestrator_ingest_creates_state_files(tmp_path, monkeypatch):
    """ingest_photos creates one .state.json per valid image."""
    photo = tmp_path / "input" / "photo1.jpeg"
    photo.parent.mkdir()
    photo.write_bytes(b"fake")  # extension is what matters for the filter
    items_dir = tmp_path / "items"
    queue_path = tmp_path / "queue.json"

    orch = BatchOrchestrator(
        items_dir=str(items_dir),
        queue_path=str(queue_path),
        next_sku=lambda: "RG-0099",
    )
    states = orch.ingest_photos([str(photo)])
    assert len(states) == 1
    assert states[0].sku == "RG-0099"
    assert (items_dir / "RG-0099" / ".state.json").exists()


def test_orchestrator_advance_runs_phases_until_blocked(tmp_path):
    """_advance_item iterates next_runnable_phase until phase returns blocked or no more runnable."""
    items_dir = tmp_path / "items"
    items_dir.mkdir()
    sku = "RG-0099"
    (items_dir / sku).mkdir()
    state = ItemState(sku=sku, items_dir=str(items_dir),
                      source_image=str(tmp_path / "src.jpg"))
    (tmp_path / "src.jpg").write_bytes(b"x")
    state.save()

    # Phase handler that completes phase_0 with outputs, blocks phase_1.
    def fake_runner(state, phase, item_dir):
        if phase == "phase_0":
            return {"outputs": {"hero_path": "/tmp/x.png"}}
        if phase == "phase_1":
            return {
                "blocked": True,
                "question": PendingQuestion(
                    question_id="q-001", phase="phase_1",
                    question="What era?",
                ),
            }
        return {"outputs": {}}

    orch = BatchOrchestrator(
        items_dir=str(items_dir),
        queue_path=str(tmp_path / "queue.json"),
        phase_runner=fake_runner,
    )
    result = orch._advance_item(state)
    assert state.phases["phase_0"].status == PhaseStatus.COMPLETED
    assert state.phases["phase_1"].status == PhaseStatus.BLOCKED
    assert state.status == ItemStatus.BLOCKED


def test_orchestrator_process_all_returns_summary(tmp_path):
    """process_all returns counts of completed/blocked/failed across items."""
    items_dir = tmp_path / "items"
    items_dir.mkdir()
    queue_path = tmp_path / "queue.json"

    for sku in ("RG-0001", "RG-0002"):
        (items_dir / sku).mkdir()
        state = ItemState(sku=sku, items_dir=str(items_dir),
                          source_image=str(tmp_path / f"{sku}.jpg"))
        (tmp_path / f"{sku}.jpg").write_bytes(b"x")
        state.save()

    from onboarding_queue import OnboardingQueue, QueueEntry
    queue = OnboardingQueue(queue_path=str(queue_path))
    queue.upsert(QueueEntry(sku="RG-0001", status="queued"))
    queue.upsert(QueueEntry(sku="RG-0002", status="queued"))
    queue.save()

    # Trivial runner that completes every phase with empty outputs
    def trivial(state, phase, item_dir):
        return {"outputs": {}}

    orch = BatchOrchestrator(
        items_dir=str(items_dir),
        queue_path=str(queue_path),
        phase_runner=trivial,
    )
    summary = orch.process_all()
    assert summary["processed"] == 2
    assert summary["completed"] == 2
    assert summary["blocked"] == 0
    assert summary["failed"] == 0
