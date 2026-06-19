"""Tests for set_channel_status.py CLI write-path (atomic write + oversize recompute)."""
import json

from set_channel_status import apply_set_channel_status


def _write_label(item_dir, label):
    item_dir.mkdir(parents=True, exist_ok=True)
    (item_dir / "label.json").write_text(json.dumps(label), encoding="utf-8")


def test_writes_status_ids_and_recomputes_oversize(tmp_path):
    item_dir = tmp_path / "RG-1"
    _write_label(item_dir, {
        "sku": "RG-1",
        "measurements_in": {"l": 30, "w": 10, "h": 5},   # 30 > 24 => oversize
        "channels": {"square": {"status": "pending"}},
    })
    out = apply_set_channel_status(
        item_dir, "square", "listed", object_id="ABC", buy_link="sq.link/x")

    on_disk = json.loads((item_dir / "label.json").read_text(encoding="utf-8"))
    assert on_disk == out
    assert on_disk["channels"]["square"] == {
        "status": "listed", "object_id": "ABC", "buy_link": "sq.link/x"}
    assert on_disk["oversize"] is True


def test_recomputes_oversize_false_for_small_box(tmp_path):
    item_dir = tmp_path / "RG-2"
    _write_label(item_dir, {
        "sku": "RG-2",
        "measurements_in": {"l": 10, "w": 8, "h": 6},
        "channels": {"square": {"status": "sold"}},
    })
    out = apply_set_channel_status(item_dir, "square", "listed")

    assert out["channels"]["square"]["status"] == "sold"   # sold stays sticky through the CLI
    assert out["oversize"] is False
