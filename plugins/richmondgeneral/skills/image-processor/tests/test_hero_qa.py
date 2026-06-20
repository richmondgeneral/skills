"""Tests for the pre-publish Hero QA gate (hero_qa.py).

Fixtures are self-generated (the RG-0031 prototype imgs are not on disk):
  - _rect_alpha(angle): an RGBA cutout whose alpha is a filled rect rotated by
    `angle` — the deterministic alpha path (mirrors the RG-0031 crooked cutout).
  - _text_hero_bgr(): real rendered text for tesseract OSD upright tests.
  - _straight_book_bgr(): a geometric opaque 'cover' for bg/full-face tests.
"""
import os
import sys
import json

import numpy as np
import cv2
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import hero_qa as hq

FIX = os.path.join(os.path.dirname(__file__), "_fixtures")


def _save_png_to(path, bgr, alpha=None):
    os.makedirs(os.path.dirname(str(path)), exist_ok=True)
    if alpha is not None:
        bgra = cv2.cvtColor(bgr, cv2.COLOR_BGR2BGRA)
        bgra[:, :, 3] = alpha
        cv2.imwrite(str(path), bgra)
    else:
        cv2.imwrite(str(path), bgr)
    return str(path)


def _save_png(name, bgr, alpha=None):
    os.makedirs(FIX, exist_ok=True)
    return _save_png_to(os.path.join(FIX, name), bgr, alpha)


def _rect_alpha(angle=0, size=400, rw=180, rh=300):
    """RGBA: a filled rectangle (dark on light) whose alpha is rotated `angle`°."""
    bgr = np.full((size, size, 3), 200, np.uint8)
    alpha = np.zeros((size, size), np.uint8)
    x0, y0 = size // 2 - rw // 2, size // 2 - rh // 2
    cv2.rectangle(alpha, (x0, y0), (x0 + rw, y0 + rh), 255, -1)
    if angle:
        M = cv2.getRotationMatrix2D((size / 2, size / 2), angle, 1.0)
        alpha = cv2.warpAffine(alpha, M, (size, size))
    bgr[alpha > 0] = (60, 60, 60)
    return bgr, alpha


def _straight_book_bgr():
    """Opaque portrait 'cover' with horizontal bars (full-bleed by design)."""
    img = np.full((480, 320, 3), 235, np.uint8)
    cv2.rectangle(img, (8, 8), (311, 471), (40, 40, 40), 6)
    for y in (90, 150, 210, 330):
        cv2.rectangle(img, (40, y), (280, y + 22), (30, 30, 30), -1)
    return img


def _text_hero_bgr():
    """Render real multi-line text (dark on white) for tesseract OSD tests."""
    from PIL import Image, ImageDraw, ImageFont
    W, H = 360, 480
    img = Image.new("RGB", (W, H), (245, 245, 245))
    d = ImageDraw.Draw(img)
    font = None
    for fp in ("/System/Library/Fonts/Supplemental/Arial.ttf",
               "/System/Library/Fonts/Helvetica.ttc",
               "/Library/Fonts/Arial.ttf"):
        if os.path.exists(fp):
            font = ImageFont.truetype(fp, 34)
            break
    if font is None:
        font = ImageFont.load_default()
    lines = ["THE SANDS", "OF MARS", "a novel by", "ARTHUR C", "CLARKE", "pocket books"]
    y = 60
    for ln in lines:
        d.text((40, y), ln, fill=(20, 20, 20), font=font)
        y += 60
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


# --------------------------------------------------------------------------
# Task 2 — level check
# --------------------------------------------------------------------------
def test_level_pass_on_straight_cutout():
    bgr, alpha = _rect_alpha(angle=0)
    p = _save_png("level_straight.png", bgr, alpha)
    r = hq.check_level(p)
    assert r["ok"] is True
    assert r["level_deg"] <= 1.5


def test_level_fail_on_16deg_tilt():
    bgr, alpha = _rect_alpha(angle=16)
    p = _save_png("level_tilt16.png", bgr, alpha)
    r = hq.check_level(p)
    assert r["ok"] is False
    assert r["level_deg"] > 1.5


# --------------------------------------------------------------------------
# Task 3 — upright check (tesseract OSD + fallback)
# --------------------------------------------------------------------------
def _osd_available():
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


OSD = _osd_available()
needs_osd = pytest.mark.skipif(not OSD, reason="tesseract OSD unavailable")


@needs_osd
def test_upright_fail_on_90deg_rotation():
    p = _save_png("up_rot90.png", np.rot90(_text_hero_bgr(), 1))
    r = hq.check_upright(p)
    assert r["ok"] is False
    assert "90" in r["reason"]


@needs_osd
def test_upright_fail_on_270deg_rotation():
    p = _save_png("up_rot270.png", np.rot90(_text_hero_bgr(), 3))
    assert hq.check_upright(p)["ok"] is False


@needs_osd
def test_upright_pass_on_straight_text():
    p = _save_png("up_straight.png", _text_hero_bgr())
    assert hq.check_upright(p)["ok"] is True


def test_upright_does_not_false_fail_textless_image():
    # a textless gradient: OSD errors -> fallback with no original -> must pass
    grad = np.tile(np.linspace(0, 255, 300, dtype=np.uint8), (300, 1))
    p = _save_png("up_textless.png", cv2.cvtColor(grad, cv2.COLOR_GRAY2BGR))
    assert hq.check_upright(p)["ok"] is True


def test_upright_flags_lowconf_rotation(monkeypatch):
    # Atari cartridges read rotate!=0 at LOW conf (0.12-0.19). Lock that the
    # threshold logic flags any nonzero rotate above the noise floor, and never
    # flags rotate=0. (tesseract-independent: OSD is monkeypatched.)
    p = _save_png("up_logic.png", _straight_book_bgr())
    monkeypatch.setattr(hq, "_osd_rotation", lambda bgr: {"rotate": 270.0, "conf": 0.15})
    assert hq.check_upright(p)["ok"] is False                 # low-conf sideways -> fail
    monkeypatch.setattr(hq, "_osd_rotation", lambda bgr: {"rotate": 0.0, "conf": 0.10})
    assert hq.check_upright(p)["ok"] is True                  # upright -> pass
    monkeypatch.setattr(hq, "_osd_rotation", lambda bgr: {"rotate": 90.0, "conf": 0.02})
    assert hq.check_upright(p)["ok"] is True                  # below noise floor -> pass


# --------------------------------------------------------------------------
# Task 4 — full-face (class-aware clip detection)
# --------------------------------------------------------------------------
def test_full_face_fail_on_clipped_cutout():
    bgr = np.full((400, 400, 3), 200, np.uint8)
    alpha = np.zeros((400, 400), np.uint8)
    alpha[0:260, 0:240] = 255                      # flush to the top-left corner
    p = _save_png("ff_clip.png", bgr, alpha)
    assert hq.check_full_face(p, item_class="cutout")["ok"] is False


def test_full_face_pass_on_floating_cutout():
    bgr = np.full((400, 400, 3), 200, np.uint8)
    alpha = np.zeros((400, 400), np.uint8)
    alpha[80:320, 120:280] = 255                   # clear margin from every border
    p = _save_png("ff_float.png", bgr, alpha)
    assert hq.check_full_face(p, item_class="cutout")["ok"] is True


def test_full_face_lenient_for_flat_goods_fullbleed():
    p = _save_png("ff_flat.png", _straight_book_bgr())   # opaque, reaches edges
    assert hq.check_full_face(p, item_class="flat")["ok"] is True


# --------------------------------------------------------------------------
# Task 5 — background by class
# --------------------------------------------------------------------------
def test_bg_cutout_requires_transparency():
    p = _save_png("bg_opaque.png", _straight_book_bgr())          # no alpha
    assert hq.check_bg(p, item_class="cutout")["ok"] is False


def test_bg_cutout_pass_with_transparency():
    bgr, alpha = _rect_alpha(angle=0)
    p = _save_png("bg_transp.png", bgr, alpha)
    assert hq.check_bg(p, item_class="cutout")["ok"] is True


def test_bg_flat_requires_opaque():
    bgr, alpha = _rect_alpha(angle=0)
    p = _save_png("bg_flat_transp.png", bgr, alpha)              # transparent
    assert hq.check_bg(p, item_class="flat")["ok"] is False


def test_bg_keepbg_is_lenient():
    p = _save_png("bg_keepbg.png", _straight_book_bgr())
    assert hq.check_bg(p, item_class="keepbg")["ok"] is True


# --------------------------------------------------------------------------
# Task 6 — defect-retention (soft)
# --------------------------------------------------------------------------
def test_defects_not_compared_without_original():
    p = _save_png("def_solo.png", _straight_book_bgr())
    r = hq.check_defects(p, original_path=None)
    assert r["ok"] is True and r["reason"] == "not_compared"


def test_defects_fail_on_extreme_detail_wipe():
    orig = _straight_book_bgr()                     # has edges/detail
    blank = np.full_like(orig, 235)                 # detail wiped
    po = _save_png("def_orig.png", orig)
    pb = _save_png("def_wiped.png", blank)
    assert hq.check_defects(pb, original_path=po)["ok"] is False


def test_defects_pass_on_honest_retention():
    orig = _straight_book_bgr()
    po = _save_png("def_orig2.png", orig)
    ph = _save_png("def_hero2.png", orig.copy())    # same detail retained
    assert hq.check_defects(ph, original_path=po)["ok"] is True


# --------------------------------------------------------------------------
# Task 7 — orchestration + class resolution
# --------------------------------------------------------------------------
def test_gate_fails_and_collects_reasons():
    # opaque (no transparency) 90°-rotated 'cutout' -> fails bg (+ upright if OSD)
    p = _save_png("gate_bad.png", np.rot90(_text_hero_bgr(), 1))
    r = hq.hero_qa_gate(p, item_class="cutout")
    assert r["status"] == "fail"
    assert len(r["reasons"]) >= 1
    assert set(r["checks"]) == {"upright", "level_deg", "full_face", "bg_ok", "defects_ok"}


def test_gate_passes_clean_flat_hero():
    p = _save_png("gate_good.png", _straight_book_bgr())
    r = hq.hero_qa_gate(p, item_class="flat")
    assert r["status"] == "pass"
    assert r["reasons"] == []


def test_resolve_item_class_from_label(tmp_path):
    item = tmp_path / "RG-9001"
    item.mkdir()
    (item / "label.json").write_text(json.dumps({"product_name": "Vintage hardcover book"}))
    assert hq.resolve_item_class(str(item)) == "flat"      # book/hardcover -> flat-goods


# --------------------------------------------------------------------------
# Task 8 — CLI single item writes label.json -> hero_qa
# --------------------------------------------------------------------------
def test_cli_writes_hero_qa_block_on_pass(tmp_path):
    item = tmp_path / "RG-9002"
    item.mkdir()
    _save_png_to(item / "hero.png", _straight_book_bgr())
    (item / "label.json").write_text(json.dumps(
        {"product_name": "hardcover book", "state": "Priced", "price": 12}))
    rc = hq.run_item(str(item), write=True)
    d = json.loads((item / "label.json").read_text())
    assert d["hero_qa"]["status"] == "pass"
    assert d["hero_qa"]["checker"] == hq.CHECKER
    assert d["price"] == 12                                 # other fields preserved
    assert rc == 0


def test_cli_fail_sets_needs_manual(tmp_path):
    item = tmp_path / "RG-9003"
    item.mkdir()
    _save_png_to(item / "hero.png", _straight_book_bgr())   # opaque -> fails cutout bg
    (item / "label.json").write_text(json.dumps({"product_name": "ceramic mug", "state": "Priced"}))
    rc = hq.run_item(str(item), write=True)
    d = json.loads((item / "label.json").read_text())
    assert d["hero_qa"]["status"] == "fail"
    assert d["photo_overrides"]["status"] == "needs_manual"
    assert rc == 1
