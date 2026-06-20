"""Tests for intake_cleanup — Live Photo sidecar pruning + listed-item scratch sweep.

Root cause these address (2026-06-19): iCloud-offloaded originals get materialized
by a manual "export unmodified originals" step that drags in each Live Photo's .mov
sidecar (~1G/intake session), and nothing ever sweeps intake scratch after an item
is done. prune_live_photo_sidecars stops the bloat at the source (always safe — it
only drops a .mov that has a still twin); sweep_intake_scratch is the definition-of-
done guardrail (only fires for terminal-state items, so it never nukes scratch an
item with open photo follow-ups still needs).
"""
import json
import os

import intake_cleanup


def _touch(path, content=b"x"):
    with open(path, "wb") as f:
        f.write(content)


# ---------- Fix A: prune_live_photo_sidecars ----------

def test_prune_removes_mov_with_still_twin(tmp_path):
    _touch(tmp_path / "IMG_1.jpeg")
    _touch(tmp_path / "IMG_1.mov")
    removed = intake_cleanup.prune_live_photo_sidecars(str(tmp_path))
    assert [os.path.basename(p) for p in removed] == ["IMG_1.mov"]
    assert (tmp_path / "IMG_1.jpeg").exists()        # still image kept
    assert not (tmp_path / "IMG_1.mov").exists()     # sidecar dropped


def test_prune_keeps_standalone_video(tmp_path):
    _touch(tmp_path / "CLIP.mov")                    # no still twin → real video
    removed = intake_cleanup.prune_live_photo_sidecars(str(tmp_path))
    assert removed == []
    assert (tmp_path / "CLIP.mov").exists()


def test_prune_twin_match_is_case_insensitive(tmp_path):
    _touch(tmp_path / "IMG_2.JPG")                   # uppercase still ext
    _touch(tmp_path / "IMG_2.MOV")                   # uppercase mov ext
    removed = intake_cleanup.prune_live_photo_sidecars(str(tmp_path))
    assert [os.path.basename(p) for p in removed] == ["IMG_2.MOV"]
    assert not (tmp_path / "IMG_2.MOV").exists()
    assert (tmp_path / "IMG_2.JPG").exists()


def test_prune_dry_run_deletes_nothing(tmp_path):
    _touch(tmp_path / "IMG_3.heic")
    _touch(tmp_path / "IMG_3.mov")
    removed = intake_cleanup.prune_live_photo_sidecars(str(tmp_path), dry_run=True)
    assert [os.path.basename(p) for p in removed] == ["IMG_3.mov"]
    assert (tmp_path / "IMG_3.mov").exists()         # dry-run: nothing deleted


def test_prune_missing_dir_returns_empty(tmp_path):
    assert intake_cleanup.prune_live_photo_sidecars(str(tmp_path / "nope")) == []


# ---------- Fix B: sweep_intake_scratch ----------

def _make_item(items_dir, sku, state):
    d = items_dir / sku
    d.mkdir(parents=True)
    (d / "label.json").write_text(json.dumps({"sku": sku, "state": state}))
    return d


def test_sweep_removes_scratch_when_state_terminal(tmp_path):
    items = tmp_path / "items"
    _make_item(items, "RG-0028", "Sold")
    staging = tmp_path / "rg-pending" / "RG-0028"
    staging.mkdir(parents=True)
    _touch(staging / "IMG.jpeg")
    res = intake_cleanup.sweep_intake_scratch("RG-0028", str(items), dry_run=False)
    assert res["eligible"] is True
    assert os.path.normpath(str(staging)) in [os.path.normpath(p) for p in res["removed"]]
    assert not staging.exists()


def test_sweep_skips_when_state_not_terminal(tmp_path):
    items = tmp_path / "items"
    _make_item(items, "RG-0030", "Listed")           # listed but photos may be pending
    staging = tmp_path / "rg-pending" / "RG-0030"
    staging.mkdir(parents=True)
    res = intake_cleanup.sweep_intake_scratch("RG-0030", str(items), dry_run=False)
    assert res["eligible"] is False
    assert "Listed" in res["reason"]
    assert res["removed"] == []
    assert staging.exists()                          # preserved — not terminal


def test_sweep_dry_run_reports_without_deleting(tmp_path):
    items = tmp_path / "items"
    _make_item(items, "RG-0029", "Archived")
    staging = tmp_path / "rg-pending" / "RG-0029"
    staging.mkdir(parents=True)
    res = intake_cleanup.sweep_intake_scratch("RG-0029", str(items), dry_run=True)
    assert res["eligible"] is True
    assert res["removed"] == []                      # dry-run removes nothing
    assert os.path.normpath(str(staging)) in [os.path.normpath(p) for p in res["targets"]]
    assert staging.exists()


def test_sweep_skips_when_no_label(tmp_path):
    items = tmp_path / "items"
    (items / "RG-0099").mkdir(parents=True)          # no label.json → can't confirm done
    staging = tmp_path / "rg-pending" / "RG-0099"
    staging.mkdir(parents=True)
    res = intake_cleanup.sweep_intake_scratch("RG-0099", str(items), dry_run=False)
    assert res["eligible"] is False
    assert res["removed"] == []
    assert staging.exists()


def test_sweep_includes_extra_scratch_dirs(tmp_path):
    items = tmp_path / "items"
    _make_item(items, "RG-0028", "Sold")
    staging = tmp_path / "rg-pending" / "RG-0028"
    staging.mkdir(parents=True)
    legacy = tmp_path / "ops" / "_intake_dishes"
    legacy.mkdir(parents=True)
    res = intake_cleanup.sweep_intake_scratch(
        "RG-0028", str(items), extra=[str(legacy)], dry_run=False)
    removed_norm = [os.path.normpath(p) for p in res["removed"]]
    assert os.path.normpath(str(staging)) in removed_norm
    assert os.path.normpath(str(legacy)) in removed_norm
    assert not staging.exists() and not legacy.exists()
