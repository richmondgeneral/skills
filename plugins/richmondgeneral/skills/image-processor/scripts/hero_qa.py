#!/usr/bin/env python3
"""hero_qa.py — blocking pre-publish Hero QA gate.

Checks a hero against the three historical failure modes (90° rotation,
>1.5° tilt, clipped face) plus background-by-class and over-clean defects,
then writes the verdict to items/RG-XXXX/label.json -> hero_qa. No item may
publish / go Listed without hero_qa.status == "pass".

Reuses the already-landed deskew.residual_tilt_deg (image-processor scripts/)
for the level check. Run via the plugin-root uv env:
  uv run --project <plugin-root> python scripts/hero_qa.py items/RG-XXXX
  uv run --project <plugin-root> python scripts/hero_qa.py --batch items/

History: RG-0031 (crooked cutout) + Atari RG-0036–0051 (90° rotation) +
RG-0030 (over-clean) postmortems, 2026-06-20.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

sys.path.insert(0, os.path.dirname(__file__))  # deskew.py, standardize.py (same dir)

import cv2
import numpy as np
from deskew import residual_tilt_deg

CHECKER = "auto:hero_qa_gate v1"
TILT_MAX_DEG = 1.5
TILT_MIN_CONF = 0.5
# OSD orientation_conf floor to FLAG a sideways hero. Measured: synthetic text
# reads 0.78–1.05 across 90/180/270; real covers/labels read higher. 0.5 catches
# all of them with margin. Bias is intentional — a false positive routes a hero
# to manual review (cheap); a false negative ships sideways (the incident).
OSD_FLAG_CONF = 0.5


def _imread(path: str):
    """Return (bgr, alpha|None). alpha present only for RGBA inputs."""
    bgr = cv2.imread(path)
    raw = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    alpha = (raw[:, :, 3]
             if raw is not None and raw.ndim == 3 and raw.shape[2] == 4
             else None)
    return bgr, alpha


def _osd_rotation(bgr) -> Optional[Dict[str, float]]:
    """Tesseract OSD: {'rotate': 0/90/180/270, 'conf': float} or None if OSD
    is unavailable (no binary / too little text / error)."""
    try:
        import pytesseract
        from PIL import Image
        pytesseract.get_tesseract_version()          # raises if binary missing
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        osd = pytesseract.image_to_osd(Image.fromarray(rgb),
                                       output_type=pytesseract.Output.DICT)
        return {"rotate": float(osd.get("rotate", 0)),
                "conf": float(osd.get("orientation_conf", 0))}
    except Exception:
        return None


def _exif_orientation(path: str) -> Optional[int]:
    try:
        from PIL import Image
        return Image.open(path).getexif().get(0x0112)   # Orientation tag
    except Exception:
        return None


def check_upright(hero_path: str, original_path: Optional[str] = None) -> Dict[str, Any]:
    """Fail only on a POSITIVE sideways signal — OSD says the text is rotated
    90/180/270 (catches the Atari batch), or (fallback) the source EXIF says it
    needed rotation that was never baked into the hero. 'unknown' never fails."""
    bgr, _ = _imread(hero_path)
    if bgr is None:
        return {"ok": False, "reason": "unreadable_hero", "method": "none"}
    osd = _osd_rotation(bgr)
    if osd is not None and int(osd["rotate"]) in (90, 180, 270) and osd["conf"] >= OSD_FLAG_CONF:
        return {"ok": False, "method": "osd",
                "reason": f"text rotated {int(osd['rotate'])}° (OSD conf {osd['conf']:.2f})"}
    # Fallback: positive 'orientation not baked' signal from the source only.
    if original_path:
        ori = _exif_orientation(original_path)
        if ori in (5, 6, 7, 8):                       # source needed a 90/270 rotation
            src, _ = _imread(original_path)
            if src is not None:
                h, w = bgr.shape[:2]
                sh, sw = src.shape[:2]
                if (w > h) == (sw > sh):              # hero kept the un-baked aspect
                    return {"ok": False, "method": "exif_fallback",
                            "reason": f"source EXIF orientation {ori} not baked into hero"}
    method = "osd" if osd is not None else "no_osd"
    return {"ok": True, "method": method}


BORDER_RING_FRAC = 0.01   # how close to the edge counts as 'touching'


def check_full_face(hero_path: str, item_class: str = "cutout") -> Dict[str, Any]:
    """Cutout heroes must float clear of every border (catches the RG-0031
    corner clip). Flat-goods / keep-bg are full-frame by design — lenient."""
    bgr, alpha = _imread(hero_path)
    if bgr is None:
        return {"ok": False, "reason": "unreadable_hero"}
    if item_class in ("flat", "keepbg"):
        return {"ok": True, "method": "fullbleed_lenient"}
    if alpha is None:
        return {"ok": True, "method": "no_alpha"}     # not a cutout; nothing to clip
    h, w = alpha.shape[:2]
    ys, xs = np.where(alpha > 8)
    if len(xs) == 0:
        return {"ok": False, "reason": "empty_alpha"}
    ring = max(1, int(min(h, w) * BORDER_RING_FRAC))
    touches = (xs.min() <= ring or ys.min() <= ring or
               xs.max() >= w - 1 - ring or ys.max() >= h - 1 - ring)
    if touches:
        return {"ok": False, "method": "alpha_bbox",
                "reason": "subject clipped at frame edge"}
    return {"ok": True, "method": "alpha_bbox"}


def check_bg(hero_path: str, item_class: str = "cutout") -> Dict[str, Any]:
    """Cutout heroes must have a real transparent background; flat-goods must be
    opaque full-bleed; keep-bg (glass/silver on its setting) is lenient."""
    _, alpha = _imread(hero_path)
    has_transp = alpha is not None and bool((alpha < 250).any())
    if item_class == "keepbg":
        return {"ok": True, "method": "keepbg_lenient"}
    if item_class == "flat":
        if has_transp:
            return {"ok": False,
                    "reason": "flat-goods hero must be opaque full-bleed, not a cutout"}
        return {"ok": True}
    if not has_transp:                                 # cutout class
        return {"ok": False, "reason": "cutout hero has no transparent background"}
    return {"ok": True}


def check_level(hero_path: str) -> Dict[str, Any]:
    """Fail if the dominant object is tilted > TILT_MAX_DEG with a trustworthy
    reading (confidence >= TILT_MIN_CONF). Mirrors the validated prototype gate."""
    bgr, alpha = _imread(hero_path)
    if bgr is None:
        return {"ok": False, "level_deg": None, "reason": "unreadable_hero"}
    r = residual_tilt_deg(bgr, alpha)
    tilt, conf = r["tilt_deg"], r["confidence"]
    failed = (tilt > TILT_MAX_DEG) and (conf >= TILT_MIN_CONF)
    out = {"ok": not failed, "level_deg": tilt, "confidence": conf}
    if failed:
        out["reason"] = f"tilt {tilt:.1f}° > {TILT_MAX_DEG}°"
    return out
