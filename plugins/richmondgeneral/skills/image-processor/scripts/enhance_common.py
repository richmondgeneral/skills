#!/usr/bin/env python3
"""Shared, torch-free helpers for the local enhance scripts (upres/sharpen/enhance).

Kept importable WITHOUT torch so the pure logic unit-tests run in the plugin's
3.14 env; the heavy ML imports live in upres.py / sharpen.py behind lazy imports.
"""
from __future__ import annotations

import datetime
import glob
import json
import os


def pick_scale(src_w: int, target_w: int) -> int:
    """Smallest Real-ESRGAN model scale (1/2/4) such that src_w*scale >= target_w.

    Returns 1 to mean "already big enough, skip the model entirely".
    """
    if src_w >= target_w:
        return 1
    need = target_w / src_w
    return 2 if need <= 2 else 4


def resolve_source(item_dir: str, source: str | None) -> str:
    """--source filename within item_dir, else the first hero.{png,jpg,jpeg}."""
    if source:
        return os.path.join(item_dir, source)
    hits = sorted(
        g for g in glob.glob(os.path.join(item_dir, "hero.*"))
        if g.lower().endswith((".png", ".jpg", ".jpeg"))
    )
    if not hits:
        raise FileNotFoundError(f"no hero.* in {item_dir}")
    return hits[0]


def resolve_out(src_path: str, out: str | None, *, suffix: str,
                item_dir: str | None = None) -> str:
    """Safe output path.

    Default = '<stem>.<suffix><ext>' beside the source (NEVER the source itself,
    so a bare run can't clobber the archived original). An explicit --out is
    honored verbatim and MAY overwrite the source when the caller asks for it.
    """
    if out:
        if os.path.isabs(out) or item_dir is None:
            return out
        return os.path.join(item_dir, out)
    stem, ext = os.path.splitext(src_path)
    return f"{stem}.{suffix}{ext or '.png'}"


def append_pipeline(item_dir: str, entry: dict) -> None:
    """Append a reproducibility record to label.json -> image_pipeline[].

    No-op if the item has no label.json (ad-hoc / scratch runs).
    """
    lj = os.path.join(item_dir, "label.json")
    if not os.path.isfile(lj):
        return
    entry.setdefault(
        "timestamp", datetime.datetime.now(datetime.timezone.utc).isoformat())
    entry.setdefault("non_generative", True)
    data = json.load(open(lj, encoding="utf-8"))
    data.setdefault("image_pipeline", []).append(entry)
    with open(lj, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
