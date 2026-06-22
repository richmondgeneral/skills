"""Tests for combo.py — deterministic 1:1 marketplace combo collage."""
import json
import os
import subprocess
import sys

from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import combo as cb

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "scripts", "combo.py")


def _img(path, color, size=(600, 600)):
    Image.new("RGB", size, color).save(path)


def _cutout(path, color, block, size=(400, 400)):
    """Transparent `size` RGBA PNG with a centered opaque `block`x`block` square of `color`."""
    im = Image.new("RGBA", size, (0, 0, 0, 0))
    b = Image.new("RGBA", (block, block), (*color, 255))
    im.paste(b, ((size[0] - block) // 2, (size[1] - block) // 2))
    im.save(path)


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


def test_crop_cover_exact_size(tmp_path):
    out = cb.crop_cover(Image.new("RGB", (800, 400), (10, 20, 30)), 300, 300)
    assert out.size == (300, 300)


def test_crop_cover_is_cover_not_contain(tmp_path):
    out = cb.crop_cover(Image.new("RGB", (800, 400), (200, 30, 30)), 300, 300)
    assert out.getpixel((0, 0)) == (200, 30, 30)        # filled, no white letterbox
    assert out.getpixel((299, 299)) == (200, 30, 30)


def test_crop_cover_flattens_alpha_on_white(tmp_path):
    src = Image.new("RGBA", (400, 400), (0, 0, 0, 0))    # fully transparent
    out = cb.crop_cover(src, 200, 200)
    assert out.mode == "RGB"
    assert out.getpixel((100, 100)) == cb.PANEL_BG       # transparency -> white, not black


def test_fills_leftover_slots_and_clamps_rail(tmp_path):
    d = _item(tmp_path, details=("detail-maker-mark", "detail-lid", "detail-bottom",
                                  "detail-interior", "detail-side"))
    sel = cb.select_slots(d, rail=4)
    assert [s["role"] for s in sel["rail"]] == ["provenance", "feature", "condition", "detail"]
    assert len(sel["rail"]) == 4
    assert len(cb.select_slots(d, rail=2)["rail"]) == 3     # clamps up to RAIL_DEFAULT
    assert len(cb.select_slots(d, rail=99)["rail"]) == 4    # clamps down to RAIL_MAX


def test_caption_override_ignores_non_dict(tmp_path):
    d = _item(tmp_path, label={"sku": "RG-9999", "combo_captions": ["oops"]})
    prov = cb.select_slots(d)["rail"][0]
    assert prov["caption"] == "Maker's mark"                # malformed override ignored


def _close(a, b, tol=4):
    # JPEG fixtures + LANCZOS resample shift solid colors by a level or two;
    # assert the region came from the right source, not byte-exact RGB.
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def test_output_size_is_1600(tmp_path):
    out = cb.compose_combo(_item(tmp_path))
    assert out is not None and out.exists()
    assert Image.open(out).size == (1600, 1600)


def test_hero_region_from_hero(tmp_path):
    im = Image.open(cb.compose_combo(_item(tmp_path))).convert("RGB")
    assert _close(im.getpixel((12, 800)), (200, 30, 30))   # hero is solid red, left/mid


def test_gutter_between_hero_and_rail_is_cream(tmp_path):
    im = Image.open(cb.compose_combo(_item(tmp_path))).convert("RGB")
    hero_w = round(1600 * cb.HERO_FRAC)                   # 992
    assert im.getpixel((hero_w + cb.GUTTER // 2, 800)) == cb.CREAM


def test_first_rail_cell_present(tmp_path):
    im = Image.open(cb.compose_combo(_item(tmp_path))).convert("RGB")
    rail_x = round(1600 * cb.HERO_FRAC) + cb.GUTTER       # 1008
    assert _close(im.getpixel((rail_x + 6, 18)), (30, 160, 30))  # first detail green, top of cell


def test_skip_removes_stale_combo(tmp_path):
    d = _item(tmp_path, details=("detail-maker-mark",))   # too few
    (d / cb.COMBO_FILENAME).write_bytes(b"stale")
    assert cb.compose_combo(d) is None
    assert not (d / cb.COMBO_FILENAME).exists()


def _luma(im, box):
    px = im.convert("RGB").crop(box).getdata()
    return sum(0.299 * r + 0.587 * g + 0.114 * b for r, g, b in px) / len(px)


def test_caption_darkens_cell_lower_left(tmp_path):
    im = Image.open(cb.compose_combo(_item(tmp_path))).convert("RGB")
    rail_x = round(1600 * cb.HERO_FRAC) + cb.GUTTER
    cell_h = (1600 - 2 * cb.GUTTER) // 3
    top = _luma(im, (rail_x + 4, 4, rail_x + 180, 60))
    low = _luma(im, (rail_x + 4, cell_h - 70, rail_x + 180, cell_h - 6))
    assert low < top - 20            # scrim pill present in lower-left


def test_compose_with_captions_keeps_size(tmp_path):
    im = Image.open(cb.compose_combo(_item(tmp_path)))
    assert im.size == (1600, 1600)   # wordmark + captions don't break the canvas


def test_records_photos_combo(tmp_path):
    d = _item(tmp_path, label={"sku": "RG-9999"})
    cb.compose_combo(d)
    cb.record_photos_combo(d, made=True)
    data = json.loads((d / "label.json").read_text())
    assert data["photos"]["combo"] == "combo.png"


def test_record_is_idempotent(tmp_path):
    d = _item(tmp_path, label={"sku": "RG-9999"})
    cb.compose_combo(d)
    cb.record_photos_combo(d, made=True)
    first = (d / "label.json").read_text()
    cb.record_photos_combo(d, made=True)                 # second call must not rewrite
    assert (d / "label.json").read_text() == first


def test_records_image_pipeline_entry(tmp_path):
    d = _item(tmp_path, label={"sku": "RG-9999"})
    cb.compose_combo(d)
    data = json.loads((d / "label.json").read_text())
    ops = [e.get("op") for e in data.get("image_pipeline", [])]
    assert "combo" in ops


def test_record_removes_combo_when_skipped(tmp_path):
    d = _item(tmp_path, label={"sku": "RG-9999", "photos": {"combo": "combo.png"}})
    cb.record_photos_combo(d, made=False)
    data = json.loads((d / "label.json").read_text())
    assert "combo" not in data.get("photos", {})


def test_cli_builds_and_records(tmp_path):
    d = _item(tmp_path, label={"sku": "RG-9999"})
    rc = subprocess.run([sys.executable, SCRIPT, "--item-dir", str(d)]).returncode
    assert rc == 0
    assert (d / "combo.png").exists()
    assert json.loads((d / "label.json").read_text())["photos"]["combo"] == "combo.png"


def test_cli_exit_2_on_skip(tmp_path):
    d = _item(tmp_path, details=("detail-maker-mark",))   # too few details
    rc = subprocess.run([sys.executable, SCRIPT, "--item-dir", str(d)]).returncode
    assert rc == 2


def test_batch_backfills_eligible_only(tmp_path):
    items = tmp_path / "items"
    items.mkdir()
    _item(items, details=("detail-maker-mark", "detail-lid", "detail-bottom"))      # RG-9999 eligible
    thin = items / "RG-0001"
    thin.mkdir()
    _img(thin / "hero.jpeg", (10, 10, 10))
    _img(thin / "detail-mark.jpeg", (20, 20, 20))                                   # only 1 detail
    made, skipped = cb._batch(items)
    assert made == 1 and skipped == 1


def test_hero_prefers_cutout_over_raw(tmp_path):
    d = _item(tmp_path)                                  # has hero.jpeg + 3 details
    _cutout(d / "cutout.png", (10, 200, 10), 200)        # add a transparent master
    assert cb.select_slots(d)["hero"].name == "cutout.png"


def test_transparent_hero_is_contained_with_white_padding(tmp_path):
    d = _item(tmp_path)
    _cutout(d / "cutout.png", (10, 200, 10), 200)        # 200x200 green block in 400x400
    im = Image.open(cb.compose_combo(d)).convert("RGB")
    hero_w = round(1600 * cb.HERO_FRAC)                   # 992
    assert im.getpixel((hero_w // 2, 6)) == cb.PANEL_BG   # contain leaves a white band at the top
    assert _close(im.getpixel((hero_w // 2, 800)), (10, 200, 10), 6)  # subject fills the middle


def test_raw_hero_still_covers(tmp_path):
    d = _item(tmp_path)                                  # only hero.jpeg (opaque) -> cover path
    im = Image.open(cb.compose_combo(d)).convert("RGB")
    assert _close(im.getpixel((12, 800)), (200, 30, 30), 4)   # red hero fills, no white band mid-left


def test_subcrop_normalized_size(tmp_path):
    base = Image.new("RGB", (1000, 800), (0, 0, 0))
    out = cb._subcrop(base, [0.25, 0.5, 0.5, 0.25])
    assert out.size == (500, 200)


def test_operator_crop_box_aims_the_panel(tmp_path):
    # provenance detail = green base with a RED patch at normalized [0.6,0.6,0.2,0.2].
    d = tmp_path / "RG-9999"
    d.mkdir()
    _img(d / "hero.jpeg", (200, 30, 30))
    base = Image.new("RGB", (500, 500), (30, 160, 30))
    base.paste(Image.new("RGB", (100, 100), (220, 20, 20)), (300, 300))  # red at x,y=0.6,0.6
    base.save(d / "detail-maker-mark.jpeg")
    _img(d / "detail-lid.jpeg", (30, 30, 200))
    _img(d / "detail-bottom.jpeg", (200, 160, 30))
    (d / "label.json").write_text(json.dumps(
        {"sku": "RG-9999", "combo_crops": {"provenance": [0.6, 0.6, 0.2, 0.2]}}))
    im = Image.open(cb.compose_combo(d)).convert("RGB")
    rail_x = round(1600 * cb.HERO_FRAC) + cb.GUTTER
    cell_h = (1600 - 2 * cb.GUTTER) // 3
    # center of the FIRST rail cell should now be the red patch (not the green base)
    px = im.getpixel((rail_x + 592 // 2, cell_h // 2))
    assert _close(px, (220, 20, 20), 8)


def test_operator_crop_box_ignores_non_numeric(tmp_path):
    d = _item(tmp_path, label={"sku": "RG-9999",
                               "combo_crops": {"provenance": [".6", ".6", ".2", ".2"]}})
    sel = cb.select_slots(d)
    assert sel["rail"][0]["crop"] is None        # non-numeric box ignored, not crashed
    assert cb.compose_combo(d) is not None        # and compose does not raise
