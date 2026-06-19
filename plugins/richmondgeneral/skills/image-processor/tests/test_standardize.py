import argparse
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from PIL import Image, ImageStat
import standardize as st


def test_square_pad_centered_makes_square_and_centers():
    # a 100x40 opaque object placed off-center on a 200x200 transparent canvas
    img = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
    img.paste(Image.new("RGBA", (100, 40), (255, 0, 0, 255)), (10, 80))
    out = st.square_pad_centered(img, fill=1.0, size=0)  # size 0 -> no resize
    assert out.width == out.height                          # square
    assert out.size == (100, 100)                           # side = max(100,40)
    bbox = out.getchannel("A").getbbox()
    cx, cy = (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2
    assert abs(cx - 50) <= 1 and abs(cy - 50) <= 1          # object centered


def test_square_pad_centered_resizes_to_size():
    img = Image.new("RGBA", (50, 50), (0, 255, 0, 255))
    out = st.square_pad_centered(img, fill=0.8, size=512)
    assert out.size == (512, 512)


def test_square_pad_centered_adds_margin():
    img = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
    img.paste(Image.new("RGBA", (60, 60), (0, 0, 255, 255)), (20, 20))
    out = st.square_pad_centered(img, fill=0.5, size=0)
    # side = 60 / 0.5 = 120; object 60 -> padding present
    assert out.size == (120, 120)


def test_gray_world_white_balance_neutralizes_cast():
    img = Image.new("RGB", (64, 64), (200, 120, 120))  # red-tinted gray
    out = st.gray_world_white_balance(img)
    r, g, b = ImageStat.Stat(out).mean
    assert (max(r, g, b) - min(r, g, b)) < (200 - 120)  # cast reduced


def test_color_correct_preserves_mode_and_size():
    img = Image.new("RGB", (32, 48), (180, 100, 90))
    out = st.color_correct(img)
    assert out.size == (32, 48)


def test_color_correct_preserves_transparency():
    img = Image.new("RGBA", (40, 40), (0, 0, 0, 0))
    img.paste(Image.new("RGBA", (20, 20), (200, 100, 90, 255)), (10, 10))
    out = st.color_correct(img)
    assert out.mode == "RGBA"
    assert out.getpixel((0, 0))[3] == 0      # transparent border stays transparent
    assert out.getpixel((20, 20))[3] == 255  # object stays opaque


# ---------------------------------------------------------------------------
# load_item_overrides
# ---------------------------------------------------------------------------

def test_load_item_overrides_missing(tmp_path):
    """No label.json → empty dict, no error."""
    assert st.load_item_overrides(tmp_path) == {}


def test_load_item_overrides_valid(tmp_path):
    (tmp_path / "label.json").write_text(
        json.dumps({"photo_overrides": {"no_color": True, "fill": 0.7, "notes": "antique brass"}})
    )
    result = st.load_item_overrides(tmp_path)
    assert result == {"no_color": True, "fill": 0.7, "notes": "antique brass"}


def test_load_item_overrides_invalid_json(tmp_path, capsys):
    """Malformed JSON → empty dict + warning on stderr."""
    (tmp_path / "label.json").write_text("{not valid json")
    result = st.load_item_overrides(tmp_path)
    assert result == {}
    assert "warning" in capsys.readouterr().err


def test_load_item_overrides_non_dict(tmp_path):
    """JSON that isn't an object → empty dict."""
    (tmp_path / "label.json").write_text("[1, 2, 3]")
    assert st.load_item_overrides(tmp_path) == {}


# ---------------------------------------------------------------------------
# apply_overrides
# ---------------------------------------------------------------------------

def _make_parser_and_defaults():
    """Return (parser, args-at-defaults) for override tests."""
    p = st._build_parser()
    args = p.parse_args(["dummy_input.png", "-o", "out.png"])
    return p, args


def test_apply_overrides_fills_defaults():
    """JSON values apply when CLI left the arg at its default."""
    p, args = _make_parser_and_defaults()
    changed = st.apply_overrides(args, {"no_color": True, "fill": 0.7}, p)
    assert args.no_color is True
    assert abs(args.fill - 0.7) < 1e-9
    assert set(changed) == {"no_color", "fill"}


def test_apply_overrides_cli_wins():
    """An arg set explicitly on the CLI is not overridden by JSON."""
    p = st._build_parser()
    # Simulate user passing --fill 0.9 on CLI
    args = p.parse_args(["dummy_input.png", "-o", "out.png", "--fill", "0.9"])
    changed = st.apply_overrides(args, {"fill": 0.5}, p)
    assert abs(args.fill - 0.9) < 1e-9  # CLI value preserved
    assert "fill" not in changed


def test_apply_overrides_ignores_unknown_keys():
    """Keys not in OVERRIDE_FIELDS (like 'notes') are silently ignored."""
    p, args = _make_parser_and_defaults()
    changed = st.apply_overrides(args, {"notes": "some text", "no_color": True}, p)
    assert "notes" not in changed
    assert "no_color" in changed


def test_apply_overrides_bad_value_warns(capsys):
    """A JSON value that can't be coerced emits a warning and skips the field."""
    p, args = _make_parser_and_defaults()
    original_fill = args.fill
    st.apply_overrides(args, {"fill": "not-a-float"}, p)
    assert args.fill == original_fill  # unchanged
    assert "warning" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# _find_hero
# ---------------------------------------------------------------------------

def test_find_hero_returns_match(tmp_path):
    hero = tmp_path / "hero.jpeg"
    hero.write_bytes(b"fake")
    result = st._find_hero(tmp_path, "hero.*")
    assert result == hero


def test_find_hero_returns_none_when_missing(tmp_path):
    assert st._find_hero(tmp_path, "hero.*") is None


def test_find_hero_ignores_unsupported_extension(tmp_path):
    (tmp_path / "hero.svg").write_bytes(b"fake")
    assert st._find_hero(tmp_path, "hero.*") is None


def test_apply_watermark_composites_bottom_right(tmp_path):
    logo = tmp_path / "logo.png"
    Image.new("RGBA", (50, 50), (255, 0, 0, 255)).save(logo)
    base = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
    out = st.apply_watermark(base, logo_path=str(logo), opacity=1.0, scale=0.2, margin=0.0)
    assert out.size == (200, 200)
    assert out.getpixel((198, 198))[3] > 0   # watermark landed bottom-right
    assert out.getpixel((0, 0))[3] == 0       # top-left untouched

def test_background_reference_white_balance_preserves_patina():
    # A warm object on a neutral gray background.
    # We want to make sure the object STAYS warm (patina preserved).
    img = Image.new("RGBA", (100, 100), (128, 128, 128, 255))
    # Paste a warm amber object in the center
    img.paste(Image.new("RGBA", (40, 40), (200, 140, 40, 255)), (30, 30))
    out = st.background_reference_white_balance(img)
    # The center should still be warm (R > G > B)
    r, g, b, a = out.getpixel((50, 50))
    assert r > g and g > b
    assert r > 150 # Still distinctly warm

def test_background_reference_white_balance_falls_back():
    # A warm object on a completely black background.
    # The dark background should trigger the fallback to gray-world.
    img = Image.new("RGBA", (100, 100), (0, 0, 0, 255))
    img.paste(Image.new("RGBA", (40, 40), (200, 140, 40, 255)), (30, 30))
    out = st.background_reference_white_balance(img)
    # Because it falls back to gray world, the whole image is treated, 
    # so the 200,140,40 is flattened toward gray.
    r, g, b, a = out.getpixel((50, 50))
    assert r < 200 # It got flattened
