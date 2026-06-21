"""Tests for golden_card.py — deterministic golden-ratio card composition."""
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import golden_card as gc


def _cutout(w, h, mw, mh):
    """Transparent w×h RGBA with an opaque mw×mh white block centered (a fake cutout)."""
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    block = Image.new("RGBA", (mw, mh), (255, 255, 255, 255))
    img.paste(block, ((w - mw) // 2, (h - mh) // 2))
    return img


def test_output_is_horizontal_golden_ratio(tmp_path):
    src = tmp_path / "hero.png"
    _cutout(800, 800, 400, 600).save(src)
    out = gc.compose_golden_card(src, tmp_path / "card.png")
    assert out is not None and out.exists()
    im = Image.open(out)
    assert im.size == (2000, 1236)                 # default width 2000, height = round(2000/phi)
    assert abs(im.width / im.height - gc.PHI) < 0.01
    assert im.width > im.height                     # horizontal


def test_padding_is_transparent(tmp_path):
    src = tmp_path / "hero.png"
    _cutout(800, 800, 400, 600).save(src)
    im = Image.open(gc.compose_golden_card(src, tmp_path / "card.png")).convert("RGBA")
    assert im.getpixel((0, 0))[3] == 0             # corners fully transparent
    assert im.getpixel((im.width - 1, im.height - 1))[3] == 0


def test_object_centered(tmp_path):
    src = tmp_path / "hero.png"
    _cutout(800, 800, 300, 500).save(src)
    im = Image.open(gc.compose_golden_card(src, tmp_path / "card.png")).convert("RGBA")
    bbox = im.getchannel("A").getbbox()
    cx = (bbox[0] + bbox[2]) / 2
    cy = (bbox[1] + bbox[3]) / 2
    assert abs(cx - im.width / 2) <= 2
    assert abs(cy - im.height / 2) <= 2


def test_portrait_is_height_constrained(tmp_path):
    src = tmp_path / "hero.png"
    _cutout(800, 800, 200, 760).save(src)          # tall object
    im = Image.open(gc.compose_golden_card(src, tmp_path / "card.png")).convert("RGBA")
    bbox = im.getchannel("A").getbbox()
    obj_h = bbox[3] - bbox[1]
    assert abs(obj_h - gc.DEFAULT_FILL * im.height) <= 3   # fills ~fill of HEIGHT
    assert (bbox[2] - bbox[0]) < im.width                  # margins left/right


def test_wide_is_width_constrained(tmp_path):
    src = tmp_path / "hero.png"
    _cutout(800, 800, 760, 200).save(src)          # wide object
    im = Image.open(gc.compose_golden_card(src, tmp_path / "card.png")).convert("RGBA")
    bbox = im.getchannel("A").getbbox()
    obj_w = bbox[2] - bbox[0]
    assert abs(obj_w - gc.DEFAULT_FILL * im.width) <= 3    # fills ~fill of WIDTH


def test_opaque_input_is_skipped(tmp_path):
    src = tmp_path / "hero.png"
    Image.new("RGB", (800, 600), (120, 120, 120)).save(src)   # fully opaque, no alpha
    out = gc.compose_golden_card(src, tmp_path / "card.png")
    assert out is None
    assert not (tmp_path / "card.png").exists()


def test_custom_width_derives_golden_height(tmp_path):
    src = tmp_path / "hero.png"
    _cutout(800, 800, 400, 400).save(src)
    im = Image.open(gc.compose_golden_card(src, tmp_path / "card.png", width=1000))
    assert im.size == (1000, round(1000 / gc.PHI))           # 1000 x 618
