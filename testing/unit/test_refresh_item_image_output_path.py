"""
Tests for cleaned_output_path in refresh_item_image.py — verifies the output
path passed to clean.py preserves the source extension. The pre-fix code
hardcoded `.jpg`, which causes clean.py (infers format from extension) to
silently re-encode PNG/WebP catalog sources as lossy JPEG.
"""
from pathlib import Path

import refresh_item_image as rim


def test_png_source_keeps_png_extension(tmp_path):
    out = rim.cleaned_output_path(
        tmp_path, sku="RG-0042", image_id="IMG_X",
        source_path=Path("/orig/master.png"))
    assert out.suffix == ".png"
    assert out.name == "RG-0042-IMG_X-cleaned.png"


def test_webp_source_keeps_webp_extension(tmp_path):
    out = rim.cleaned_output_path(
        tmp_path, sku="RG-0042", image_id="IMG_X",
        source_path=Path("/orig/master.webp"))
    assert out.suffix == ".webp"


def test_jpg_source_stays_jpg(tmp_path):
    out = rim.cleaned_output_path(
        tmp_path, sku="RG-0042", image_id="IMG_X",
        source_path=Path("/orig/master.jpg"))
    assert out.suffix == ".jpg"


def test_jpeg_source_stays_jpeg(tmp_path):
    out = rim.cleaned_output_path(
        tmp_path, sku="RG-0042", image_id="IMG_X",
        source_path=Path("/orig/master.jpeg"))
    assert out.suffix == ".jpeg"


def test_unfamiliar_extension_falls_back_to_jpg(tmp_path):
    """Square supports more formats than clean.py is tested with; for an
    unknown extension (TIFF, GIF, BMP) we'd rather pick a known-safe target."""
    out = rim.cleaned_output_path(
        tmp_path, sku="RG-0042", image_id="IMG_X",
        source_path=Path("/orig/master.tiff"))
    assert out.suffix == ".jpg"


def test_no_sku_uses_item_prefix(tmp_path):
    out = rim.cleaned_output_path(
        tmp_path, sku=None, image_id="IMG_X",
        source_path=Path("/orig/master.png"))
    assert out.name == "item-IMG_X-cleaned.png"


def test_uppercase_extension_normalized(tmp_path):
    """A .PNG source should still preserve PNG format."""
    out = rim.cleaned_output_path(
        tmp_path, sku="RG-0042", image_id="IMG_X",
        source_path=Path("/orig/master.PNG"))
    assert out.suffix == ".png"
