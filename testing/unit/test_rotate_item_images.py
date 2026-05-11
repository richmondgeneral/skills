"""
Tests for rotate_item_images.py — verifies the CW rotation math is correct
(easy to flip by accident since PIL is CCW-positive), the EXIF transpose
runs up-front, the four-candidate scoring picks the right winner, and the
--min-confidence gate skips the Square write on low-confidence detections.
"""
import argparse

from PIL import Image, ImageDraw

import rotate_item_images as rim


def _make_marker_image(tmp_path, name="src.png", size=(40, 80)):
    """Tall image with a red pixel in the TOP-LEFT corner — easy to verify
    orientation after rotation."""
    img = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(img)
    draw.rectangle([(0, 0), (4, 4)], fill="red")
    p = tmp_path / name
    img.save(p)
    return p


def test_cw_90_moves_top_left_red_to_top_right(tmp_path):
    src = _make_marker_image(tmp_path)
    dst = tmp_path / "out.png"

    rim.rotate_to_correct(src, dst, 90)

    out = Image.open(dst)
    # Original was 40w × 80h with red at (0,0). After CW 90° it becomes
    # 80w × 40h with the red square in the TOP-RIGHT.
    assert out.size == (80, 40), f"expected 80x40, got {out.size}"
    # Top-right pixel should be red.
    px = out.getpixel((out.size[0] - 1, 0))
    assert px == (255, 0, 0), f"expected red at top-right, got {px}"
    # Top-left should now be white.
    assert out.getpixel((0, 0)) == (255, 255, 255)


def test_cw_180_moves_top_left_red_to_bottom_right(tmp_path):
    src = _make_marker_image(tmp_path)
    dst = tmp_path / "out.png"

    rim.rotate_to_correct(src, dst, 180)

    out = Image.open(dst)
    assert out.size == (40, 80)
    assert out.getpixel((out.size[0] - 1, out.size[1] - 1)) == (255, 0, 0)
    assert out.getpixel((0, 0)) == (255, 255, 255)


def test_cw_270_moves_top_left_red_to_bottom_left(tmp_path):
    src = _make_marker_image(tmp_path)
    dst = tmp_path / "out.png"

    rim.rotate_to_correct(src, dst, 270)

    out = Image.open(dst)
    assert out.size == (80, 40)
    assert out.getpixel((0, out.size[1] - 1)) == (255, 0, 0)
    assert out.getpixel((0, 0)) == (255, 255, 255)


def test_cw_0_is_passthrough(tmp_path):
    src = _make_marker_image(tmp_path)
    dst = tmp_path / "out.png"

    rim.rotate_to_correct(src, dst, 0)

    out = Image.open(dst)
    assert out.size == (40, 80)
    assert out.getpixel((0, 0)) == (255, 0, 0)


def test_jpeg_with_alpha_input_coerces_to_rgb(tmp_path):
    """If input is RGBA (e.g., transparent PNG) but format is JPEG, must
    coerce to RGB so PIL doesn't crash on save."""
    src = tmp_path / "src.jpg"
    img = Image.new("RGB", (10, 20), "white")
    img.save(src, format="JPEG")
    # Re-open and convert to RGBA in memory to simulate the edge case.
    # The save path inside rotate_to_correct should handle this.
    dst = tmp_path / "out.jpg"
    rim.rotate_to_correct(src, dst, 90)
    out = Image.open(dst)
    assert out.size == (20, 10)


def test_png_source_stays_png_not_demoted_to_jpeg(tmp_path):
    """Regression: ImageOps.exif_transpose returns a copy with .format=None,
    so reading img.format after transposing falls through to 'JPEG' and the
    file gets silently re-encoded as lossy JPEG with a .png filename. The
    fix captures .format BEFORE transpose."""
    src = _make_marker_image(tmp_path)
    dst = tmp_path / "out.png"
    rim.rotate_to_correct(src, dst, 0)
    out = Image.open(dst)
    assert out.format == "PNG", f"expected PNG, got {out.format}"


# ============================================================================
# EXIF transpose: orientation tag in the source must be baked into pixels and
# stripped from the output, otherwise downstream viewers honoring the tag will
# double-rotate.
# ============================================================================

def _make_jpeg_with_exif_orientation(path, orientation, size=(40, 80)):
    """Write a JPEG with red top-left and the given EXIF orientation tag.
    Orientation=6 means 'rotate 90 CW to display upright' — i.e. raw pixels
    are 'sideways' as stored on disk."""
    img = Image.new("RGB", size, "white")
    ImageDraw.Draw(img).rectangle([(0, 0), (4, 4)], fill="red")
    exif = img.getexif()
    exif[0x0112] = orientation
    img.save(path, format="JPEG", exif=exif.tobytes(), quality=95)


def test_exif_orientation_baked_in_and_tag_stripped(tmp_path):
    src = tmp_path / "src.jpg"
    _make_jpeg_with_exif_orientation(src, orientation=6)

    dst = tmp_path / "out.jpg"
    rim.rotate_to_correct(src, dst, 0)

    out = Image.open(dst)
    # Raw 40w × 80h with orientation=6 → after 90 CW transpose → 80w × 40h.
    assert out.size == (80, 40), f"transpose not applied: got {out.size}"
    # Red square ends up in the top-right after 90 CW. JPEG chroma subsampling
    # smears the red/white edge a lot, so compare corners rather than expect
    # near-saturated red.
    tr_r, tr_g, tr_b = out.getpixel((77, 2))[:3]
    _, tl_g, _ = out.getpixel((2, 2))[:3]
    assert tr_r > 150 and tr_g < 80 and tr_b < 80, (
        f"expected red-dominant top-right, got ({tr_r}, {tr_g}, {tr_b})")
    # G is the direction discriminator: white has G≈255, red has G≈0-30.
    # If transpose went CCW (wrong direction), red would be in top-LEFT and
    # tl_g would also be low.
    assert tl_g - tr_g > 100, (
        f"red should be in top-RIGHT (cw=90 direction), not top-left; "
        f"top-right G={tr_g}, top-left G={tl_g}")
    # Orientation tag must be absent or 1, otherwise a viewer rotates again.
    out_exif = out.getexif()
    assert out_exif.get(0x0112, 1) == 1, (
        f"orientation should be stripped, got {out_exif.get(0x0112)}")


# ============================================================================
# detect_rotation_via_gemini: scoring logic with mocked Gemini calls.
# max_workers=1 makes _gemini_call invocations deterministic in [0,90,180,270]
# order, letting the fake return per-cw canned responses by counter index.
# ============================================================================

def _patch_gemini_responses(monkeypatch, responses_by_cw):
    order = [0, 90, 180, 270]
    counter = {"n": 0}

    def fake_call(image_bytes, mime, api_key, timeout=30):
        cw = order[counter["n"]]
        counter["n"] += 1
        return responses_by_cw[cw]

    monkeypatch.setattr(rim, "_gemini_call", fake_call)


def test_detect_picks_clean_winner(tmp_path, monkeypatch):
    _patch_gemini_responses(monkeypatch, {
        0:   {"is_upright": False, "confidence": 0.10, "reasoning": "sideways"},
        90:  {"is_upright": False, "confidence": 0.10, "reasoning": "sideways"},
        180: {"is_upright": False, "confidence": 0.20, "reasoning": "upside-down"},
        270: {"is_upright": True,  "confidence": 0.90, "reasoning": "text upright"},
    })
    src = _make_marker_image(tmp_path)

    result = rim.detect_rotation_via_gemini(src, "fake-key", max_workers=1)

    assert result["rotation_cw_degrees"] == 270
    assert result["confidence"] == 0.90
    assert result["raw_confidence"] == 0.90
    assert result["n_upright_candidates"] == 1


def test_detect_penalizes_two_way_ambiguity(tmp_path, monkeypatch):
    """Two orientations marked upright at conf=1.0 → effective conf halved,
    so the min-confidence gate can catch and skip this case."""
    _patch_gemini_responses(monkeypatch, {
        0:   {"is_upright": True,  "confidence": 1.0, "reasoning": "ambig"},
        90:  {"is_upright": False, "confidence": 0.1, "reasoning": "sideways"},
        180: {"is_upright": True,  "confidence": 1.0, "reasoning": "ambig"},
        270: {"is_upright": False, "confidence": 0.1, "reasoning": "sideways"},
    })
    src = _make_marker_image(tmp_path)

    result = rim.detect_rotation_via_gemini(src, "fake-key", max_workers=1)

    assert result["n_upright_candidates"] == 2
    assert result["raw_confidence"] == 1.0
    assert result["confidence"] == 0.5
    # Tie-break: prefer cw=0 over a non-zero rotation when conf ties.
    assert result["rotation_cw_degrees"] == 0


def test_detect_returns_zero_when_nothing_upright(tmp_path, monkeypatch):
    _patch_gemini_responses(monkeypatch, {
        cw: {"is_upright": False, "confidence": 0.3, "reasoning": "ambig"}
        for cw in (0, 90, 180, 270)
    })
    src = _make_marker_image(tmp_path)

    result = rim.detect_rotation_via_gemini(src, "fake-key", max_workers=1)

    assert result["rotation_cw_degrees"] == 0
    assert result["confidence"] == 0.0
    assert "no orientation scored as upright" in result["reasoning"]


def test_detect_tie_break_prefers_no_rotation(tmp_path, monkeypatch):
    """When cw=0 and a non-zero cw tie on confidence, prefer cw=0
    (rotation must clearly beat 'leave alone')."""
    _patch_gemini_responses(monkeypatch, {
        0:   {"is_upright": True,  "confidence": 0.8, "reasoning": "ok"},
        90:  {"is_upright": True,  "confidence": 0.8, "reasoning": "also ok"},
        180: {"is_upright": False, "confidence": 0.1, "reasoning": "no"},
        270: {"is_upright": False, "confidence": 0.1, "reasoning": "no"},
    })
    src = _make_marker_image(tmp_path)

    result = rim.detect_rotation_via_gemini(src, "fake-key", max_workers=1)

    assert result["rotation_cw_degrees"] == 0
    assert result["confidence"] == 0.4  # 0.8 raw / 2 upright votes


# ============================================================================
# --min-confidence gate: rotate_one_image must skip the Square write when the
# detector's confidence falls below the threshold, and must never write under
# --inspect regardless of confidence.
# ============================================================================

def _wire_rotate_one_image(monkeypatch, detect_result):
    """Stub the I/O boundaries of rotate_one_image so we can drive the gate
    with canned detect output and observe whether Square gets called."""
    calls = {"detect": 0, "update": 0}

    def fake_detect(path, key, **kw):
        calls["detect"] += 1
        return detect_result

    def fake_update(*a, **kw):
        calls["update"] += 1

    def fake_get_image(token, version, image_id):
        return {"image_data": {"url": "https://fake.local/img.jpg",
                               "name": "img.jpg", "caption": ""}}

    class _FakeHead:
        headers = {"content-type": "image/jpeg"}

    def fake_head(url, **kw):
        return _FakeHead()

    def fake_download(url, dest):
        Image.new("RGB", (10, 10), "white").save(dest, format="JPEG")

    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    monkeypatch.setattr(rim, "detect_rotation_via_gemini", fake_detect)
    monkeypatch.setattr(rim, "update_catalog_image_inplace", fake_update)
    monkeypatch.setattr(rim, "get_image_object", fake_get_image)
    monkeypatch.setattr(rim, "download_image", fake_download)
    monkeypatch.setattr(rim.requests, "head", fake_head)

    return calls


def test_skips_apply_when_confidence_below_threshold(tmp_path, monkeypatch):
    calls = _wire_rotate_one_image(monkeypatch, detect_result={
        "rotation_cw_degrees": 90,
        "confidence": 0.40,  # below default 0.75
        "reasoning": "ambig",
    })
    args = argparse.Namespace(inspect=False, min_confidence=0.75)

    summary = rim.rotate_one_image("token", "v", "img-id", None, args, tmp_path)

    assert calls["detect"] == 1
    assert calls["update"] == 0, "must NOT touch Square when confidence is low"
    assert summary["applied"] is False
    assert "below --min-confidence" in summary.get("skipped_reason", "")


def test_applies_when_confidence_meets_threshold(tmp_path, monkeypatch):
    calls = _wire_rotate_one_image(monkeypatch, detect_result={
        "rotation_cw_degrees": 90,
        "confidence": 0.90,
        "reasoning": "clear",
    })
    args = argparse.Namespace(inspect=False, min_confidence=0.75)

    summary = rim.rotate_one_image("token", "v", "img-id", None, args, tmp_path)

    assert calls["update"] == 1
    assert summary["applied"] is True
    assert "skipped_reason" not in summary


def test_inspect_mode_never_writes_even_at_high_confidence(tmp_path, monkeypatch):
    calls = _wire_rotate_one_image(monkeypatch, detect_result={
        "rotation_cw_degrees": 90,
        "confidence": 1.0,
        "reasoning": "very confident",
    })
    args = argparse.Namespace(inspect=True, min_confidence=0.75)

    summary = rim.rotate_one_image("token", "v", "img-id", None, args, tmp_path)

    assert calls["update"] == 0, "inspect mode must NEVER call Square"
    assert summary["applied"] is False
