"""
Tests for get_mime_type and safe_save_image in image-processor/lib/models/base.py.

safe_save_image is the shared write path that providers use instead of raw
img.save() — it preserves ICC/EXIF on formats that support them, only coerces
mode (RGBA→RGB) when the target format demands it, and never lets the file
extension silently dictate format (the bug class that started this sweep).
"""
import importlib.util
import sys
from pathlib import Path

from PIL import Image


_REPO = Path(__file__).resolve().parent.parent.parent
_MODELS_DIR = _REPO / "image-processor" / "lib" / "models"
if str(_MODELS_DIR) not in sys.path:
    sys.path.insert(0, str(_MODELS_DIR))

_spec = importlib.util.spec_from_file_location("_base_mod", _MODELS_DIR / "base.py")
base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(base)


# ============================================================================
# get_mime_type
# ============================================================================

def test_mime_jpeg_extensions():
    assert base.get_mime_type("foo.jpg") == "image/jpeg"
    assert base.get_mime_type("foo.jpeg") == "image/jpeg"
    assert base.get_mime_type("FOO.JPG") == "image/jpeg"


def test_mime_png():
    assert base.get_mime_type("foo.png") == "image/png"


def test_mime_webp():
    assert base.get_mime_type("foo.webp") == "image/webp"


def test_mime_tiff_both_spellings():
    assert base.get_mime_type("foo.tif") == "image/tiff"
    assert base.get_mime_type("foo.tiff") == "image/tiff"


def test_mime_unknown_extension_falls_back_to_jpeg():
    """Unknown / no-extension is the case Gemini was getting on every call
    before — the safest default is image/jpeg since most endpoints accept it."""
    assert base.get_mime_type("foo.bin") == "image/jpeg"
    assert base.get_mime_type("foo") == "image/jpeg"


# ============================================================================
# safe_save_image — format precedence
# ============================================================================

def test_save_png_extension_writes_png(tmp_path):
    dst = tmp_path / "out.png"
    fmt = base.safe_save_image(Image.new("RGB", (10, 10)), dst)
    assert fmt == "PNG"
    with Image.open(dst) as im:
        assert im.format == "PNG"


def test_save_jpg_extension_writes_jpeg(tmp_path):
    dst = tmp_path / "out.jpg"
    fmt = base.safe_save_image(Image.new("RGB", (10, 10)), dst)
    assert fmt == "JPEG"
    with Image.open(dst) as im:
        assert im.format == "JPEG"


def test_save_explicit_output_format_overrides_extension(tmp_path):
    """If a caller passes output_format='PNG' but the path is .jpg, the
    explicit arg wins (still emits a PNG, even if the filename is misleading)."""
    dst = tmp_path / "out.jpg"
    fmt = base.safe_save_image(Image.new("RGB", (10, 10)), dst,
                               output_format="PNG")
    assert fmt == "PNG"
    with Image.open(dst) as im:
        assert im.format == "PNG"


# ============================================================================
# safe_save_image — alpha handling
# ============================================================================

def test_rgba_to_png_preserves_alpha(tmp_path):
    img = Image.new("RGBA", (10, 10), (255, 0, 0, 0))  # fully transparent red
    dst = tmp_path / "out.png"
    base.safe_save_image(img, dst)
    with Image.open(dst) as out:
        assert out.mode == "RGBA"
        _, _, _, a = out.getpixel((5, 5))
        assert a == 0


def test_rgba_to_jpeg_coerces_to_rgb(tmp_path):
    """JPEG can't carry alpha; safe_save coerces only here, not for PNG/WebP."""
    img = Image.new("RGBA", (10, 10), (255, 0, 0, 255))
    dst = tmp_path / "out.jpg"
    base.safe_save_image(img, dst)
    with Image.open(dst) as out:
        assert out.mode == "RGB"


def test_rgba_to_webp_preserves_alpha(tmp_path):
    img = Image.new("RGBA", (10, 10), (0, 0, 255, 0))
    dst = tmp_path / "out.webp"
    base.safe_save_image(img, dst)
    with Image.open(dst) as out:
        assert out.mode == "RGBA"
        _, _, _, a = out.getpixel((5, 5))
        assert a == 0


# ============================================================================
# safe_save_image — ICC profile preservation
# ============================================================================

def _make_icc_source(tmp_path):
    """Write a small RGB PNG with a fake ICC profile in im.info, then reopen
    it so we have a real on-disk source whose im.info['icc_profile'] is set."""
    src = tmp_path / "src.png"
    img = Image.new("RGB", (40, 40), (128, 128, 128))
    fake_icc = b"\x00\x00\x02\x30fake-icc-payload-for-test"
    img.save(src, format="PNG", icc_profile=fake_icc)
    return src, fake_icc


def test_icc_profile_carries_through_png(tmp_path):
    src, fake_icc = _make_icc_source(tmp_path)
    with Image.open(src) as im:
        source_info = dict(im.info)
        dst = tmp_path / "out.png"
        base.safe_save_image(im, dst, source_info=source_info)
    with Image.open(dst) as out:
        assert out.info.get("icc_profile") == fake_icc


def test_icc_profile_carries_through_jpeg(tmp_path):
    src, fake_icc = _make_icc_source(tmp_path)
    with Image.open(src) as im:
        source_info = dict(im.info)
        dst = tmp_path / "out.jpg"
        base.safe_save_image(im, dst, source_info=source_info)
    with Image.open(dst) as out:
        assert out.info.get("icc_profile") == fake_icc


def test_no_icc_means_no_save_kwarg(tmp_path):
    """If source has no ICC, output also has none — no crash, no fake data."""
    dst = tmp_path / "out.png"
    base.safe_save_image(Image.new("RGB", (10, 10)), dst, source_info={})
    with Image.open(dst) as out:
        assert "icc_profile" not in out.info
