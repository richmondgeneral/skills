"""Unit tests for sharpen.py's deterministic unsharp path (torch-free).
The --deblur (NAFNet) path needs torch and is validated under the rg-enhance env."""
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import sharpen


def _noise_png(path, seed=0):
    arr = (np.random.RandomState(seed).rand(64, 64, 3) * 255).astype("uint8")
    Image.fromarray(arr).save(path)


def test_unsharp_changes_pixels(tmp_path):
    src = tmp_path / "g.png"
    _noise_png(src)
    out = tmp_path / "o.png"
    sharpen.sharpen_file(str(src), str(out), amount=0.6, deblur=False)
    a0 = np.asarray(Image.open(src).convert("RGB"))
    a1 = np.asarray(Image.open(out).convert("RGB"))
    assert not np.array_equal(a0, a1)            # it did something


def test_unsharp_is_deterministic(tmp_path):
    src = tmp_path / "g.png"
    _noise_png(src)
    o1, o2 = tmp_path / "o1.png", tmp_path / "o2.png"
    sharpen.sharpen_file(str(src), str(o1), amount=0.6, deblur=False)
    sharpen.sharpen_file(str(src), str(o2), amount=0.6, deblur=False)
    a1 = np.asarray(Image.open(o1).convert("RGB"))
    a2 = np.asarray(Image.open(o2).convert("RGB"))
    assert np.array_equal(a1, a2)                # deterministic


def test_unsharp_preserves_dimensions(tmp_path):
    src = tmp_path / "g.png"
    _noise_png(src)
    out = tmp_path / "o.png"
    sharpen.sharpen_file(str(src), str(out), amount=0.6, deblur=False)
    assert Image.open(out).size == Image.open(src).size


def test_sharpen_record_shape(tmp_path):
    src = tmp_path / "g.png"
    _noise_png(src)
    out = tmp_path / "o.png"
    rec = sharpen.sharpen_file(str(src), str(out), amount=0.6, deblur=False)
    assert rec["tool"] == "sharpen.py" and rec["model"] == "unsharp"
    assert rec["amount"] == 0.6
