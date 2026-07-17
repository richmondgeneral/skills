"""Integration: the blocking listing-IMAGE gate at the publish phases.

Closes the RG-0023 gap: an item reached state Listed on Square with ZERO
images and the storefront showed a placeholder. The gate asserts the Square
catalog item has >=1 image before phase_4 (Square primary) / phase_7 (GitHub
publish), mirroring the hero_qa gate's BLOCK + parked-question behavior.

has_square_image() is the read-side chokepoint. The image count comes from a
live Square lookup (injected/mocked here so tests never hit the network); it
falls back to label.json -> channels.square.image_ids when None.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import item_state as ist


def _write_label(item_dir, payload):
    (item_dir / "label.json").write_text(json.dumps(payload))


# ── has_square_image() read-side chokepoint ──

def test_has_square_image_false_with_zero_images_from_count(tmp_path):
    item = tmp_path / "RG-3200"
    item.mkdir()
    _write_label(item, {"channels": {"square": {"object_id": "ABC123"}}})
    ok, reason = ist.has_square_image(str(item), image_count=0)
    assert ok is False
    assert "no image" in reason
    assert "ABC123" in reason  # names the offending Square item


def test_has_square_image_true_with_one_image_from_count(tmp_path):
    item = tmp_path / "RG-3201"
    item.mkdir()
    _write_label(item, {"channels": {"square": {"object_id": "ABC123"}}})
    ok, reason = ist.has_square_image(str(item), image_count=1)
    assert ok is True
    assert "1 image" in reason


def test_has_square_image_falls_back_to_label_image_ids(tmp_path):
    """image_count=None -> count label.json channels.square.image_ids."""
    item = tmp_path / "RG-3202"
    item.mkdir()
    _write_label(item, {"channels": {"square": {
        "object_id": "OID", "image_ids": ["IMG1", "IMG2"]}}})
    assert ist.has_square_image(str(item))[0] is True  # no count -> fallback


def test_has_square_image_fallback_empty_blocks(tmp_path):
    item = tmp_path / "RG-3203"
    item.mkdir()
    _write_label(item, {"channels": {"square": {"object_id": "OID"}}})  # no image_ids
    assert ist.has_square_image(str(item))[0] is False


def test_has_square_image_no_label_blocks(tmp_path):
    item = tmp_path / "RG-3204"
    item.mkdir()
    assert ist.has_square_image(str(item))[0] is False


def test_square_image_ids_reads_list(tmp_path):
    item = tmp_path / "RG-3205"
    item.mkdir()
    _write_label(item, {"channels": {"square": {"image_ids": ["A", "B", "C"]}}})
    assert ist.square_image_ids(str(item)) == ["A", "B", "C"]


# ── orchestrator wiring: block phase_4 / phase_7 when Square has no image ──

def _make_state_ready_for_phase4(tmp_path, sku):
    state = ist.ItemState(sku=sku, items_dir=str(tmp_path))
    for ph in ("phase_0", "phase_1", "phase_2", "phase_3", "phase_5", "phase_6"):
        state.complete_phase(ph)
    state.save()
    return state


def test_advance_item_blocks_phase4_when_square_has_no_image(tmp_path):
    """phase_4 must BLOCK (not run) when the Square item has zero images, and
    park the 'no image — upload a hero before listing' question."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
    import process_batch as pb

    sku = "RG-3300"
    item_dir = tmp_path / sku
    item_dir.mkdir()
    # hero_qa passes (so we isolate the IMAGE gate), but Square has no image.
    _write_label(item_dir, {"hero_qa": {"status": "pass"},
                            "channels": {"square": {"object_id": "OIDZERO"}}})

    state = _make_state_ready_for_phase4(tmp_path, sku)

    ran = []

    def runner(st, phase, idir):
        ran.append(phase)
        return {"outputs": {}}

    orch = pb.BatchOrchestrator(items_dir=str(tmp_path), phase_runner=runner,
                               queue_path=str(tmp_path / "queue.json"))
    # Mock the live Square lookup -> zero images (no network).
    orch.square_image_count = lambda idir: 0

    orch._advance_item(state)

    assert "phase_4" not in ran  # publish phase was blocked, not run
    assert state.phases["phase_4"].status == ist.PhaseStatus.BLOCKED
    parked = [q for q in state.questions if q.get("phase") == "phase_4"]
    assert parked, "expected a parked question for phase_4"
    assert "no image" in parked[-1]["question"]
    assert "OIDZERO" in parked[-1]["question"]


def test_advance_item_allows_publish_when_square_has_image(tmp_path):
    """With hero_qa pass AND >=1 Square image, the publish phases run."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
    import process_batch as pb

    sku = "RG-3301"
    item_dir = tmp_path / sku
    item_dir.mkdir()
    _write_label(item_dir, {"hero_qa": {"status": "pass"},
                            "channels": {"square": {"object_id": "OIDOK"}}})

    state = _make_state_ready_for_phase4(tmp_path, sku)

    ran = []

    def runner(st, phase, idir):
        ran.append(phase)
        return {"outputs": {}}

    orch = pb.BatchOrchestrator(items_dir=str(tmp_path), phase_runner=runner,
                               queue_path=str(tmp_path / "queue.json"))
    orch.square_image_count = lambda idir: 1  # Square has an image

    orch._advance_item(state)

    assert "phase_4" in ran  # gate passed -> phase ran
    assert "phase_7" in ran
    assert state.phases["phase_4"].status == ist.PhaseStatus.COMPLETED
    assert state.phases["phase_7"].status == ist.PhaseStatus.COMPLETED


def test_advance_item_image_gate_falls_back_to_label_when_count_none(tmp_path):
    """When the live count is None (Square unreachable), the gate falls back to
    label.json channels.square.image_ids — empty there must still BLOCK."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
    import process_batch as pb

    sku = "RG-3302"
    item_dir = tmp_path / sku
    item_dir.mkdir()
    _write_label(item_dir, {"hero_qa": {"status": "pass"},
                            "channels": {"square": {"object_id": "OIDNONE"}}})

    state = _make_state_ready_for_phase4(tmp_path, sku)

    ran = []
    orch = pb.BatchOrchestrator(
        items_dir=str(tmp_path),
        phase_runner=lambda st, ph, idir: ran.append(ph) or {"outputs": {}},
        queue_path=str(tmp_path / "queue.json"),
    )
    orch.square_image_count = lambda idir: None  # Square unreachable -> fallback

    orch._advance_item(state)

    assert "phase_4" not in ran
    assert state.phases["phase_4"].status == ist.PhaseStatus.BLOCKED


def test_advance_item_image_gate_passes_via_label_fallback(tmp_path):
    """Live count None but label.json records image_ids -> gate PASSES."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
    import process_batch as pb

    sku = "RG-3303"
    item_dir = tmp_path / sku
    item_dir.mkdir()
    _write_label(item_dir, {"hero_qa": {"status": "pass"},
                            "channels": {"square": {
                                "object_id": "OIDLBL", "image_ids": ["IMGX"]}}})

    state = _make_state_ready_for_phase4(tmp_path, sku)

    ran = []
    orch = pb.BatchOrchestrator(
        items_dir=str(tmp_path),
        phase_runner=lambda st, ph, idir: ran.append(ph) or {"outputs": {}},
        queue_path=str(tmp_path / "queue.json"),
    )
    orch.square_image_count = lambda idir: None  # rely on label.json image_ids

    orch._advance_item(state)

    assert "phase_4" in ran
    assert state.phases["phase_4"].status == ist.PhaseStatus.COMPLETED


def test_image_gate_does_not_run_for_non_publish_phases(tmp_path):
    """The image gate only guards PUBLISH_PHASES; a non-publish runnable phase
    is never image-gated. (phase_0 runs first with no image at all.)"""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
    import process_batch as pb

    sku = "RG-3304"
    item_dir = tmp_path / sku
    item_dir.mkdir()
    _write_label(item_dir, {})  # no square, no images

    state = ist.ItemState(sku=sku, items_dir=str(tmp_path))
    state.save()

    ran = []

    def runner(st, phase, idir):
        ran.append(phase)
        # Stop after phase_0 so we don't reach a publish phase.
        return {"blocked": True, "question_text": "stop here"} if phase != "phase_0" \
            else {"outputs": {}}

    image_gate_calls = []
    orch = pb.BatchOrchestrator(items_dir=str(tmp_path), phase_runner=runner,
                               queue_path=str(tmp_path / "queue.json"))
    orig_gate = orch.image_gate
    orch.image_gate = lambda idir: image_gate_calls.append(idir) or orig_gate(idir)

    orch._advance_item(state)

    assert "phase_0" in ran            # non-publish phase ran un-gated
    assert image_gate_calls == []      # image gate never consulted for phase_0
