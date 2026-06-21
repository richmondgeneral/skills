"""Tests for combo.py — deterministic 1:1 marketplace combo collage."""
import json
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import combo as cb


def _img(path, color, size=(600, 600)):
    Image.new("RGB", size, color).save(path)


def _item(tmp_path, details=("detail-maker-mark", "detail-lid", "detail-bottom"),
          hero=True, label=None):
    d = tmp_path / "RG-9999"
    d.mkdir()
    if hero:
        _img(d / "hero.jpeg", (200, 30, 30))
    palette = [(30, 160, 30), (30, 30, 200), (200, 160, 30), (160, 30, 160), (30, 160, 160)]
    for i, name in enumerate(details):
        _img(d / f"{name}.jpeg", palette[i % len(palette)])
    if label is not None:
        (d / "label.json").write_text(json.dumps(label), encoding="utf-8")
    return d


def test_selects_hero_and_three_roles(tmp_path):
    d = _item(tmp_path)
    sel = cb.select_slots(d)
    assert sel is not None
    assert sel["hero"].name == "hero.jpeg"
    assert [s["role"] for s in sel["rail"]] == ["provenance", "feature", "condition"]


def test_skips_when_too_few_details(tmp_path):
    d = _item(tmp_path, details=("detail-maker-mark", "detail-lid"))
    assert cb.select_slots(d) is None


def test_skips_when_no_hero(tmp_path):
    d = _item(tmp_path, hero=False)
    assert cb.select_slots(d) is None


def test_caption_generic_fallback(tmp_path):
    d = _item(tmp_path)
    prov = cb.select_slots(d)["rail"][0]
    assert prov["caption"] == "Maker's mark"


def test_caption_override_from_label_json(tmp_path):
    d = _item(tmp_path, label={"sku": "RG-9999",
                               "combo_captions": {"provenance": "Kreamer · Size 50"}})
    prov = cb.select_slots(d)["rail"][0]
    assert prov["caption"] == "Kreamer · Size 50"
