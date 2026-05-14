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


def test_orchestrator_resume_reopens_only_phases_with_all_answered_questions(tmp_path):
    """resume() reopens BLOCKED phases per-phase based on answered questions.

    Setup an item with two BLOCKED phases (phase_0 and phase_1), answer only
    phase_0's question. Phase_0 should reopen; phase_1 should stay blocked.
    """
    items_dir = tmp_path / "items"
    items_dir.mkdir()
    sku = "RG-0099"
    (items_dir / sku).mkdir()

    state = ItemState(sku=sku, items_dir=str(items_dir),
                      source_image=str(tmp_path / "src.jpg"))
    (tmp_path / "src.jpg").write_bytes(b"x")
    # Block phase_0 and phase_1 with distinct questions
    state.start_phase("phase_0")
    state.block_phase("phase_0", PendingQuestion(
        question_id="q-0", phase="phase_0", question="P0?",
    ))
    # We must allow phase_1 to be next_runnable; since phase_0 is BLOCKED,
    # phase_1 (which depends on phase_0) won't be runnable. Use a parallel
    # approach: block phase_1 directly by manipulating its status.
    state.phases["phase_1"].status = PhaseStatus.BLOCKED
    state.questions.append({
        "question_id": "q-1", "phase": "phase_1", "question": "P1?", "answer": None,
    })
    state._recalculate_status()
    # Answer only phase_0's question
    state.answer_question("q-0", "yes")
    state.save()

    from onboarding_queue import OnboardingQueue, QueueEntry
    queue = OnboardingQueue(queue_path=str(tmp_path / "queue.json"))
    queue.upsert(QueueEntry.from_item_state(state))
    queue.save()

    # Phase runner that always blocks again (so we can observe which phase reopened)
    runs = []
    def blocking_runner(state, phase, item_dir):
        runs.append(phase)
        return {"blocked": True, "question": PendingQuestion(
            question_id=f"q-{phase}-redo", phase=phase, question="again?",
        )}

    orch = BatchOrchestrator(
        items_dir=str(items_dir),
        queue_path=str(tmp_path / "queue.json"),
        phase_runner=blocking_runner,
    )
    orch.resume()
    # Only phase_0 should have been re-run (phase_1's question is still unanswered)
    assert "phase_0" in runs
    assert "phase_1" not in runs


def test_orchestrator_runner_exception_marks_phase_failed(tmp_path):
    """When the phase_runner raises, the phase is marked FAILED with error message."""
    items_dir = tmp_path / "items"
    items_dir.mkdir()
    sku = "RG-0099"
    (items_dir / sku).mkdir()
    state = ItemState(sku=sku, items_dir=str(items_dir),
                      source_image=str(tmp_path / "src.jpg"))
    (tmp_path / "src.jpg").write_bytes(b"x")
    state.save()

    def raising_runner(state, phase, item_dir):
        raise RuntimeError("simulated remove.bg outage")

    orch = BatchOrchestrator(
        items_dir=str(items_dir),
        queue_path=str(tmp_path / "queue.json"),
        phase_runner=raising_runner,
    )
    result = orch._advance_item(state)
    # phase_0 should be failed; item status should be FAILED.
    assert state.phases["phase_0"].status == PhaseStatus.FAILED
    assert "RuntimeError" in state.phases["phase_0"].error
    assert "remove.bg outage" in state.phases["phase_0"].error
    assert state.status == ItemStatus.FAILED


def test_orchestrator_runner_unknown_shape_marks_phase_failed(tmp_path):
    """When the phase_runner returns an unrecognized shape (e.g., {}), the phase fails."""
    items_dir = tmp_path / "items"
    items_dir.mkdir()
    sku = "RG-0099"
    (items_dir / sku).mkdir()
    state = ItemState(sku=sku, items_dir=str(items_dir),
                      source_image=str(tmp_path / "src.jpg"))
    (tmp_path / "src.jpg").write_bytes(b"x")
    state.save()

    def malformed_runner(state, phase, item_dir):
        return {}  # missing all of blocked/skipped/outputs

    orch = BatchOrchestrator(
        items_dir=str(items_dir),
        queue_path=str(tmp_path / "queue.json"),
        phase_runner=malformed_runner,
    )
    result = orch._advance_item(state)
    # Every phase should fail with the unrecognized-result message
    assert state.phases["phase_0"].status == PhaseStatus.FAILED
    assert "unrecognized result" in state.phases["phase_0"].error


def test_phase_0_invokes_remove_background(tmp_path, monkeypatch):
    """The real phase_runner for phase_0 calls remove_background and stores the output path."""
    photo = tmp_path / "src.jpg"
    photo.write_bytes(b"x")
    items_dir = tmp_path / "items"
    items_dir.mkdir()
    sku = "RG-9999"
    (items_dir / sku).mkdir()

    state = ItemState(sku=sku, items_dir=str(items_dir), source_image=str(photo))
    state.save()

    # Mock the import within process_batch so no API key / network needed
    calls = []
    def fake_remove_bg(input_path, output_path, api_key):
        calls.append({"in": input_path, "out": output_path, "key": api_key})
        Path(output_path).write_bytes(b"hero")

    import process_batch as pb
    monkeypatch.setattr(pb, "_remove_background", fake_remove_bg)
    monkeypatch.setenv("REMOVEBG_API_KEY", "test-key-not-real")

    orch = pb.BatchOrchestrator(
        items_dir=str(items_dir),
        queue_path=str(tmp_path / "q.json"),
    )
    state.start_phase("phase_0")
    result = orch._phase_0_image(state, str(items_dir / sku))
    assert "outputs" in result
    assert "hero_path" in result["outputs"]
    assert (items_dir / sku / "hero.png").exists()
    assert len(calls) == 1
    assert calls[0]["key"] == "test-key-not-real"


def test_phase_0_blocks_when_source_image_missing(tmp_path, monkeypatch):
    """If state.source_image doesn't exist on disk, phase_0 returns blocked."""
    items_dir = tmp_path / "items"
    items_dir.mkdir()
    sku = "RG-9999"
    (items_dir / sku).mkdir()
    state = ItemState(sku=sku, items_dir=str(items_dir),
                      source_image="/does/not/exist.jpg")
    import process_batch as pb
    orch = pb.BatchOrchestrator(items_dir=str(items_dir),
                                queue_path=str(tmp_path / "q.json"))
    result = orch._phase_0_image(state, str(items_dir / sku))
    assert result.get("blocked") is True
    assert isinstance(result.get("question"), PendingQuestion)


def test_phase_0_blocks_when_remove_background_unavailable(tmp_path, monkeypatch):
    """If the remove_background module didn't import, phase_0 blocks with a clear question."""
    items_dir = tmp_path / "items"
    items_dir.mkdir()
    sku = "RG-9999"
    (items_dir / sku).mkdir()
    photo = tmp_path / "src.jpg"
    photo.write_bytes(b"x")
    state = ItemState(sku=sku, items_dir=str(items_dir), source_image=str(photo))

    import process_batch as pb
    monkeypatch.setattr(pb, "_remove_background", None)

    orch = pb.BatchOrchestrator(items_dir=str(items_dir),
                                queue_path=str(tmp_path / "q.json"))
    result = orch._phase_0_image(state, str(items_dir / sku))
    assert result.get("blocked") is True


def test_phase_1_records_appraisal_decisions(tmp_path):
    """phase_1 records the appraisal decisions (price, condition, shippable) as audit entries."""
    items_dir = tmp_path / "items"; items_dir.mkdir()
    (items_dir / "RG-9999").mkdir()
    state = ItemState(sku="RG-9999", items_dir=str(items_dir))
    state.start_phase("phase_0"); state.complete_phase("phase_0", outputs={"hero_path": "/x"})
    state.start_phase("phase_1")
    # The caller (Claude) passes appraisal data via state.phases["phase_1"].outputs
    state.phases["phase_1"].outputs.update({
        "title": "1979 Manual",
        "era": "1979",
        "condition": "Very Good",
        "price": 18.50,
        "shippable": True,
    })

    import process_batch as pb
    orch = pb.BatchOrchestrator(items_dir=str(items_dir),
                                queue_path=str(tmp_path / "q.json"))
    result = orch._phase_1_appraisal(state, str(items_dir / "RG-9999"))
    assert "outputs" in result
    assert len(state.decisions) >= 3  # price, condition, shippable at minimum
    types = {d["type"] for d in state.decisions}
    assert "price" in types
    assert "condition" in types


def test_phase_2_logs_catalog_plan_when_sku_free(tmp_path, monkeypatch):
    """phase_2 verifies the SKU isn't already in Square, then logs the catalog plan."""
    items_dir = tmp_path / "items"; items_dir.mkdir()
    (items_dir / "RG-9999").mkdir()
    state = ItemState(sku="RG-9999", items_dir=str(items_dir))
    state.phases["phase_1"].outputs.update({"title": "T", "price": 10.0})

    import process_batch as pb
    # Monkeypatch the cache lookup helper
    monkeypatch.setattr(pb, "_check_sku_in_square_cache", lambda sku: None)

    orch = pb.BatchOrchestrator(items_dir=str(items_dir),
                                queue_path=str(tmp_path / "q.json"))
    result = orch._phase_2_catalog(state, str(items_dir / "RG-9999"))
    assert "outputs" in result
    assert result["outputs"].get("ready_for_create") is True
    # Should have logged the catalog plan
    plan_types = {d["type"] for d in state.decisions}
    assert "catalog_plan" in plan_types


def test_phase_2_blocks_on_sku_collision(tmp_path, monkeypatch):
    """If the SKU already exists in Square cache, phase_2 returns blocked."""
    items_dir = tmp_path / "items"; items_dir.mkdir()
    (items_dir / "RG-9999").mkdir()
    state = ItemState(sku="RG-9999", items_dir=str(items_dir))

    import process_batch as pb
    monkeypatch.setattr(pb, "_check_sku_in_square_cache", lambda sku: "EXISTING_ITEM_ID")

    orch = pb.BatchOrchestrator(items_dir=str(items_dir),
                                queue_path=str(tmp_path / "q.json"))
    result = orch._phase_2_catalog(state, str(items_dir / "RG-9999"))
    assert result.get("blocked") is True
    assert isinstance(result.get("question"), PendingQuestion)
    assert "RG-9999" in result["question"].question
    # Question should offer overwrite/skip/renumber options
    assert "overwrite" in result["question"].options


def test_phase_3_records_inventory_decision(tmp_path):
    """phase_3 logs an inventory=1 decision and returns ready."""
    items_dir = tmp_path / "items"; items_dir.mkdir()
    (items_dir / "RG-9999").mkdir()
    state = ItemState(sku="RG-9999", items_dir=str(items_dir))

    import process_batch as pb
    orch = pb.BatchOrchestrator(items_dir=str(items_dir),
                                queue_path=str(tmp_path / "q.json"))
    result = orch._phase_3_inventory(state, str(items_dir / "RG-9999"))
    assert result["outputs"]["quantity"] == 1
    types = {d["type"] for d in state.decisions}
    assert "inventory" in types


def test_phase_4_image_upload_logs_decision(tmp_path):
    """phase_4 logs an image_upload decision and returns ready."""
    items_dir = tmp_path / "items"; items_dir.mkdir()
    (items_dir / "RG-9999").mkdir()
    state = ItemState(sku="RG-9999", items_dir=str(items_dir))
    state.phases["phase_4"].outputs.update({"item_id": "ITEM_ID", "hero_path": "/h.png"})

    import process_batch as pb
    orch = pb.BatchOrchestrator(items_dir=str(items_dir),
                                queue_path=str(tmp_path / "q.json"))
    result = orch._phase_4_image_upload(state, str(items_dir / "RG-9999"))
    assert result["outputs"]["uploaded"] is True
    assert any(d["type"] == "image_upload" for d in state.decisions)


def test_phase_5_payment_link_records_decision(tmp_path):
    """phase_5 logs a payment_link decision capturing shippable from phase_1."""
    items_dir = tmp_path / "items"; items_dir.mkdir()
    (items_dir / "RG-9999").mkdir()
    state = ItemState(sku="RG-9999", items_dir=str(items_dir))
    state.phases["phase_1"].outputs["shippable"] = False

    import process_batch as pb
    orch = pb.BatchOrchestrator(items_dir=str(items_dir),
                                queue_path=str(tmp_path / "q.json"))
    result = orch._phase_5_payment_link(state, str(items_dir / "RG-9999"))
    assert result["outputs"]["payment_link_created"] is True
    decisions = [d for d in state.decisions if d["type"] == "payment_link"]
    assert len(decisions) == 1
    assert decisions[0]["choice"]["shippable"] is False


def test_phase_6_label_queues(tmp_path):
    items_dir = tmp_path / "items"; items_dir.mkdir()
    (items_dir / "RG-9999").mkdir()
    state = ItemState(sku="RG-9999", items_dir=str(items_dir))

    import process_batch as pb
    orch = pb.BatchOrchestrator(items_dir=str(items_dir),
                                queue_path=str(tmp_path / "q.json"))
    result = orch._phase_6_label(state, str(items_dir / "RG-9999"))
    assert result["outputs"]["label_queued"] is True
    assert any(d["type"] == "label" for d in state.decisions)


def test_phase_7_publishing_records_decision(tmp_path):
    items_dir = tmp_path / "items"; items_dir.mkdir()
    (items_dir / "RG-9999").mkdir()
    state = ItemState(sku="RG-9999", items_dir=str(items_dir))

    import process_batch as pb
    orch = pb.BatchOrchestrator(items_dir=str(items_dir),
                                queue_path=str(tmp_path / "q.json"))
    result = orch._phase_7_publishing(state, str(items_dir / "RG-9999"))
    assert result["outputs"]["page_drafted"] is True
    assert any(d["type"] == "publishing" for d in state.decisions)


def test_phase_8_whatnot_can_skip(tmp_path):
    """When sell_on_whatnot is False, phase_8 returns skipped."""
    items_dir = tmp_path / "items"; items_dir.mkdir()
    (items_dir / "RG-9999").mkdir()
    state = ItemState(sku="RG-9999", items_dir=str(items_dir))
    state.phases["phase_8"].outputs["sell_on_whatnot"] = False

    import process_batch as pb
    orch = pb.BatchOrchestrator(items_dir=str(items_dir),
                                queue_path=str(tmp_path / "q.json"))
    result = orch._phase_8_whatnot(state, str(items_dir / "RG-9999"))
    assert result.get("skipped") is True


def test_phase_8_whatnot_records_when_selling(tmp_path):
    """When sell_on_whatnot is True (or absent → default True), phase_8 logs and returns ready."""
    items_dir = tmp_path / "items"; items_dir.mkdir()
    (items_dir / "RG-9999").mkdir()
    state = ItemState(sku="RG-9999", items_dir=str(items_dir))
    # Leave sell_on_whatnot unset — implementation should treat that as default

    import process_batch as pb
    orch = pb.BatchOrchestrator(items_dir=str(items_dir),
                                queue_path=str(tmp_path / "q.json"))
    result = orch._phase_8_whatnot(state, str(items_dir / "RG-9999"))
    assert result["outputs"]["whatnot_csv_appended"] is True
    assert any(d["type"] == "whatnot" for d in state.decisions)


def test_phase_9_photos_archive_is_mac_only(tmp_path, monkeypatch):
    """On non-darwin platforms, phase_9 returns skipped with Mac-only reason."""
    items_dir = tmp_path / "items"; items_dir.mkdir()
    (items_dir / "RG-9999").mkdir()
    state = ItemState(sku="RG-9999", items_dir=str(items_dir))

    import process_batch as pb
    monkeypatch.setattr(pb.sys, "platform", "linux")

    orch = pb.BatchOrchestrator(items_dir=str(items_dir),
                                queue_path=str(tmp_path / "q.json"))
    result = orch._phase_9_photos_archive(state, str(items_dir / "RG-9999"))
    assert result.get("skipped") is True
    assert "Mac only" in result.get("reason", "")


def test_phase_9_photos_archive_runs_on_darwin(tmp_path, monkeypatch):
    """On darwin, phase_9 logs and returns ready."""
    items_dir = tmp_path / "items"; items_dir.mkdir()
    (items_dir / "RG-9999").mkdir()
    state = ItemState(sku="RG-9999", items_dir=str(items_dir))

    import process_batch as pb
    monkeypatch.setattr(pb.sys, "platform", "darwin")

    orch = pb.BatchOrchestrator(items_dir=str(items_dir),
                                queue_path=str(tmp_path / "q.json"))
    result = orch._phase_9_photos_archive(state, str(items_dir / "RG-9999"))
    assert result["outputs"]["photos_archived"] is True
    assert any(d["type"] == "photos_archive" for d in state.decisions)
