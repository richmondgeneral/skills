"""Tests for v6.0 audit-log writer."""
import pytest
import json
from pathlib import Path
from audit_log import AuditLog


def test_log_decision_appends_jsonl(tmp_path):
    """Logging a decision appends one JSONL line."""
    log_dir = tmp_path
    al = AuditLog(log_dir=str(log_dir))
    al.log_decision(
        sku="RG-0099",
        phase="phase_1",
        decision_type="price",
        choice=18.50,
        confidence=0.78,
        inputs_considered={"era": "1979"},
        alternatives_seen=[],
        rationale="midpoint of comps",
    )
    decisions_file = log_dir / "decisions.jsonl"
    assert decisions_file.exists()
    lines = decisions_file.read_text().strip().split("\n")
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["sku"] == "RG-0099"
    assert record["choice"] == 18.50
    assert record["confidence"] == 0.78


def test_log_correction_includes_diff(tmp_path):
    """Logging a correction captures agent_choice vs corrected_to."""
    al = AuditLog(log_dir=str(tmp_path))
    al.log_correction(
        sku="RG-0099",
        decision_id="dec-001",
        decision_type="price",
        agent_choice=18.50,
        corrected_to=22.00,
        correction_source="manual",
        reason="underpriced for the condition",
        reviewer="scottybe",
    )
    record = json.loads((tmp_path / "corrections.jsonl").read_text().strip())
    assert record["agent_choice"] == 18.50
    assert record["corrected_to"] == 22.00
    assert record["correction_source"] == "manual"


def test_log_review_event(tmp_path):
    """review_log captures start + end events with duration."""
    al = AuditLog(log_dir=str(tmp_path))
    al.log_review_event(sku="RG-0099", event="review_started")
    al.log_review_event(
        sku="RG-0099",
        event="review_completed",
        duration_s=324,
        corrections_applied=2,
        outcome="accepted_with_corrections",
    )
    lines = (tmp_path / "review_log.jsonl").read_text().strip().split("\n")
    assert len(lines) == 2
    end = json.loads(lines[1])
    assert end["duration_s"] == 324
    assert end["outcome"] == "accepted_with_corrections"


def test_concurrent_appends_dont_corrupt(tmp_path):
    """Multiple appends in quick succession produce valid JSONL."""
    al = AuditLog(log_dir=str(tmp_path))
    for i in range(20):
        al.log_decision(
            sku=f"RG-{i:04d}",
            phase="phase_1",
            decision_type="price",
            choice=10.0 + i,
            confidence=0.5,
            inputs_considered={},
            alternatives_seen=[],
            rationale="test",
        )
    lines = (tmp_path / "decisions.jsonl").read_text().strip().split("\n")
    assert len(lines) == 20
    # Every line must parse as valid JSON.
    for line in lines:
        json.loads(line)


def test_audit_log_init_does_not_create_log_dir(tmp_path):
    """AuditLog construction does NOT create the log_dir as a side effect.
    The directory is created lazily on first write."""
    nonexistent = tmp_path / "doesnt-exist-yet"
    assert not nonexistent.exists()
    al = AuditLog(log_dir=str(nonexistent))
    # Construction alone must not create the directory.
    assert not nonexistent.exists()
    # First write should create it.
    al.log_review_event(sku="RG-0001", event="review_started")
    assert nonexistent.exists()


def test_log_correction_returns_id(tmp_path):
    """log_correction returns a correction_id for chained traceability."""
    al = AuditLog(log_dir=str(tmp_path))
    cid = al.log_correction(
        sku="RG-0099",
        decision_id="dec-001",
        decision_type="price",
        agent_choice=18.50,
        corrected_to=22.00,
        correction_source="manual",
        reason="underpriced",
        reviewer="scottybe",
    )
    assert cid.startswith("cor-")
    assert len(cid) == 12  # "cor-" + 8 hex


def test_iter_records_yields_decoded_jsonl(tmp_path):
    """iter_records yields one dict per JSONL line, lazily."""
    al = AuditLog(log_dir=str(tmp_path))
    for i in range(3):
        al.log_decision(
            sku=f"RG-{i:04d}",
            phase="phase_1",
            decision_type="price",
            choice=float(10 + i),
            confidence=0.5,
            inputs_considered={},
            alternatives_seen=[],
            rationale="t",
        )
    records = list(al.iter_records("decisions"))
    assert len(records) == 3
    assert records[0]["sku"] == "RG-0000"
    assert records[2]["choice"] == 12.0


def test_iter_records_empty_file(tmp_path):
    """iter_records on a non-existent stream returns an empty iterator."""
    al = AuditLog(log_dir=str(tmp_path / "empty"))
    records = list(al.iter_records("decisions"))
    assert records == []


def test_iter_records_invalid_stream_raises(tmp_path):
    """iter_records rejects unknown stream names."""
    al = AuditLog(log_dir=str(tmp_path))
    with pytest.raises(ValueError, match="Unknown stream"):
        list(al.iter_records("not_a_stream"))
