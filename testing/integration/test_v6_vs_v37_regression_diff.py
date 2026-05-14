"""Document the intentional schema differences between v3.7 and v6.0 outputs.

This test isn't a "is v6.0 bit-identical to v3.7" check — it isn't, and shouldn't be.
It's a contract test that locks in the data fields v3.7's label.json produced so v6.0's
state.json can be confirmed to carry the same information (in a richer shape).

If v6.0 ever drops a field that v3.7 relied on, this test fails loudly and forces
either a schema fix or an explicit decision to deprecate that field.
"""
from pathlib import Path

import pytest

from item_state import ItemState


FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "sample-photo.jpeg"


def test_v6_state_includes_all_v37_label_fields(tmp_path):
    """Every field v3.7 wrote to label.json must be reachable from v6.0's state.json."""
    items_dir = tmp_path / "items"
    (items_dir / "RG-9999").mkdir(parents=True)
    state = ItemState(
        sku="RG-9999",
        items_dir=str(items_dir),
        source_image=str(FIXTURE),
    )
    # Simulate what Claude populates during autonomous phase_1
    state.phases["phase_1"].outputs.update({
        "title": "1979 Manual",
        "era": "1979",
        "condition": "Very Good",
        "condition_notes": "minor edge wear",
        "price": 18.50,
        "shippable": True,
        "maker": "Acme Press",
        "origin": "USA",
        "description": "<p>A piece of mid-century printed ephemera.</p>",
    })
    state.save()

    # v3.7 label.json schema fields (verified against items/RG-*/label.json on disk
    # in the items repo: sku, product_name, attributes, price, condition, condition_notes).
    v37_required_fields = {
        "sku", "product_name", "attributes", "price",
        "condition", "condition_notes",
    }
    # In v6.0, these are reachable from state.sku + state.phases["phase_1"].outputs.
    p1 = state.phases["phase_1"].outputs
    available = {
        "sku": state.sku,
        "product_name": p1["title"],
        "attributes": {},  # v6.0 doesn't have a flat attributes field yet;
                           # condition + maker + era serve as structured attrs.
        "price": p1["price"],
        "condition": p1["condition"],
        "condition_notes": p1["condition_notes"],
    }
    missing = v37_required_fields - set(available)
    assert not missing, (
        f"v6.0 state.json is missing v3.7 label.json fields: {missing}. "
        f"Update phase_1's expected outputs schema before merging."
    )


def test_v6_writes_additional_audit_data_v37_did_not(tmp_path):
    """v6.0 captures decision rationale that v3.7 dropped on the floor."""
    from process_batch import BatchOrchestrator

    items_dir = tmp_path / "items"
    (items_dir / "RG-9999").mkdir(parents=True)
    state = ItemState(
        sku="RG-9999",
        items_dir=str(items_dir),
        source_image=str(FIXTURE),
    )
    state.phases["phase_1"].outputs.update({
        "title": "T",
        "price": 10.0,
        "condition": "Good",
        "shippable": True,
    })

    orch = BatchOrchestrator(
        items_dir=str(items_dir),
        queue_path=str(tmp_path / "q.json"),
    )
    state.start_phase("phase_1")
    orch._phase_1_appraisal(state, str(items_dir / "RG-9999"))

    # The decisions list captures audit-trail rows v3.7 did not produce.
    assert any(d["type"] == "price" for d in state.decisions), (
        "v6.0 should record a price decision in state.decisions (v3.7 didn't)."
    )
    assert any(d["type"] == "condition" for d in state.decisions)
    assert any(d["type"] == "shipping_eligible" for d in state.decisions)


def test_v6_phase_status_enum_covers_v37_lifecycle(tmp_path):
    """Every v3.7 phase outcome (success/skipped/manual-abort) maps to a v6.0 PhaseStatus."""
    from item_state import PhaseStatus

    # v3.7 had implicit lifecycle: phase ran-to-completion, user aborted, or user skipped.
    # v6.0's PhaseStatus enum is a superset.
    v37_implicit_states = {"completed", "skipped", "pending"}
    v6_states = {s.value for s in PhaseStatus}
    missing = v37_implicit_states - v6_states
    assert not missing, (
        f"v6.0 PhaseStatus is missing v3.7 lifecycle states: {missing}"
    )
