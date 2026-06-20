"""End-to-end autonomous flow with mock phase runner."""
import json
from pathlib import Path

import pytest

from process_batch import BatchOrchestrator
from item_state import ItemState, ItemStatus, PhaseStatus
from audit_log import AuditLog


FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "sample-photo.jpeg"


def test_autonomous_e2e_one_item(tmp_path):
    items_dir = tmp_path / "items"
    queue_path = tmp_path / "queue.json"
    audit_dir = tmp_path / "audit"

    # Phase runner that simulates every phase succeeding.
    decisions_made = []

    def fake_runner(state, phase, item_dir):
        # Log a decision for phases 1, 2, 5 (the ones with real choices)
        if phase == "phase_1":
            state.log_decision(
                phase=phase, decision_type="price",
                choice=18.50, confidence=0.78, rationale="midpoint comps",
            )
            decisions_made.append("price")
        if phase == "phase_2":
            state.log_decision(
                phase=phase, decision_type="type_category",
                choice="CLZCJ62H4TTHDQ3ZBYMZQASQ", confidence=0.95,
                rationale="visible binding suggests Books & Paper",
            )
            decisions_made.append("type_category")
        return {"outputs": {"phase": phase, "result": "mocked-success"}}

    orch = BatchOrchestrator(
        items_dir=str(items_dir),
        queue_path=str(queue_path),
        phase_runner=fake_runner,
        next_sku=lambda: "RG-9999",
        audit_log=AuditLog(log_dir=str(audit_dir)),
        hero_gate=lambda item_dir: (True, "test-bypass"),  # publish gate tested separately
    )

    states = orch.ingest_photos([str(FIXTURE)])
    assert len(states) == 1
    assert states[0].sku == "RG-9999"

    summary = orch.process_all()
    assert summary["completed"] == 1
    assert summary["blocked"] == 0
    assert summary["failed"] == 0

    final = ItemState.load("RG-9999", items_dir=str(items_dir))
    assert final.status == ItemStatus.COMPLETED
    assert all(p.status == PhaseStatus.COMPLETED for p in final.phases.values())
    assert len(final.decisions) == 2
    assert "price" in decisions_made
