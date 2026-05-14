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
