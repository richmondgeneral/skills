"""Integration: the blocking Hero QA gate at the publish phases.

can_list() is the read-side chokepoint (pure label.json read, no cv2). The
process_batch _advance_item hook refuses phase_4 (Square primary) / phase_7
(GitHub publish) unless hero_qa.status == 'pass'.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import item_state as ist


def test_can_list_false_without_pass(tmp_path):
    item = tmp_path / "RG-3000"
    item.mkdir()
    (item / "label.json").write_text(json.dumps({"state": "Priced"}))   # no hero_qa
    ok, reason = ist.can_list(str(item))
    assert ok is False
    assert "hero_qa" in reason


def test_can_list_false_on_explicit_fail(tmp_path):
    item = tmp_path / "RG-3002"
    item.mkdir()
    (item / "label.json").write_text(json.dumps({"hero_qa": {"status": "fail"}}))
    assert ist.can_list(str(item))[0] is False


def test_can_list_true_with_pass(tmp_path):
    item = tmp_path / "RG-3001"
    item.mkdir()
    (item / "label.json").write_text(json.dumps({"hero_qa": {"status": "pass"}}))
    assert ist.can_list(str(item))[0] is True


def test_publish_phases_constant_covers_upload_and_publish():
    assert "phase_4" in ist.PUBLISH_PHASES      # Square primary upload
    assert "phase_7" in ist.PUBLISH_PHASES      # GitHub Pages publishing


def test_advance_item_blocks_publish_phase_when_gate_fails(tmp_path, monkeypatch):
    """A whole-pipeline check: with hero_qa absent and the gate runner stubbed
    to leave it failing, the orchestrator must BLOCK at the first publish phase
    rather than run it."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
    import process_batch as pb

    sku = "RG-3100"
    item_dir = tmp_path / sku
    item_dir.mkdir()
    (item_dir / "label.json").write_text(json.dumps({"state": "Priced"}))  # no hero_qa

    # Build an item whose phases 0..3,5,6 are done so phase_4 is next-runnable.
    state = ist.ItemState(sku=sku, items_dir=str(tmp_path))
    for ph in ("phase_0", "phase_1", "phase_2", "phase_3", "phase_5", "phase_6"):
        state.complete_phase(ph)
    state.save()

    # phase_runner must NEVER be called for a publish phase that's gated off.
    ran = []

    def runner(st, phase, idir):
        ran.append(phase)
        return {"outputs": {}}

    orch = pb.BatchOrchestrator(items_dir=str(tmp_path), phase_runner=runner,
                                queue_path=str(tmp_path / "queue.json"))
    # Stub the gate runner so it does NOT write a pass (simulates a failing hero).
    monkeypatch.setattr(orch, "_run_hero_qa", lambda idir: None)

    orch._advance_item(state)

    assert "phase_4" not in ran                  # publish phase was blocked, not run
    assert state.phases["phase_4"].status == ist.PhaseStatus.BLOCKED
