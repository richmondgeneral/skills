"""
Tests for downscale_output_in_place in clean.py — verifies the post-Gemini
in-place resize preserves alpha on PNG/WebP targets and only RGB-coerces
JPEG targets. The pre-fix code unconditionally `.convert("RGB")`'d, silently
destroying transparency on background-removed PNG outputs.
"""
from PIL import Image

from clean import downscale_output_in_place


def _make_rgba(path, size=(4000, 4000)):
    """Solid-red opaque image with a 200x200 fully-transparent square in the
    top-left corner — lets us read alpha back after resize."""
    img = Image.new("RGBA", size, (255, 0, 0, 255))
    transparent = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
    img.paste(transparent, (0, 0))
    img.save(path)


def test_downscale_preserves_alpha_on_png_output(tmp_path):
    path = tmp_path / "out.png"
    _make_rgba(path)

    new_dims = downscale_output_in_place(path, max_long_edge=2048)

    assert new_dims == "2048x2048"
    with Image.open(path) as im:
        assert im.mode == "RGBA", f"alpha stripped: mode={im.mode}"
        # Top-left was fully transparent; should still be transparent post-resize.
        # (LANCZOS may bleed pixels at the edge, so sample well inside the
        # transparent region.)
        _, _, _, a = im.getpixel((10, 10))
        assert a == 0, f"alpha at (10,10) should be 0, got {a}"


def test_downscale_preserves_alpha_on_webp_output(tmp_path):
    path = tmp_path / "out.webp"
    _make_rgba(path)

    new_dims = downscale_output_in_place(path, max_long_edge=2048)

    assert new_dims == "2048x2048"
    with Image.open(path) as im:
        assert im.mode == "RGBA", f"alpha stripped: mode={im.mode}"
        _, _, _, a = im.getpixel((10, 10))
        assert a == 0


def test_downscale_coerces_rgba_to_rgb_for_jpeg_target(tmp_path):
    """JPEG cannot carry alpha, so RGB coercion IS correct for .jpg outputs."""
    path = tmp_path / "out.jpg"
    # Pillow won't save RGBA directly as JPEG, so we have to start from a
    # mode-RGBA in-memory image and let Pillow do its conversion on save.
    Image.new("RGB", (4000, 4000), (255, 0, 0)).save(path, format="JPEG")

    new_dims = downscale_output_in_place(path, max_long_edge=2048)

    assert new_dims == "2048x2048"
    with Image.open(path) as im:
        assert im.mode == "RGB"


def test_downscale_skipped_when_already_small(tmp_path):
    path = tmp_path / "small.png"
    _make_rgba(path, size=(1024, 768))

    new_dims = downscale_output_in_place(path, max_long_edge=2048)

    assert new_dims is None
    with Image.open(path) as im:
        assert im.size == (1024, 768)
        assert im.mode == "RGBA"


def test_downscale_disabled_with_zero(tmp_path):
    path = tmp_path / "big.png"
    _make_rgba(path)

    new_dims = downscale_output_in_place(path, max_long_edge=0)

    assert new_dims is None
    with Image.open(path) as im:
        assert im.size == (4000, 4000)


def test_downscale_preserves_aspect_ratio_on_portrait(tmp_path):
    path = tmp_path / "portrait.png"
    Image.new("RGBA", (3024, 4032), (0, 255, 0, 255)).save(path)

    new_dims = downscale_output_in_place(path, max_long_edge=2048)

    assert new_dims is not None
    with Image.open(path) as im:
        assert im.size == (round(3024 * 2048 / 4032), 2048)
        assert im.mode == "RGBA"
