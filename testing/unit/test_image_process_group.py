from pathlib import Path

from PIL import Image

from process_group import build_output_path, discover_images, has_transparency


def test_discover_images_excludes_qr_and_existing_nobg(tmp_path):
    (tmp_path / "hero.jpg").write_bytes(b"x")
    (tmp_path / "IMG_0001.jpg").write_bytes(b"x")
    (tmp_path / "qr-code.png").write_bytes(b"x")
    (tmp_path / "IMG_0001-nobg.png").write_bytes(b"x")

    files = discover_images(
        input_dir=tmp_path,
        recursive=False,
        include_patterns=[],
        exclude_patterns=["qr-code*", "*label*", "* -not-used*"],
        suffix="-nobg",
    )

    names = [f.name for f in files]
    assert "hero.jpg" in names
    assert "IMG_0001.jpg" in names
    assert "qr-code.png" not in names
    assert "IMG_0001-nobg.png" not in names


def test_build_output_path_preserves_subdirs(tmp_path):
    input_dir = tmp_path / "in"
    output_dir = tmp_path / "out"
    source = input_dir / "details" / "IMG_0002.jpg"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"x")

    out = build_output_path(source, input_dir, output_dir, "-nobg")

    assert out == output_dir / "details" / "IMG_0002-nobg.png"
    assert out.parent.exists()


def test_has_transparency_detects_alpha(tmp_path):
    transparent = tmp_path / "transparent.png"
    opaque = tmp_path / "opaque.png"

    Image.new("RGBA", (2, 2), (255, 255, 255, 0)).save(transparent)
    Image.new("RGB", (2, 2), (255, 255, 255)).save(opaque)

    assert has_transparency(transparent) is True
    assert has_transparency(opaque) is False
