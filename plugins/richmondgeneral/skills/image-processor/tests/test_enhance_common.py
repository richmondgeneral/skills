"""Unit tests for enhance_common.py — the torch-free shared helpers used by
upres.py / sharpen.py / enhance.py. These run in the plugin's 3.14 env (no torch)."""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import enhance_common as ec


def test_pick_scale_needs_2x():
    assert ec.pick_scale(896, 1500) == 2          # 896*2=1792 >= 1500


def test_pick_scale_needs_4x():
    assert ec.pick_scale(896, 3000) == 4          # 2x=1792 < 3000, 4x=3584 ok


def test_pick_scale_already_big():
    assert ec.pick_scale(2000, 1500) == 1         # no upscale needed


def test_resolve_source_explicit(tmp_path):
    (tmp_path / "front.png").write_bytes(b"x")
    assert ec.resolve_source(str(tmp_path), "front.png") == str(tmp_path / "front.png")


def test_resolve_source_hero_glob(tmp_path):
    (tmp_path / "hero.png").write_bytes(b"x")
    assert Path(ec.resolve_source(str(tmp_path), None)).name == "hero.png"


def test_resolve_source_missing(tmp_path):
    try:
        ec.resolve_source(str(tmp_path), None)
        assert False, "expected FileNotFoundError"
    except FileNotFoundError:
        pass


def test_resolve_out_default_suffix(tmp_path):
    src = tmp_path / "hero.png"
    src.write_bytes(b"x")
    out = ec.resolve_out(str(src), None, suffix="upres")
    assert Path(out).name == "hero.upres.png"


def test_resolve_out_default_never_equals_source(tmp_path):
    src = tmp_path / "hero.png"
    src.write_bytes(b"x")
    out = ec.resolve_out(str(src), None, suffix="upres")
    assert Path(out) != src                       # never silently overwrite source


def test_resolve_out_explicit_overwrite_allowed(tmp_path):
    src = tmp_path / "hero.png"
    src.write_bytes(b"x")
    out = ec.resolve_out(str(src), "hero.png", suffix="upres", item_dir=str(tmp_path))
    assert Path(out) == src                        # explicit --out may overwrite


def test_append_pipeline_creates_list(tmp_path):
    (tmp_path / "label.json").write_text(json.dumps({"sku": "RG-9999"}))
    ec.append_pipeline(str(tmp_path), {"tool": "upres.py", "model": "x4plus"})
    d = json.loads((tmp_path / "label.json").read_text())
    assert isinstance(d["image_pipeline"], list)
    assert d["image_pipeline"][0]["tool"] == "upres.py"
    assert d["image_pipeline"][0]["non_generative"] is True       # default stamped
    assert "timestamp" in d["image_pipeline"][0]


def test_append_pipeline_appends(tmp_path):
    (tmp_path / "label.json").write_text(json.dumps({"image_pipeline": [{"tool": "a"}]}))
    ec.append_pipeline(str(tmp_path), {"tool": "b"})
    d = json.loads((tmp_path / "label.json").read_text())
    assert [e["tool"] for e in d["image_pipeline"]] == ["a", "b"]


def test_append_pipeline_no_label_is_noop(tmp_path):
    ec.append_pipeline(str(tmp_path), {"tool": "x"})   # no label.json present
    assert not (tmp_path / "label.json").exists()
