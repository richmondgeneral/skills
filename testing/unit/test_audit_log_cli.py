"""Tests for audit_log.py CLI subcommands."""
import json
import subprocess
import sys
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[2] / "rg-full-auto" / "scripts" / "audit_log.py"


def _seed(log_dir: Path):
    """Write a few records to the streams under log_dir."""
    from audit_log import AuditLog
    al = AuditLog(log_dir=str(log_dir))
    did = al.log_decision(
        sku="RG-0099", phase="phase_1", decision_type="price",
        choice=18.50, confidence=0.78,
        inputs_considered={}, alternatives_seen=[], rationale="t",
    )
    al.log_correction(
        sku="RG-0099", decision_id=did, decision_type="price",
        agent_choice=18.50, corrected_to=22.00,
        correction_source="manual", reason="underpriced", reviewer="scottybe",
    )
    al.log_review_event(sku="RG-0099", event="review_started")
    al.log_review_event(
        sku="RG-0099", event="review_completed",
        duration_s=324, corrections_applied=1, outcome="accepted_with_corrections",
    )


def test_cli_report_by_sku(tmp_path, capsys):
    """audit_log.py report --sku RG-0099 prints decisions for that SKU."""
    _seed(tmp_path)
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "report", "--sku", "RG-0099", "--log-dir", str(tmp_path)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "RG-0099" in result.stdout
    assert "phase_1" in result.stdout
    assert "18.5" in result.stdout


def test_cli_review_stats(tmp_path):
    """review-stats prints the per-SKU review duration + outcome."""
    _seed(tmp_path)
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "review-stats", "--log-dir", str(tmp_path)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "RG-0099" in result.stdout
    assert "324" in result.stdout
    assert "accepted_with_corrections" in result.stdout
