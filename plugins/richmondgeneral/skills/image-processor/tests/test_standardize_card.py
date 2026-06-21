"""standardize.py golden-card wiring (offline: do_bg=False, transparent input)."""
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import standardize as st


def _transparent_input(path):
    img = Image.new("RGBA", (600, 600), (0, 0, 0, 0))
    img.paste(Image.new("RGBA", (300, 400), (200, 50, 50, 255)), (150, 100))
    img.save(path)


def test_standardize_emits_card_for_cutout(tmp_path):
    src = tmp_path / "hero.png"
    _transparent_input(src)
    out = tmp_path / "hero-std.png"
    st.standardize(str(src), str(out), do_color=False, do_bg=False, do_card=True)
    card = tmp_path / "card.png"
    assert card.exists()
    im = Image.open(card)
    assert im.size == (2000, 1236)


def test_standardize_no_card_when_disabled(tmp_path):
    src = tmp_path / "hero.png"
    _transparent_input(src)
    out = tmp_path / "hero-std.png"
    st.standardize(str(src), str(out), do_color=False, do_bg=False, do_card=False)
    assert not (tmp_path / "card.png").exists()


def test_cli_no_card_flag_parses_false():
    p = st._build_parser()
    assert p.parse_args(["x", "-o", "y"]).do_card is True
    assert p.parse_args(["x", "-o", "y", "--no-card"]).do_card is False
