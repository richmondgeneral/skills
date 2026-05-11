import tempfile
from pathlib import Path

from PIL import Image

from clean import maybe_downscale, DEFAULT_MAX_LONG_EDGE


def test_downscale_shrinks_large_square(tmp_path):
    src = tmp_path / "big.png"
    Image.new("RGB", (4000, 4000), (255, 0, 0)).save(src)

    out = maybe_downscale(src, max_long_edge=2048)

    assert out != src
    assert out.exists()
    with Image.open(out) as im:
        assert im.size == (2048, 2048)
    assert Path(tempfile.gettempdir()) in out.parents
    assert "ds2048" in out.name


def test_downscale_preserves_portrait_aspect(tmp_path):
    src = tmp_path / "portrait.png"
    Image.new("RGB", (3024, 4032), (0, 255, 0)).save(src)

    out = maybe_downscale(src, max_long_edge=2048)

    with Image.open(out) as im:
        w, h = im.size
    assert h == 2048
    assert w == round(3024 * 2048 / 4032)  # 1536


def test_downscale_skipped_when_already_small(tmp_path):
    src = tmp_path / "small.png"
    Image.new("RGB", (1024, 768), (0, 0, 255)).save(src)

    out = maybe_downscale(src, max_long_edge=2048)

    assert out == src


def test_downscale_disabled_with_zero(tmp_path):
    src = tmp_path / "big.png"
    Image.new("RGB", (4000, 4000), (255, 255, 255)).save(src)

    out = maybe_downscale(src, max_long_edge=0)

    assert out == src


def test_downscale_leaves_original_untouched(tmp_path):
    src = tmp_path / "big.png"
    Image.new("RGB", (4000, 4000), (255, 255, 255)).save(src)

    maybe_downscale(src, max_long_edge=2048)

    with Image.open(src) as im:
        assert im.size == (4000, 4000)
