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


def _imread(path: str):
    """Return (bgr, alpha|None). alpha present only for RGBA inputs."""
    bgr = cv2.imread(path)
    raw = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    alpha = (raw[:, :, 3]
             if raw is not None and raw.ndim == 3 and raw.shape[2] == 4
             else None)
    return bgr, alpha


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
