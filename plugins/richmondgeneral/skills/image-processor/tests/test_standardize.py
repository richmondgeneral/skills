import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from PIL import Image, ImageStat
import standardize as st


def test_square_pad_centered_makes_square_and_centers():
    # a 100x40 opaque object placed off-center on a 200x200 transparent canvas
    img = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
    img.paste(Image.new("RGBA", (100, 40), (255, 0, 0, 255)), (10, 80))
    out = st.square_pad_centered(img, margin=0.0, size=0)  # size 0 -> no resize
    assert out.width == out.height                          # square
    assert out.size == (100, 100)                           # side = max(100,40)
    bbox = out.getchannel("A").getbbox()
    cx, cy = (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2
    assert abs(cx - 50) <= 1 and abs(cy - 50) <= 1          # object centered


def test_square_pad_centered_resizes_to_size():
    img = Image.new("RGBA", (50, 50), (0, 255, 0, 255))
    out = st.square_pad_centered(img, margin=0.1, size=512)
    assert out.size == (512, 512)


def test_square_pad_centered_adds_margin():
    img = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
    img.paste(Image.new("RGBA", (60, 60), (0, 0, 255, 255)), (20, 20))
    out = st.square_pad_centered(img, margin=0.25, size=0)
    # side = 60 * (1 + 0.5) = 90; object 60 -> padding present
    assert out.size == (90, 90)


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
