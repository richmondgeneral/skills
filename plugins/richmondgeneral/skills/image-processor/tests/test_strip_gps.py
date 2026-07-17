import os
import sys

import piexif
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from PIL import Image
import standardize as st

GPS_IFD = 0x8825


def _gps_dict():
    return {
        piexif.GPSIFD.GPSLatitudeRef: b"N",
        piexif.GPSIFD.GPSLatitude: ((42, 1), (24, 1), (1234, 100)),
        piexif.GPSIFD.GPSLongitudeRef: b"W",
        piexif.GPSIFD.GPSLongitude: ((88, 1), (18, 1), (0, 1)),
    }


def _make_gps_jpeg(path, orientation=None):
    Image.new("RGB", (32, 24), (120, 90, 60)).save(path, "JPEG", quality=90)
    zeroth = {piexif.ImageIFD.Make: b"Apple"}
    if orientation:
        zeroth[piexif.ImageIFD.Orientation] = orientation
    piexif.insert(piexif.dump({"0th": zeroth, "Exif": {}, "GPS": _gps_dict()}), str(path))


def _make_gps_png(path):
    img = Image.new("RGB", (32, 24), (60, 90, 120))
    exif = piexif.dump({"0th": {piexif.ImageIFD.Make: b"Apple"}, "Exif": {}, "GPS": _gps_dict()})
    img.save(path, "PNG", exif=exif)


def _gps(path):
    with Image.open(path) as img:
        return dict(img.getexif().get_ifd(GPS_IFD))


def _pixels(path):
    with Image.open(path) as img:
        return img.tobytes()


def test_strip_gps_jpeg_removes_gps_lossless(tmp_path):
    p = tmp_path / "hero.jpeg"
    _make_gps_jpeg(p)
    assert _gps(p)                       # fixture really has GPS
    before = _pixels(p)
    assert st.strip_gps(p) is True
    assert not _gps(p)
    assert _pixels(p) == before          # scan data untouched (no re-encode)
    # non-GPS EXIF survives
    with Image.open(p) as img:
        assert img.getexif().get(271) == "Apple"


def test_strip_gps_jpeg_keeps_orientation(tmp_path):
    p = tmp_path / "hero.jpeg"
    _make_gps_jpeg(p, orientation=6)
    assert st.strip_gps(p) is True
    with Image.open(p) as img:
        assert img.getexif().get(274) == 6


def test_strip_gps_png_drops_exif_chunk_lossless(tmp_path):
    p = tmp_path / "detail.png"
    _make_gps_png(p)
    assert _gps(p)
    before = _pixels(p)
    assert st.strip_gps(p) is True
    assert not _gps(p)
    assert _pixels(p) == before


def test_strip_gps_noop_when_clean(tmp_path):
    p = tmp_path / "clean.jpeg"
    Image.new("RGB", (16, 16), (10, 20, 30)).save(p, "JPEG")
    before = p.read_bytes()
    assert st.strip_gps(p) is False
    assert p.read_bytes() == before      # untouched files stay byte-identical


def test_dump_sans_gps_drops_malformed_tags():
    # the RG-0055/0062 batch: piexif.load returns tuple MakerNote (37500) and
    # int SceneType (41729) that piexif.dump refuses to re-serialize — the
    # sanitizer must drop the offenders (never the whole file) and still
    # produce GPS-free EXIF bytes.
    d = {
        "0th": {piexif.ImageIFD.Make: b"Apple"},
        "Exif": {37500: (0, 1, 2), 41729: 1, piexif.ExifIFD.LensMake: b"Apple"},
        "GPS": _gps_dict(),
        "1st": {},
        "thumbnail": None,
    }
    out = st._dump_sans_gps(d)
    reloaded = piexif.load(out)
    assert reloaded["GPS"] == {}
    assert reloaded["0th"][piexif.ImageIFD.Make] == b"Apple"
    assert reloaded["Exif"][piexif.ExifIFD.LensMake] == b"Apple"
    assert 37500 not in reloaded["Exif"]


def test_strip_gps_cli(tmp_path, capsys):
    a, b = tmp_path / "a.jpeg", tmp_path / "b.jpeg"
    _make_gps_jpeg(a)
    Image.new("RGB", (16, 16)).save(b, "JPEG")
    rc = st.run_strip_gps([str(a), str(b)])
    assert rc == 0
    assert not _gps(a)
    out = capsys.readouterr().out
    assert "stripped" in out and "clean" in out
