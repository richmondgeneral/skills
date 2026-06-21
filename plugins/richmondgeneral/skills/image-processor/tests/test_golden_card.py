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


def test_fully_transparent_input_is_skipped(tmp_path):
    src = tmp_path / "hero.png"
    Image.new("RGBA", (800, 600), (0, 0, 0, 0)).save(src)   # nothing to float
    out = gc.compose_golden_card(src, tmp_path / "card.png")
    assert out is None
    assert not (tmp_path / "card.png").exists()


def test_tiny_speck_is_skipped(tmp_path):
    src = tmp_path / "hero.png"
    img = Image.new("RGBA", (800, 600), (0, 0, 0, 0))
    img.putpixel((400, 300), (255, 0, 0, 255))   # a single opaque pixel (alpha noise)
    img.save(src)
    out = gc.compose_golden_card(src, tmp_path / "card.png")
    assert out is None
    assert not (tmp_path / "card.png").exists()


def test_skip_deletes_stale_card(tmp_path):
    card = tmp_path / "card.png"
    card.write_bytes(b"stale")                       # pre-existing stale card
    src = tmp_path / "hero.png"
    Image.new("RGB", (800, 600), (10, 20, 30)).save(src)   # opaque -> skip
    out = gc.compose_golden_card(src, card)
    assert out is None
    assert not card.exists()                         # stale card removed on skip


def test_record_photos_card_reconciles(tmp_path):
    import json
    label = tmp_path / "label.json"
    label.write_text(json.dumps({"photos": {"hero": "hero.png", "card": "card.png"}}))
    # no card.png present -> stale photos.card removed
    gc.record_photos_card(tmp_path)
    assert "card" not in json.loads(label.read_text())["photos"]
    # card.png present -> photos.card set
    (tmp_path / "card.png").write_bytes(b"x")
    gc.record_photos_card(tmp_path)
    assert json.loads(label.read_text())["photos"]["card"] == "card.png"


def test_record_photos_card_no_write_when_no_change(tmp_path):
    # Item with no card and no photos.card: record_photos_card must NOT modify the file
    # (no reformat, no empty "photos": {} added).
    label = tmp_path / "label.json"
    original = '{\n  "sku": "RG-9999"\n}\n'
    label.write_text(original)
    gc.record_photos_card(tmp_path)                 # no card.png present
    assert label.read_text() == original            # byte-identical, untouched


def test_record_photos_card_idempotent_when_already_set(tmp_path):
    import json
    label = tmp_path / "label.json"
    (tmp_path / "card.png").write_bytes(b"x")        # card exists
    gc.record_photos_card(tmp_path)                  # creates photos.card
    after_first = label.read_text() if label.exists() else None
    # label.json didn't exist at first call -> record is a no-op when label.json is absent;
    # create it now WITH the correct value and confirm a second call doesn't rewrite it.
    label.write_text(json.dumps({"photos": {"card": "card.png"}}, indent=2))
    before = label.read_text()
    gc.record_photos_card(tmp_path)                  # already correct -> no write
    assert label.read_text() == before
