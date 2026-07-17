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
# OSD floors to FLAG a mis-oriented hero. Empirically (survey of real heroes):
# UPRIGHT heroes always read rotate=0; truly SIDEWAYS heroes read 90/270 (their
# text runs vertically) — reliable even at low conf (text-sparse Atari labels
# read 0.12–0.19; book covers 1.6–4.7). So for 90/270 a low floor is safe and
# catches the Atari incident. 180° (upside-down) is the UNRELIABLE reading —
# OSD weakly guesses 180 (conf 0.1–0.5) on upright items with symmetric-ish
# label text (false positives on RG-0049/0050/0016/0019) — so 180 needs high
# confidence. No real incident was ever 180°. Locked by monkeypatched tests.
OSD_FLAG_CONF = 0.10      # 90/270 (vertical text) — the RG-0036–0051 mode
OSD_FLIP_CONF = 1.0       # 180 (upside-down) — only when OSD is confident


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
    if osd is not None:
        rot, conf = int(osd["rotate"]), osd["conf"]
        flag = ((rot in (90, 270) and conf >= OSD_FLAG_CONF) or
                (rot == 180 and conf >= OSD_FLIP_CONF))
        if flag:
            return {"ok": False, "method": "osd",
                    "reason": f"text rotated {rot}° (OSD conf {conf:.2f})"}
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
    """Only fails the one unambiguous wrong-treatment case: a FLAT-goods hero
    shipped as a transparent cutout (flat goods must be an opaque full-bleed
    face crop). An opaque hero is ALWAYS acceptable — we deliberately do NOT
    require transparency for cutout/unknown items. That absolute "hero must be
    transparent" rule is exactly what drove RG-0031 (postmortem A1 reversed it)
    and would false-fail the many legitimately-opaque photo heroes in the
    catalog. The gate's job is geometry/orientation defects, not cutout aesthetics."""
    _, alpha = _imread(hero_path)
    has_transp = alpha is not None and bool((alpha < 250).any())
    if item_class == "flat" and has_transp:
        return {"ok": False,
                "reason": "flat-goods hero must be opaque full-bleed, not a cutout"}
    return {"ok": True}


DEFECT_MIN_RETENTION = 0.40


def _edge_density(bgr) -> float:
    g = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    return float((cv2.Canny(cv2.GaussianBlur(g, (5, 5), 0), 40, 120) > 0).mean())


def check_defects(hero_path: str, original_path: Optional[str] = None) -> Dict[str, Any]:
    """Soft guard against over-cleaning (RG-0030 hallucinated-clean). Only active
    with an original; fails ONLY on extreme detail loss so honest cleanups pass."""
    if not original_path or not os.path.exists(original_path):
        return {"ok": True, "reason": "not_compared"}
    hb, _ = _imread(hero_path)
    ob, _ = _imread(original_path)
    if hb is None or ob is None:
        return {"ok": True, "reason": "not_compared"}
    od = _edge_density(ob)
    if od < 1e-4:
        return {"ok": True, "reason": "original_featureless"}
    retention = _edge_density(hb) / od
    if retention < DEFECT_MIN_RETENTION:
        return {"ok": False,
                "reason": f"detail retention {retention:.0%} < {DEFECT_MIN_RETENTION:.0%} (over-cleaned?)"}
    return {"ok": True, "retention": round(retention, 2)}


def check_level(hero_path: str) -> Dict[str, Any]:
    """Fail if the dominant object is tilted > TILT_MAX_DEG with a trustworthy
    reading (confidence >= TILT_MIN_CONF). Mirrors the validated prototype gate.

    RADIAL-SYMMETRY SKIP (added 2026-06-20, RG-0023): a radially symmetric
    subject (starburst brooch, round medallion, floral/sunburst pin, circular
    plate) has NO dominant orientation axis, so the min-area-rect / PCA tilt is
    meaningless garbage — the real RG-0023 Weiss starburst brooch read 41.6°
    while visually dead-straight, false-failing this check and blocking publish.
    residual_tilt_deg now probes rotational self-similarity on the same object
    mask; when it reports `radial_symmetric`, we mark level N/A (pass) with a
    recorded reason instead of penalising the garbage angle. Clearly-oriented
    (non-symmetric) items still fail when genuinely crooked."""
    bgr, alpha = _imread(hero_path)
    if bgr is None:
        return {"ok": False, "level_deg": None, "reason": "unreadable_hero"}
    r = residual_tilt_deg(bgr, alpha)
    tilt, conf = r["tilt_deg"], r["confidence"]
    if r.get("radial_symmetric"):
        return {"ok": True, "level_deg": tilt, "confidence": conf,
                "level_skipped_radial_symmetry": True,
                "symmetry_max_iou": r.get("symmetry_max_iou"),
                "note": ("level N/A — radially symmetric subject (no orientation "
                         f"axis); tilt reading {tilt}° is not meaningful "
                         f"(rotational self-overlap max IoU "
                         f"{r.get('symmetry_max_iou')})")}
    failed = (tilt > TILT_MAX_DEG) and (conf >= TILT_MIN_CONF)
    out = {"ok": not failed, "level_deg": tilt, "confidence": conf}
    if failed:
        out["reason"] = f"tilt {tilt:.1f}° > {TILT_MAX_DEG}°"
    return out


# Profile (from standardize/photo-profiles) -> gate item-class.
_PROFILE_CLASS = {"flat-goods": "flat", "keep-bg": "keepbg",
                  "standard": "cutout", "true-color": "cutout", "manual": "cutout"}


def resolve_item_class(item_dir: str) -> str:
    """Map the item's photo profile (inferred from label.json the same way
    standardize.py does) to a gate class: flat | keepbg | cutout."""
    label: Dict[str, Any] = {}
    p = Path(item_dir) / "label.json"
    if p.exists():
        try:
            label = json.loads(p.read_text())
        except Exception:
            label = {}
    try:
        import standardize as st
        profiles = st.load_photo_profiles()
        profile = st.resolve_profile(label, profiles) if profiles else "standard"
    except Exception:
        profile = "standard"
    return _PROFILE_CLASS.get(profile, "cutout")


def hero_qa_gate(hero_path: str, original_path: Optional[str] = None,
                 item_class: Optional[str] = None) -> Dict[str, Any]:
    """Run all five checks and return {status, checked_at, checker, item_class,
    checks, reasons}. status == 'fail' if any hard check fails (defects is soft
    but does fail on the extreme over-clean threshold)."""
    item_class = item_class or "cutout"
    up = check_upright(hero_path, original_path)
    lv = check_level(hero_path)
    ff = check_full_face(hero_path, item_class)
    bg = check_bg(hero_path, item_class)
    df = check_defects(hero_path, original_path)
    checks = {"upright": up["ok"], "level_deg": lv.get("level_deg"),
              "full_face": ff["ok"], "bg_ok": bg["ok"], "defects_ok": df["ok"]}
    if lv.get("level_skipped_radial_symmetry"):
        checks["level_skipped_radial_symmetry"] = True
    reasons = [c["reason"] for c in (up, lv, ff, bg, df)
               if not c["ok"] and c.get("reason")]
    hard_ok = up["ok"] and lv["ok"] and ff["ok"] and bg["ok"] and df["ok"]
    return {"status": "pass" if hard_ok else "fail",
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "checker": CHECKER, "item_class": item_class,
            "checks": checks, "reasons": reasons}


# --------------------------------------------------------------------------
# CLI / item-directory layer
# --------------------------------------------------------------------------
def find_hero(item_dir: str) -> Optional[str]:
    for name in ("hero.png", "hero.jpg", "hero.jpeg", "hero.webp"):
        p = Path(item_dir) / name
        if p.exists():
            return str(p)
    cand = sorted(Path(item_dir).glob("hero.*"))
    return str(cand[0]) if cand else None


def _write_hero_qa(item_dir: str, verdict: Dict[str, Any]) -> None:
    """Persist the verdict into label.json -> hero_qa (atomic tmp+rename),
    preserving all other fields. A fail also flips photo_overrides.status."""
    p = Path(item_dir) / "label.json"
    d = json.loads(p.read_text()) if p.exists() else {}
    d["hero_qa"] = {k: verdict[k] for k in
                    ("status", "checked_at", "checker", "checks", "reasons")}
    if verdict["status"] == "fail":
        d.setdefault("photo_overrides", {})["status"] = "needs_manual"
    else:
        # Idempotent: clear a stale gate-set needs_manual now that it passes,
        # without disturbing other photo_overrides keys.
        po = d.get("photo_overrides")
        if isinstance(po, dict) and po.get("status") == "needs_manual":
            po.pop("status", None)
            if not po:
                d.pop("photo_overrides", None)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(d, indent=2))
    tmp.replace(p)


def run_item(item_dir: str, write: bool = True,
             original_path: Optional[str] = None) -> int:
    """Gate one item dir. Returns 0 pass / 1 fail / 2 no-hero."""
    hero = find_hero(item_dir)
    if not hero:
        print(f"  ✗ {Path(item_dir).name}: no hero image found", file=sys.stderr)
        return 2
    verdict = hero_qa_gate(hero, original_path, resolve_item_class(item_dir))
    if write:
        _write_hero_qa(item_dir, verdict)
    tag = "✓ pass" if verdict["status"] == "pass" else "✗ FAIL"
    extra = f"  — {'; '.join(verdict['reasons'])}" if verdict["reasons"] else ""
    print(f"  {tag}  {Path(item_dir).name}{extra}")
    return 0 if verdict["status"] == "pass" else 1


def run_batch(items_root: str, write: bool = True, as_json: bool = False) -> int:
    """Gate every RG-* under items_root, writing each hero_qa. Returns 1 if any
    currently-Listed item FAILS (the blocking audit signal), else 0."""
    root = Path(items_root)
    item_dirs = sorted(d for d in root.glob("RG-*")
                       if (d / "label.json").exists() or list(d.glob("hero.*")))
    listed_fail = 0
    rows = []
    for d in item_dirs:
        hero = find_hero(str(d))
        label: Dict[str, Any] = {}
        lp = d / "label.json"
        if lp.exists():
            try:
                label = json.loads(lp.read_text())
            except Exception:
                pass
        state = label.get("state", "?")
        if not hero:
            rows.append((d.name, "no-hero", state, ""))
            continue
        verdict = hero_qa_gate(hero, None, resolve_item_class(str(d)))
        if write:
            _write_hero_qa(str(d), verdict)
        if verdict["status"] == "fail" and state == "Listed":
            listed_fail += 1
        rows.append((d.name, verdict["status"], state, "; ".join(verdict["reasons"])))
    if as_json:
        print(json.dumps([{"sku": s, "status": st, "state": stt, "reasons": r}
                          for s, st, stt, r in rows], indent=2))
    else:
        print(f"\nHero QA audit — {len(rows)} items:")
        for sku, status, state, note in rows:
            mark = "✓" if status == "pass" else ("∅" if status == "no-hero" else "✗")
            tail = f"  [{state}] {note}" if note else f"  [{state}]"
            print(f"  {mark} {sku:<10} {status:<7}{tail}")
        print(f"\n⚠ {listed_fail} currently-Listed item(s) FAIL the gate."
              if listed_fail else "\n✓ All Listed items pass the gate.")
    return 1 if listed_fail else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Pre-publish Hero QA gate")
    ap.add_argument("path", help="items/RG-XXXX dir (or items/ root with --batch)")
    ap.add_argument("--batch", action="store_true",
                    help="run over every RG-* under path (back-fill / audit)")
    ap.add_argument("--no-write", action="store_true",
                    help="do not modify label.json")
    ap.add_argument("--original", help="original photo for the defect comparison")
    ap.add_argument("--json", action="store_true", help="emit machine JSON")
    a = ap.parse_args()
    if a.batch:
        return run_batch(a.path, write=not a.no_write, as_json=a.json)
    if a.json:
        hero = find_hero(a.path)
        verdict = (hero_qa_gate(hero, a.original, resolve_item_class(a.path))
                   if hero else {"status": "fail", "reasons": ["no hero image"]})
        print(json.dumps(verdict, indent=2))
        return 0 if verdict.get("status") == "pass" else 1
    return run_item(a.path, write=not a.no_write, original_path=a.original)


if __name__ == "__main__":
    sys.exit(main())
