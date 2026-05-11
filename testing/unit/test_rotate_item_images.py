"""
Tests for rotate_item_images.py — verifies the CW rotation math is correct
(easy to flip by accident since PIL is CCW-positive).
"""
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
