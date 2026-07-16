"""GPS scrub at the sips-export ingest point (the 2026-07-15 leak: 130 published
images carried iPhone GPS EXIF because file_cluster exported originals verbatim).

file_cluster runs over the bare bridge (stdlib python3), so its scrub is a
stdlib in-place GPS-IFD wipe — no piexif at runtime. piexif/Pillow are used
here only to BUILD fixtures and to verify."""
import os
import shutil
import sys

import piexif
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import file_cluster as fc

GPS_IFD = 0x8825


def _make_gps_jpeg(path, orientation=6):
    Image.new("RGB", (32, 24), (120, 90, 60)).save(path, "JPEG", quality=90)
    exif = piexif.dump({
        "0th": {piexif.ImageIFD.Make: b"Apple", piexif.ImageIFD.Orientation: orientation},
        "Exif": {piexif.ExifIFD.LensMake: b"Apple"},
        "GPS": {
            piexif.GPSIFD.GPSLatitudeRef: b"N",
            piexif.GPSIFD.GPSLatitude: ((42, 1), (24, 1), (1234, 100)),
            piexif.GPSIFD.GPSLongitudeRef: b"W",
            piexif.GPSIFD.GPSLongitude: ((88, 1), (18, 1), (0, 1)),
        },
    })
    piexif.insert(exif, str(path))


def test_wipe_gps_jpeg_inplace(tmp_path):
    p = tmp_path / "detail-1.jpeg"
    _make_gps_jpeg(p)
    size = p.stat().st_size
    with Image.open(p) as img:
        before_pixels = img.tobytes()
        assert img.getexif().get_ifd(GPS_IFD)          # fixture has GPS

    assert fc.wipe_gps_jpeg(str(p)) is True

    assert p.stat().st_size == size                    # in-place: byte length unchanged
    with Image.open(p) as img:
        assert not img.getexif().get_ifd(GPS_IFD)      # GPS gone
        assert img.getexif().get(274) == 6             # orientation kept
        assert img.getexif().get(271) == "Apple"       # other EXIF kept
        assert img.tobytes() == before_pixels          # pixels untouched


def test_wipe_gps_jpeg_zeroes_value_bytes(tmp_path):
    # distinctive rational 987654321/1 — its 4-byte encoding must not survive
    p = tmp_path / "x.jpeg"
    Image.new("RGB", (8, 8)).save(p, "JPEG")
    piexif.insert(piexif.dump({
        "0th": {}, "Exif": {},
        "GPS": {piexif.GPSIFD.GPSAltitude: (987654321, 1)},
    }), str(p))
    marker_be = (987654321).to_bytes(4, "big")
    marker_le = (987654321).to_bytes(4, "little")
    assert marker_be in p.read_bytes() or marker_le in p.read_bytes()
    assert fc.wipe_gps_jpeg(str(p)) is True
    raw = p.read_bytes()
    assert marker_be not in raw and marker_le not in raw


def test_wipe_gps_jpeg_noop_when_clean(tmp_path):
    p = tmp_path / "clean.jpeg"
    Image.new("RGB", (8, 8)).save(p, "JPEG")
    before = p.read_bytes()
    assert fc.wipe_gps_jpeg(str(p)) is False
    assert p.read_bytes() == before


def test_wipe_gps_jpeg_nonfatal_on_garbage(tmp_path):
    p = tmp_path / "not-a.jpeg"
    p.write_bytes(b"definitely not a jpeg")
    assert fc.wipe_gps_jpeg(str(p)) is False           # never raises, never blocks filing


def test_sips_convert_scrubs_gps(tmp_path, monkeypatch):
    """The wiring: every sips export is followed by the GPS wipe."""
    src = tmp_path / "original.jpeg"
    _make_gps_jpeg(src)
    dst = tmp_path / "hero.jpeg"

    def fake_run(cmd, stage=None):
        assert cmd[0] == "sips"
        shutil.copyfile(cmd[-3], cmd[-1])              # sips src --out dst
    monkeypatch.setattr(fc, "_run", fake_run)

    fc.sips_convert(str(src), str(dst))
    with Image.open(dst) as img:
        assert not img.getexif().get_ifd(GPS_IFD)
