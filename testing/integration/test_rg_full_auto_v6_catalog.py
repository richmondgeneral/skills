"""v6.0 catalog-collision integration test — companion to the v3.7 catalog_fallback test.

Verifies the BatchOrchestrator's phase_2 gate: when the SKU already exists in the
Square catalog cache, the phase blocks with a question presenting overwrite/skip/renumber
options and the item is left in BLOCKED status.

The pre-existing v3.7 integration test at testing/integration/test_rg_full_auto_catalog_fallback.py
remains in place — it documents the legacy upsert-fallback path of RGItemProcessor and still passes.
"""
from pathlib import Path

import pytest

from item_state import ItemState, ItemStatus
from onboarding_queue import OnboardingQueue, QueueEntry


FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "sample-photo.jpeg"


def test_v6_catalog_block_on_sku_collision(tmp_path, monkeypatch):
    """If the SKU already exists in Square cache, phase_2 blocks for resolution."""
    items_dir = tmp_path / "items"
    (items_dir / "RG-9999").mkdir(parents=True)
    state = ItemState(
        sku="RG-9999",
        items_dir=str(items_dir),
        source_image=str(FIXTURE),
    )
    # Pre-complete phase_0 and phase_1 so phase_2 is the next runnable phase.
    state.start_phase("phase_0")
    state.complete_phase("phase_0", outputs={"hero_path": "/x.png"})
    state.start_phase("phase_1")
    state.complete_phase("phase_1", outputs={"title": "T", "price": 10})
    state.save()

    queue_path = tmp_path / "queue.json"
    q = OnboardingQueue(queue_path=str(queue_path))
    q.upsert(QueueEntry.from_item_state(state))
    q.save()

    import process_batch as pb
    monkeypatch.setattr(pb, "_check_sku_in_square_cache",
                        lambda sku: "EXISTING_ITEM_ID")

    orch = pb.BatchOrchestrator(
        items_dir=str(items_dir),
        queue_path=str(queue_path),
    )
    summary = orch.process_all()
    assert summary["blocked"] == 1, f"Expected 1 blocked, got summary={summary}"

    loaded = ItemState.load("RG-9999", items_dir=str(items_dir))
    assert loaded.status == ItemStatus.BLOCKED
    assert any(q.get("phase") == "phase_2" for q in loaded.questions)
    # The collision question should offer the documented options.
    collision_q = next(q for q in loaded.questions if q.get("phase") == "phase_2")
    assert "overwrite" in collision_q.get("options", [])
