#!/usr/bin/env python3
"""Compose a 1:1 marketplace "combo" collage from an item's hero + detail shots.

Hero-dominant magazine layout: a big hero panel (left ~62%) beside a rail of
auto-selected, captioned detail crops (right ~38%). Square 1600x1600, intended as
a SUPPLEMENTARY marketplace photo (the clean full hero stays primary).

Deterministic, pure-PIL, NON-generative (only crops/scales/composites existing
pixels and draws factual caption text) — safe to run even on labeled goods.

SKIP RULE: needs a hero + >= MIN_DETAILS detail-*.<ext> shots, else compose returns
None and writes nothing (exit code 2 from the CLI — not an error).

CLI:
  combo.py --item-dir items/RG-XXXX [--out combo.png] [--rail 3|4]
           [--caption-mode specific|generic] [--layout magazine]
  combo.py --batch items/            # backfill every items/RG-*/ with enough details
"""
import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(__file__))
from enhance_common import append_pipeline  # reuse the image_pipeline[] recorder

CANVAS = 1600
HERO_FRAC = 0.62
GUTTER = 16
RAIL_DEFAULT = 3
RAIL_MAX = 4
MIN_DETAILS = 3
CREAM = (233, 224, 207)
PANEL_BG = (255, 255, 255)
CAP_SCRIM = (26, 24, 20)
CAP_TEXT = (246, 241, 230)
COMBO_FILENAME = "combo.png"

HERO_NAMES = ("hero.png", "hero.jpg", "hero.jpeg", "hero.webp")
DETAIL_EXTS = (".png", ".jpg", ".jpeg", ".webp")

PROVENANCE = ("maker-mark", "makers-mark", "stamp", "ext-mark", "mark", "signature", "label", "tag")
FEATURE = ("lid", "interior", "mechanism", "control", "dial", "spine", "title", "face", "logo", "front")
CONDITION = ("bottom", "back", "condition", "wear", "profile", "side", "base")

ROLE_DEFAULT_CAPTION = {
    "provenance": "Maker's mark",
    "feature": "Key feature",
    "condition": "Condition",
    "detail": "Detail",
}


def _find_hero(item_dir) -> Optional[Path]:
    for n in HERO_NAMES:
        p = Path(item_dir) / n
        if p.exists():
            return p
    return None


def _details(item_dir) -> list:
    out = []
    for p in sorted(Path(item_dir).iterdir()):
        if p.name.startswith("detail-") and p.suffix.lower() in DETAIL_EXTS:
            out.append(p)
    return out


def _pick(details, used, keys) -> Optional[Path]:
    for k in keys:
        for p in details:
            if p not in used and k in p.stem.lower():
                return p
    return None


def select_slots(item_dir, rail: int = RAIL_DEFAULT, caption_mode: str = "specific") -> Optional[dict]:
    """Map hero + detail-*.<ext> files to slots. None if no hero or < MIN_DETAILS details."""
    item_dir = Path(item_dir)
    hero = _find_hero(item_dir)
    if hero is None:
        return None
    details = _details(item_dir)
    if len(details) < MIN_DETAILS:
        return None
    rail = max(RAIL_DEFAULT, min(rail, RAIL_MAX))

    overrides = {}
    lj = item_dir / "label.json"
    if caption_mode == "specific" and lj.exists():
        try:
            raw = json.loads(lj.read_text(encoding="utf-8")).get("combo_captions")
            overrides = raw if isinstance(raw, dict) else {}
        except Exception:
            overrides = {}

    used, chosen = [], []
    for role, keys in (("provenance", PROVENANCE), ("feature", FEATURE), ("condition", CONDITION)):
        p = _pick(details, used, keys)
        if p is not None:
            used.append(p)
            chosen.append((p, role))
    for p in details:  # fill remaining slots from leftovers, in filename order
        if len(chosen) >= rail:
            break
        if p not in used:
            used.append(p)
            chosen.append((p, "detail"))
    chosen = chosen[:rail]

    out = []
    for p, role in chosen:
        cap = overrides.get(role) or ROLE_DEFAULT_CAPTION.get(role, "Detail")
        out.append({"path": p, "role": role, "caption": cap})
    return {"hero": hero, "rail": out}


def _flatten(img: Image.Image) -> Image.Image:
    """RGB copy; any alpha is composited over PANEL_BG (white) so cutouts don't go black."""
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        bg = Image.new("RGB", rgba.size, PANEL_BG)
        bg.paste(rgba, mask=rgba.split()[-1])
        return bg
    return img.convert("RGB")


def crop_cover(img: Image.Image, w: int, h: int, pos=(0.5, 0.5)) -> Image.Image:
    """Scale-to-cover then crop to exactly w x h (no letterbox). pos = focal fraction."""
    img = _flatten(img)
    sw, sh = img.size
    scale = max(w / sw, h / sh)
    nw, nh = max(1, round(sw * scale)), max(1, round(sh * scale))
    img = img.resize((nw, nh), Image.LANCZOS)
    mx, my = nw - w, nh - h
    x = min(max(0, int(round(mx * pos[0]))), mx)
    y = min(max(0, int(round(my * pos[1]))), my)
    return img.crop((x, y, x + w, y + h))
