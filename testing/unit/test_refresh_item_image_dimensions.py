"""
Tests for the file-output dimension parser in refresh_item_image.py.

Bug: the regex `(\\d+)\\s*x\\s*(\\d+)` matches the JFIF density field
("density 1x1") before the real dimensions ("1500x2000") because density
appears first in `file` output. Fix: pick the largest WxH match by area.
"""
import refresh_item_image as rim


def test_jfif_density_1x1_is_ignored_in_favor_of_real_dims():
    """The bug: 'density 1x1, ... 1500x2000' must return 1500x2000."""
    line = ("rot-cover.jpg: JPEG image data, JFIF standard 1.01, aspect ratio, "
            "density 1x1, segment length 16, baseline, precision 8, "
            "1500x2000, components 3")
    assert rim.parse_dimensions(line) == "1500x2000"


def test_simple_single_dim_returned():
    line = "img.png: PNG image data, 640 x 480, 8-bit/color RGB, non-interlaced"
    assert rim.parse_dimensions(line) == "640x480"


def test_returns_none_when_no_dimensions_present():
    assert rim.parse_dimensions("foo: some other file type") is None
    assert rim.parse_dimensions("") is None


def test_picks_largest_when_multiple_candidates():
    # If two candidates both look real, prefer the larger by area.
    line = "weird.jpg: JPEG ... 100x200, ... 3000x4000, ..."
    assert rim.parse_dimensions(line) == "3000x4000"
