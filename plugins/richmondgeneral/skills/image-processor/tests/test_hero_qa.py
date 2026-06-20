"""Tests for the pre-publish Hero QA gate (hero_qa.py).

Fixtures are self-generated (the RG-0031 prototype imgs are not on disk):
  - _rect_alpha(angle): an RGBA cutout whose alpha is a filled rect rotated by
    `angle` — the deterministic alpha path (mirrors the RG-0031 crooked cutout).
  - _text_hero_bgr(): real rendered text for tesseract OSD upright tests.
  - _straight_book_bgr(): a geometric opaque 'cover' for bg/full-face tests.
"""
import os
import sys
import json

import numpy as np
import cv2
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import hero_qa as hq

FIX = os.path.join(os.path.dirname(__file__), "_fixtures")


def _save_png(name, bgr, alpha=None):
    os.makedirs(FIX, exist_ok=True)
    path = os.path.join(FIX, name)
    if alpha is not None:
        bgra = cv2.cvtColor(bgr, cv2.COLOR_BGR2BGRA)
        bgra[:, :, 3] = alpha
        cv2.imwrite(path, bgra)
    else:
        cv2.imwrite(path, bgr)
    return path


def _rect_alpha(angle=0, size=400, rw=180, rh=300):
    """RGBA: a filled rectangle (dark on light) whose alpha is rotated `angle`°."""
    bgr = np.full((size, size, 3), 200, np.uint8)
    alpha = np.zeros((size, size), np.uint8)
    x0, y0 = size // 2 - rw // 2, size // 2 - rh // 2
    cv2.rectangle(alpha, (x0, y0), (x0 + rw, y0 + rh), 255, -1)
    if angle:
        M = cv2.getRotationMatrix2D((size / 2, size / 2), angle, 1.0)
        alpha = cv2.warpAffine(alpha, M, (size, size))
    bgr[alpha > 0] = (60, 60, 60)
    return bgr, alpha


def _straight_book_bgr():
    """Opaque portrait 'cover' with horizontal bars (full-bleed by design)."""
    img = np.full((480, 320, 3), 235, np.uint8)
    cv2.rectangle(img, (8, 8), (311, 471), (40, 40, 40), 6)
    for y in (90, 150, 210, 330):
        cv2.rectangle(img, (40, y), (280, y + 22), (30, 30, 30), -1)
    return img


def _text_hero_bgr():
    """Render real multi-line text (dark on white) for tesseract OSD tests."""
    from PIL import Image, ImageDraw, ImageFont
    W, H = 360, 480
    img = Image.new("RGB", (W, H), (245, 245, 245))
    d = ImageDraw.Draw(img)
    font = None
    for fp in ("/System/Library/Fonts/Supplemental/Arial.ttf",
               "/System/Library/Fonts/Helvetica.ttc",
               "/Library/Fonts/Arial.ttf"):
        if os.path.exists(fp):
            font = ImageFont.truetype(fp, 34)
            break
    if font is None:
        font = ImageFont.load_default()
    lines = ["THE SANDS", "OF MARS", "a novel by", "ARTHUR C", "CLARKE", "pocket books"]
    y = 60
    for ln in lines:
        d.text((40, y), ln, fill=(20, 20, 20), font=font)
        y += 60
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


# --------------------------------------------------------------------------
# Task 2 — level check
# --------------------------------------------------------------------------
def test_level_pass_on_straight_cutout():
    bgr, alpha = _rect_alpha(angle=0)
    p = _save_png("level_straight.png", bgr, alpha)
    r = hq.check_level(p)
    assert r["ok"] is True
    assert r["level_deg"] <= 1.5


def test_level_fail_on_16deg_tilt():
    bgr, alpha = _rect_alpha(angle=16)
    p = _save_png("level_tilt16.png", bgr, alpha)
    r = hq.check_level(p)
    assert r["ok"] is False
    assert r["level_deg"] > 1.5
