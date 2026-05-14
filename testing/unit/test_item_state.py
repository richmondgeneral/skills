"""Tests for rg-full-auto v6.0 per-item state machine."""
import pytest
from item_state import PhaseStatus, ItemStatus


def test_phase_status_values():
    """PhaseStatus enum values match design doc spec."""
    assert PhaseStatus.PENDING.value == "pending"
    assert PhaseStatus.IN_PROGRESS.value == "in_progress"
    assert PhaseStatus.COMPLETED.value == "completed"
    assert PhaseStatus.FAILED.value == "failed"
    assert PhaseStatus.BLOCKED.value == "blocked"
    assert PhaseStatus.SKIPPED.value == "skipped"


def test_item_status_values():
    """ItemStatus enum values match design doc spec."""
    assert ItemStatus.QUEUED.value == "queued"
    assert ItemStatus.PROCESSING.value == "processing"
    assert ItemStatus.BLOCKED.value == "blocked"
    assert ItemStatus.COMPLETED.value == "completed"
    assert ItemStatus.FAILED.value == "failed"


from item_state import PhaseData


def test_phase_data_default():
    """PhaseData starts in PENDING with empty outputs."""
    p = PhaseData()
    assert p.status == PhaseStatus.PENDING
    assert p.started_at is None
    assert p.completed_at is None
    assert p.outputs == {}
    assert p.error is None


def test_phase_data_to_dict():
    """PhaseData serializes to JSON-safe dict."""
    p = PhaseData(status=PhaseStatus.COMPLETED, outputs={"k": "v"})
    d = p.to_dict()
    assert d["status"] == "completed"
    assert d["outputs"] == {"k": "v"}


from item_state import ItemState
from pathlib import Path
import json


def test_item_state_new(tmp_path):
    """A new ItemState initializes empty phases + QUEUED status."""
    state = ItemState(sku="RG-0099", items_dir=str(tmp_path))
    assert state.sku == "RG-0099"
    assert state.status == ItemStatus.QUEUED
    assert state.decisions == []
    assert state.questions == []
    # Phases initialize as PENDING for the canonical 10 phases.
    assert "phase_0" in state.phases
    assert "phase_9" in state.phases
    assert state.phases["phase_0"].status == PhaseStatus.PENDING


def test_item_state_save_and_load(tmp_path):
    """ItemState round-trips through .state.json on disk."""
    state = ItemState(sku="RG-0099", items_dir=str(tmp_path))
    state.status = ItemStatus.PROCESSING
    state.phases["phase_0"].status = PhaseStatus.COMPLETED
    (tmp_path / "RG-0099").mkdir()
    state.save()
    state_file = tmp_path / "RG-0099" / ".state.json"
    assert state_file.exists()
    loaded = ItemState.load("RG-0099", items_dir=str(tmp_path))
    assert loaded.status == ItemStatus.PROCESSING
    assert loaded.phases["phase_0"].status == PhaseStatus.COMPLETED


def test_item_state_load_legacy_item_no_state(tmp_path):
    """Loading an item without .state.json returns None (legacy mode)."""
    (tmp_path / "RG-0001").mkdir()
    loaded = ItemState.load("RG-0001", items_dir=str(tmp_path))
    assert loaded is None


def test_item_state_save_is_atomic_via_tmp_rename(tmp_path):
    """save() writes via .tmp then renames; no .tmp file remains after."""
    (tmp_path / "RG-0099").mkdir()
    state = ItemState(sku="RG-0099", items_dir=str(tmp_path))
    state.save()
    final = tmp_path / "RG-0099" / ".state.json"
    tmp_artifact = tmp_path / "RG-0099" / ".state.json.tmp"
    assert final.exists()
    assert not tmp_artifact.exists()  # rename moved it, no orphan


def test_item_state_round_trip_preserves_review_block(tmp_path):
    """The review block survives save → load with all 4 keys preserved."""
    (tmp_path / "RG-0099").mkdir()
    state = ItemState(sku="RG-0099", items_dir=str(tmp_path))
    state.review["agent_finished_at"] = "2026-05-13T18:00:00+00:00"
    state.review["human_reviewed_at"] = "2026-05-13T18:05:24+00:00"
    state.review["elapsed_review_s"] = 324
    state.review["outcome"] = "accepted_with_corrections"
    state.save()
    loaded = ItemState.load("RG-0099", items_dir=str(tmp_path))
    assert loaded.review["agent_finished_at"] == "2026-05-13T18:00:00+00:00"
    assert loaded.review["human_reviewed_at"] == "2026-05-13T18:05:24+00:00"
    assert loaded.review["elapsed_review_s"] == 324
    assert loaded.review["outcome"] == "accepted_with_corrections"


def test_item_state_round_trip_preserves_decisions_and_questions(tmp_path):
    """decisions and questions lists round-trip non-empty contents."""
    (tmp_path / "RG-0099").mkdir()
    state = ItemState(sku="RG-0099", items_dir=str(tmp_path))
    state.decisions.append({"phase": "phase_1", "type": "price", "choice": 18.50})
    state.questions.append({"phase": "phase_2", "q": "is this scrimshaw real?"})
    state.save()
    loaded = ItemState.load("RG-0099", items_dir=str(tmp_path))
    assert len(loaded.decisions) == 1
    assert loaded.decisions[0]["choice"] == 18.50
    assert len(loaded.questions) == 1
    assert loaded.questions[0]["q"] == "is this scrimshaw real?"


def test_item_state_save_updates_updated_at(tmp_path):
    """save() bumps updated_at but preserves created_at."""
    import time
    (tmp_path / "RG-0099").mkdir()
    state = ItemState(sku="RG-0099", items_dir=str(tmp_path))
    original_created_at = state.created_at
    original_updated_at = state.updated_at
    time.sleep(0.01)  # ensure monotonic clock has advanced
    state.save()
    assert state.created_at == original_created_at  # preserved
    assert state.updated_at > original_updated_at   # bumped


def test_item_state_load_preserves_updated_at(tmp_path):
    """Loading a serialized item should NOT bump updated_at — only mutations should."""
    import time
    (tmp_path / "RG-0099").mkdir()
    state = ItemState(sku="RG-0099", items_dir=str(tmp_path))
    state.save()
    original_updated = state.updated_at
    time.sleep(0.01)
    loaded = ItemState.load("RG-0099", items_dir=str(tmp_path))
    assert loaded.updated_at == original_updated, \
        "load() must preserve updated_at; bumping makes the in-memory model disagree with disk"


def test_phase_dependencies_constant_exists():
    """PHASE_DEPENDENCIES maps each phase to its required predecessors."""
    from item_state import PHASE_DEPENDENCIES, PHASES
    assert set(PHASE_DEPENDENCIES.keys()) == set(PHASES)
    # phase_0 has no deps
    assert PHASE_DEPENDENCIES["phase_0"] == []
    # phase_4 (image upload) needs phase_0 (image) AND phase_2 (catalog)
    assert "phase_0" in PHASE_DEPENDENCIES["phase_4"]
    assert "phase_2" in PHASE_DEPENDENCIES["phase_4"]


def test_pending_question_defaults():
    """A new PendingQuestion has empty answer + asked_at timestamp."""
    from item_state import PendingQuestion
    q = PendingQuestion(question_id="q-001", phase="phase_1", question="What era?")
    assert q.answer is None
    assert q.is_answered() is False
    assert q.context == ""
    assert q.options == []
    assert q.asked_at != ""  # __post_init__ sets it


def test_pending_question_is_answered():
    """is_answered returns True when answer is non-empty."""
    from item_state import PendingQuestion
    q = PendingQuestion(question_id="q-001", phase="phase_1", question="?")
    assert q.is_answered() is False
    q.answer = "1979"
    assert q.is_answered() is True
    q.answer = ""
    assert q.is_answered() is False  # empty string doesn't count


def test_pending_question_round_trip(tmp_path):
    """PendingQuestion round-trips through asdict / from_dict."""
    from item_state import PendingQuestion
    from dataclasses import asdict
    q = PendingQuestion(
        question_id="q-001",
        phase="phase_1",
        question="What era?",
        context="The cover has 1979 stamped",
        options=["1970s", "1980s"],
        answer="1979",
    )
    d = asdict(q)
    assert d["answer"] == "1979"
    q2 = PendingQuestion(**d)
    assert q2.is_answered()
    assert q2.options == ["1970s", "1980s"]
