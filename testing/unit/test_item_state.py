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
