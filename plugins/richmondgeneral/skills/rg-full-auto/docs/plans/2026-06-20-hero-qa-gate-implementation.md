# Pre-publish Hero QA Gate — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** A blocking pre-publish gate that stops a hero from being committed/published/`Listed` unless it passes upright, level, full-face, background, and defect checks — catching the RG-0030/RG-0031/Atari failure modes.

**Architecture:** New self-contained `image-processor/scripts/hero_qa.py` (gate engine + CLI) reuses the already-landed `deskew.residual_tilt_deg` for the level check, adds a tesseract-OSD upright check (deterministic fallback), class-aware full-face/background checks, and a soft defect check. It writes a `hero_qa` block to `label.json`. The rg-full-auto pipeline (`process_batch.py`) subprocesses the CLI before the publish phases; `item_state.can_list()` reads the verdict and blocks `phase_4`/`phase_7`. A `bake_orientation()` add to `standardize.py` fixes the orientation-not-baked root cause.

**Tech Stack:** Python 3.14 (`uv`), OpenCV (`deskew.py`, already a dep), `pytesseract` (new dep, tesseract binary present), Pillow, pytest.

**Conventions for every task below:**
- `PROJ=/Users/scottybe/workspace/richmondgeneral/skills/plugins/richmondgeneral`
- Run tests: `uv run --project $PROJ pytest <path> -v`
- Run CLI: `uv run --project $PROJ python <script> <args>`
- **Before EVERY `git commit`** (shared `skills/` checkout, active parallel agent): `cd /Users/scottybe/workspace/richmondgeneral/skills && git rev-parse --abbrev-ref HEAD` must print `main`; `git add <explicit paths only>` (never `-A`); verify `git diff --cached --name-only` lists only your files; then commit with the `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>` trailer.
- **Dual-copy:** all `skills/...` edits are mirrored to `~/.claude/plugins/cache/richmondgeneral/skills/...` in Task 11 (one rsync), then validated. Do not hand-edit the cache.

---

### Task 1: Add `pytesseract` dependency + OSD smoke check

**Files:**
- Modify: `plugins/richmondgeneral/pyproject.toml` (dependencies array)
- Test: `plugins/richmondgeneral/skills/image-processor/tests/test_hero_qa.py` (new)

**Step 1 — add the dep.** In `pyproject.toml` `dependencies`, add `"pytesseract>=0.3.10"` next to `opencv-python-headless`/`numpy`. Then `uv lock --project $PROJ` to refresh `uv.lock`.

**Step 2 — verify the env.** Run:
```
uv run --project $PROJ python -c "import cv2,numpy,pytesseract; print(pytesseract.get_tesseract_version())"
```
Expected: prints a tesseract version (e.g. `5.x`). If `get_tesseract_version()` raises, the binary is missing — the gate must still import (OSD guarded); note it and continue.

**Step 3 — commit.**
```
git add plugins/richmondgeneral/pyproject.toml plugins/richmondgeneral/uv.lock
git commit -m "build(image-processor): add pytesseract for hero-QA OSD upright check"
```

---

### Task 2: `hero_qa.py` skeleton + level check (reuse `deskew`)

**Files:**
- Create: `plugins/richmondgeneral/skills/image-processor/scripts/hero_qa.py`
- Test: `plugins/richmondgeneral/skills/image-processor/tests/test_hero_qa.py`

**Step 1 — failing test.** Create the test file with shared fixtures (used by later tasks too):

```python
import os, sys, json
import numpy as np
import cv2
import pytest
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import hero_qa as hq

FIX = os.path.join(os.path.dirname(__file__), "_fixtures")

def _straight_book_bgr():
    """A high-contrast portrait 'book cover' with horizontal text-like bars."""
    img = np.full((480, 320, 3), 235, np.uint8)          # portrait, light cover
    cv2.rectangle(img, (20, 20), (299, 459), (40, 40, 40), 6)   # cover border
    for y in (90, 150, 210, 330):                         # horizontal 'text' bars
        cv2.rectangle(img, (50, y), (270, y + 22), (30, 30, 30), -1)
    return img

def _save_png(path, bgr, alpha=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if alpha is not None:
        bgra = cv2.cvtColor(bgr, cv2.COLOR_BGR2BGRA); bgra[:, :, 3] = alpha
        cv2.imwrite(path, bgra)
    else:
        cv2.imwrite(path, bgr)
    return path

def test_level_pass_on_straight_hero():
    p = _save_png(os.path.join(FIX, "straight.png"), _straight_book_bgr())
    r = hq.check_level(p)
    assert r["ok"] is True
    assert r["level_deg"] <= 1.5

def test_level_fail_on_16deg_tilt():
    from test_hero_qa import _straight_book_bgr  # noqa
    base = _straight_book_bgr()
    # rotate 16° on a padded canvas so the whole object stays in frame
    pad = 240
    canvas = np.full((base.shape[0] + 2*pad, base.shape[1] + 2*pad, 3), 235, np.uint8)
    canvas[pad:pad+base.shape[0], pad:pad+base.shape[1]] = base
    h, w = canvas.shape[:2]
    M = cv2.getRotationMatrix2D((w/2, h/2), 16, 1.0)
    tilted = cv2.warpAffine(canvas, M, (w, h), borderValue=(235,235,235))
    p = _save_png(os.path.join(FIX, "tilt16.png"), tilted)
    r = hq.check_level(p)
    assert r["ok"] is False
    assert r["level_deg"] > 1.5
```

Run: `uv run --project $PROJ pytest .../tests/test_hero_qa.py -v` → FAIL (`module hero_qa not found`).

**Step 2 — implement `check_level`** in `hero_qa.py`:

```python
#!/usr/bin/env python3
"""hero_qa.py — blocking pre-publish Hero QA gate.

Checks a hero against the three historical failure modes (90° rotation,
>1.5° tilt, clipped face) plus background-by-class and over-clean defects.
Reuses deskew.residual_tilt_deg for the level check. CLI writes the verdict
to items/RG-XXXX/label.json -> hero_qa. Run via:
  uv run --project <plugin-root> python scripts/hero_qa.py items/RG-XXXX
"""
from __future__ import annotations
import os, sys, json, argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

sys.path.insert(0, os.path.dirname(__file__))      # deskew.py, standardize.py
import cv2
import numpy as np
from deskew import residual_tilt_deg

CHECKER = "auto:hero_qa_gate v1"
TILT_MAX_DEG = 1.5
TILT_MIN_CONF = 0.5

def _imread(path: str):
    bgr = cv2.imread(path)
    raw = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    alpha = raw[:, :, 3] if (raw is not None and raw.ndim == 3 and raw.shape[2] == 4) else None
    return bgr, alpha

def check_level(hero_path: str) -> Dict[str, Any]:
    bgr, alpha = _imread(hero_path)
    if bgr is None:
        return {"ok": False, "level_deg": None, "reason": "unreadable_hero"}
    r = residual_tilt_deg(bgr, alpha)
    tilt, conf = r["tilt_deg"], r["confidence"]
    # Only fail when the tilt reading is trustworthy (matches the prototype gate).
    failed = (tilt > TILT_MAX_DEG) and (conf >= TILT_MIN_CONF)
    out = {"ok": not failed, "level_deg": tilt, "confidence": conf}
    if failed:
        out["reason"] = f"tilt {tilt:.1f}° > {TILT_MAX_DEG}°"
    return out
```

Run the two tests → PASS.

**Step 3 — commit:** `git add .../scripts/hero_qa.py .../tests/test_hero_qa.py && git commit -m "feat(hero-qa): level check reusing deskew.residual_tilt_deg"`

---

### Task 3: Upright check (tesseract OSD + deterministic fallback)

**Files:** Modify `hero_qa.py`, `tests/test_hero_qa.py`

**Step 1 — failing tests:**

```python
def test_upright_fail_on_90deg_rotation():
    base = _straight_book_bgr()
    sideways = np.rot90(base, 1)                  # now landscape, text vertical
    p = _save_png(os.path.join(FIX, "rot90.png"), sideways)
    r = hq.check_upright(p)
    assert r["ok"] is False
    assert "90" in r["reason"] or "rotat" in r["reason"].lower()

def test_upright_pass_on_straight():
    p = _save_png(os.path.join(FIX, "straight.png"), _straight_book_bgr())
    assert hq.check_upright(p)["ok"] is True
```

Run → FAIL (`check_upright` undefined).

**Step 2 — implement.** OSD primary; on any tesseract error / low confidence / no binary, fall back to a conservative aspect+EXIF signal that only fails on a *positive* sideways indication.

```python
OSD_MIN_CONF = 1.0      # tesseract orientation_conf; >1 is a confident call

def _osd_rotation(bgr) -> Optional[Dict[str, float]]:
    """Return {'rotate': 0/90/180/270, 'conf': float} or None if OSD unavailable."""
    try:
        import pytesseract
        from PIL import Image
        pytesseract.get_tesseract_version()       # raises if binary missing
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        osd = pytesseract.image_to_osd(Image.fromarray(rgb),
                                       output_type=pytesseract.Output.DICT)
        return {"rotate": float(osd.get("rotate", 0)),
                "conf": float(osd.get("orientation_conf", 0))}
    except Exception:
        return None                                # too little text / no binary / error

def _exif_orientation(path: str) -> Optional[int]:
    try:
        from PIL import Image
        exif = Image.open(path).getexif()
        return exif.get(0x0112)                     # Orientation tag
    except Exception:
        return None

def check_upright(hero_path: str, original_path: Optional[str] = None) -> Dict[str, Any]:
    bgr, _ = _imread(hero_path)
    if bgr is None:
        return {"ok": False, "reason": "unreadable_hero", "method": "none"}
    osd = _osd_rotation(bgr)
    if osd is not None and osd["conf"] >= OSD_MIN_CONF and int(osd["rotate"]) in (90, 180, 270):
        return {"ok": False, "method": "osd",
                "reason": f"text rotated {int(osd['rotate'])}° (OSD conf {osd['conf']:.1f})"}
    if osd is not None and int(osd["rotate"]) == 0 and osd["conf"] >= OSD_MIN_CONF:
        return {"ok": True, "method": "osd"}
    # Fallback: only FAIL on a positive 'orientation not baked' signal from the source.
    if original_path:
        ori = _exif_orientation(original_path)
        if ori in (5, 6, 7, 8):                     # source needed a 90/270 rotation
            h, w = bgr.shape[:2]
            src, _ = _imread(original_path)
            if src is not None:
                sh, sw = src.shape[:2]
                hero_landscape = w > h
                src_raw_landscape = sw > sh          # pixels as stored (pre-transpose)
                if hero_landscape == src_raw_landscape:   # hero kept the un-baked aspect
                    return {"ok": False, "method": "exif_fallback",
                            "reason": f"source EXIF orientation {ori} not baked into hero"}
    return {"ok": True, "method": osd and "osd_lowconf" or "unknown"}  # don't false-fail
```

Run → PASS. (If this machine lacks the tesseract binary, `test_upright_fail_on_90deg_rotation` will not get an OSD signal; guard it: `pytest.importorskip` is not enough — skip when `hq._osd_rotation(_straight_book_bgr()) is None` to keep CI green where tesseract is absent. Tesseract is present on this machine, so it runs here.)

**Step 3 — commit:** `... -m "feat(hero-qa): upright check via tesseract OSD + EXIF fallback (catches 90° Atari mode)"`

---

### Task 4: Full-face check (class-aware clip detection)

**Files:** Modify `hero_qa.py`, `tests/test_hero_qa.py`

**Step 1 — failing tests:**

```python
def test_full_face_fail_on_clipped_cutout():
    # subject alpha touches the top + left border -> clipped, not floating
    bgr = np.full((400, 400, 3), 200, np.uint8)
    alpha = np.zeros((400, 400), np.uint8)
    alpha[0:260, 0:240] = 255                      # flush to top-left corner
    p = _save_png(os.path.join(FIX, "clip.png"), bgr, alpha)
    assert hq.check_full_face(p, item_class="cutout")["ok"] is False

def test_full_face_pass_on_floating_cutout():
    bgr = np.full((400, 400, 3), 200, np.uint8)
    alpha = np.zeros((400, 400), np.uint8)
    alpha[80:320, 120:280] = 255                   # clear margin from every border
    p = _save_png(os.path.join(FIX, "float.png"), bgr, alpha)
    assert hq.check_full_face(p, item_class="cutout")["ok"] is True

def test_full_face_lenient_for_flat_goods_fullbleed():
    bgr = _straight_book_bgr()                      # opaque, reaches edges by design
    p = _save_png(os.path.join(FIX, "flat.png"), bgr)
    assert hq.check_full_face(p, item_class="flat")["ok"] is True
```

Run → FAIL.

**Step 2 — implement:**

```python
BORDER_RING_FRAC = 0.01   # how close to the edge counts as 'touching'

def check_full_face(hero_path: str, item_class: str = "cutout") -> Dict[str, Any]:
    bgr, alpha = _imread(hero_path)
    if bgr is None:
        return {"ok": False, "reason": "unreadable_hero"}
    # Flat-goods / keep-bg are full-frame by design: the face SHOULD reach edges.
    if item_class in ("flat", "keepbg"):
        return {"ok": True, "method": "fullbleed_lenient"}
    # Cutout class: the subject must float clear of the border on all sides.
    if alpha is None:
        return {"ok": True, "method": "no_alpha"}   # not a cutout; nothing to clip-check
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
```

Run → PASS. **Commit:** `... -m "feat(hero-qa): class-aware full-face clip check (catches RG-0031 corner clip)"`

---

### Task 5: Background-by-class check

**Files:** Modify `hero_qa.py`, `tests/test_hero_qa.py`

**Step 1 — failing tests:**

```python
def test_bg_cutout_requires_transparency():
    p = _save_png(os.path.join(FIX, "opaque.png"), _straight_book_bgr())   # no alpha
    assert hq.check_bg(p, item_class="cutout")["ok"] is False

def test_bg_flat_requires_opaque():
    bgr = _straight_book_bgr(); alpha = np.full(bgr.shape[:2], 0, np.uint8)
    alpha[40:440, 40:280] = 255
    p = _save_png(os.path.join(FIX, "flat_transp.png"), bgr, alpha)
    assert hq.check_bg(p, item_class="flat")["ok"] is False   # flat must be full-bleed opaque

def test_bg_keepbg_is_lenient():
    p = _save_png(os.path.join(FIX, "opaque2.png"), _straight_book_bgr())
    assert hq.check_bg(p, item_class="keepbg")["ok"] is True
```

Run → FAIL.

**Step 2 — implement:**

```python
def check_bg(hero_path: str, item_class: str = "cutout") -> Dict[str, Any]:
    _, alpha = _imread(hero_path)
    has_transp = alpha is not None and bool((alpha < 250).any())
    if item_class == "keepbg":
        return {"ok": True, "method": "keepbg_lenient"}
    if item_class == "flat":
        if has_transp:
            return {"ok": False, "reason": "flat-goods hero must be opaque full-bleed, not a cutout"}
        return {"ok": True}
    # cutout class (standard/true-color): require a real transparent background
    if not has_transp:
        return {"ok": False, "reason": "cutout hero has no transparent background"}
    return {"ok": True}
```

Run → PASS. **Commit:** `... -m "feat(hero-qa): background-by-class check"`

---

### Task 6: Defect-retention soft check

**Files:** Modify `hero_qa.py`, `tests/test_hero_qa.py`

**Step 1 — failing tests:**

```python
def test_defects_not_compared_without_original():
    p = _save_png(os.path.join(FIX, "straight.png"), _straight_book_bgr())
    r = hq.check_defects(p, original_path=None)
    assert r["ok"] is True and r["reason"] == "not_compared"

def test_defects_fail_on_extreme_detail_wipe():
    orig = _straight_book_bgr()                     # has edges/detail
    blank = np.full_like(orig, 235)                 # detail wiped
    po = _save_png(os.path.join(FIX, "orig.png"), orig)
    pb = _save_png(os.path.join(FIX, "wiped.png"), blank)
    assert hq.check_defects(pb, original_path=po)["ok"] is False
```

Run → FAIL.

**Step 2 — implement** (coarse edge-density retention; only fails on extreme wipe):

```python
DEFECT_MIN_RETENTION = 0.40

def _edge_density(bgr) -> float:
    g = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    return float((cv2.Canny(cv2.GaussianBlur(g, (5, 5), 0), 40, 120) > 0).mean())

def check_defects(hero_path: str, original_path: Optional[str] = None) -> Dict[str, Any]:
    if not original_path or not os.path.exists(original_path):
        return {"ok": True, "reason": "not_compared"}
    hb, _ = _imread(hero_path); ob, _ = _imread(original_path)
    if hb is None or ob is None:
        return {"ok": True, "reason": "not_compared"}
    od = _edge_density(ob)
    if od < 1e-4:
        return {"ok": True, "reason": "original_featureless"}
    retention = _edge_density(hb) / od
    if retention < DEFECT_MIN_RETENTION:
        return {"ok": False, "reason": f"detail retention {retention:.0%} < {DEFECT_MIN_RETENTION:.0%} (over-cleaned?)"}
    return {"ok": True, "retention": round(retention, 2)}
```

Run → PASS. **Commit:** `... -m "feat(hero-qa): soft defect-retention check (guards RG-0030 over-clean)"`

---

### Task 7: Orchestration — `hero_qa_gate()` + class resolution

**Files:** Modify `hero_qa.py`, `tests/test_hero_qa.py`

**Step 1 — failing tests:**

```python
def test_gate_fails_with_all_reasons():
    # a 90°-rotated opaque 'cutout' -> fails upright + bg (no transparency)
    sideways = np.rot90(_straight_book_bgr(), 1)
    p = _save_png(os.path.join(FIX, "bad.png"), sideways)
    r = hq.hero_qa_gate(p, item_class="cutout")
    assert r["status"] == "fail"
    assert len(r["reasons"]) >= 1
    assert set(r["checks"]) == {"upright", "level_deg", "full_face", "bg_ok", "defects_ok"}

def test_gate_passes_clean_flat_hero():
    p = _save_png(os.path.join(FIX, "straight.png"), _straight_book_bgr())
    r = hq.hero_qa_gate(p, item_class="flat")
    assert r["status"] == "pass" and r["reasons"] == []

def test_resolve_item_class_from_label(tmp_path):
    item = tmp_path / "RG-9001"; item.mkdir()
    (item / "label.json").write_text(json.dumps({"product_name": "Vintage hardcover book"}))
    assert hq.resolve_item_class(str(item)) == "flat"   # 'book'/'hardcover' -> flat-goods
```

Run → FAIL.

**Step 2 — implement** (reuse standardize's profile logic; map profile → class):

```python
import standardize as st

_PROFILE_CLASS = {"flat-goods": "flat", "keep-bg": "keepbg",
                  "standard": "cutout", "true-color": "cutout", "manual": "cutout"}

def resolve_item_class(item_dir: str) -> str:
    label = {}
    p = Path(item_dir) / "label.json"
    if p.exists():
        try: label = json.loads(p.read_text())
        except Exception: label = {}
    profiles = st.load_photo_profiles()
    profile = st.resolve_profile(label, profiles) if profiles else "standard"
    return _PROFILE_CLASS.get(profile, "cutout")

def hero_qa_gate(hero_path: str, original_path: Optional[str] = None,
                 item_class: Optional[str] = None) -> Dict[str, Any]:
    item_class = item_class or "cutout"
    up = check_upright(hero_path, original_path)
    lv = check_level(hero_path)
    ff = check_full_face(hero_path, item_class)
    bg = check_bg(hero_path, item_class)
    df = check_defects(hero_path, original_path)
    checks = {"upright": up["ok"], "level_deg": lv.get("level_deg"),
              "full_face": ff["ok"], "bg_ok": bg["ok"], "defects_ok": df["ok"]}
    reasons = [c["reason"] for c in (up, lv, ff, bg, df)
               if not c["ok"] and c.get("reason")]
    hard_ok = up["ok"] and lv["ok"] and ff["ok"] and bg["ok"] and df["ok"]
    return {"status": "pass" if hard_ok else "fail",
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "checker": CHECKER, "item_class": item_class,
            "checks": checks, "reasons": reasons}
```

Run → PASS. **Commit:** `... -m "feat(hero-qa): orchestrate 5 checks + class resolution from label.json"`

---

### Task 8: CLI — single item, writes `label.json -> hero_qa`

**Files:** Modify `hero_qa.py` (add `__main__`), `tests/test_hero_qa.py`

**Step 1 — failing test:**

```python
def test_cli_writes_hero_qa_block(tmp_path):
    item = tmp_path / "RG-9002"; item.mkdir()
    _save_png(str(item / "hero.png"), _straight_book_bgr())
    (item / "label.json").write_text(json.dumps({"product_name": "hardcover book", "state": "Priced"}))
    rc = hq.run_item(str(item), write=True)         # programmatic entry the CLI calls
    d = json.loads((item / "label.json").read_text())
    assert d["hero_qa"]["status"] == "pass"
    assert d["hero_qa"]["checker"] == hq.CHECKER
    assert rc == 0
```

Run → FAIL.

**Step 2 — implement** `run_item` + `find_hero` + argparse `main()`:

```python
def find_hero(item_dir: str) -> Optional[str]:
    for name in ("hero.png", "hero.jpg", "hero.jpeg", "hero.webp"):
        p = Path(item_dir) / name
        if p.exists(): return str(p)
    cand = sorted(Path(item_dir).glob("hero.*"))
    return str(cand[0]) if cand else None

def _write_hero_qa(item_dir: str, verdict: Dict[str, Any]) -> None:
    p = Path(item_dir) / "label.json"
    d = json.loads(p.read_text()) if p.exists() else {}
    d["hero_qa"] = {k: verdict[k] for k in ("status","checked_at","checker","checks","reasons")}
    if verdict["status"] == "fail":
        d.setdefault("photo_overrides", {})["status"] = "needs_manual"
    tmp = p.with_suffix(".json.tmp"); tmp.write_text(json.dumps(d, indent=2)); tmp.replace(p)

def run_item(item_dir: str, write: bool = True, original_path: Optional[str] = None) -> int:
    hero = find_hero(item_dir)
    if not hero:
        print(f"  ✗ {Path(item_dir).name}: no hero image found", file=sys.stderr); return 2
    verdict = hero_qa_gate(hero, original_path, resolve_item_class(item_dir))
    if write: _write_hero_qa(item_dir, verdict)
    tag = "✓ pass" if verdict["status"] == "pass" else "✗ FAIL"
    print(f"  {tag}  {Path(item_dir).name}" + (f"  — {'; '.join(verdict['reasons'])}" if verdict["reasons"] else ""))
    return 0 if verdict["status"] == "pass" else 1

def main() -> int:
    ap = argparse.ArgumentParser(description="Pre-publish Hero QA gate")
    ap.add_argument("path", help="items/RG-XXXX dir (or items/ root with --batch)")
    ap.add_argument("--batch", action="store_true", help="run over every RG-* under path")
    ap.add_argument("--no-write", action="store_true", help="don't modify label.json")
    ap.add_argument("--original", help="original photo for defect comparison (single mode)")
    ap.add_argument("--json", action="store_true", help="emit machine JSON")
    a = ap.parse_args()
    if a.batch:
        return run_batch(a.path, write=not a.no_write, as_json=a.json)
    if a.json:
        hero = find_hero(a.path)
        print(json.dumps(hero_qa_gate(hero, a.original, resolve_item_class(a.path)) if hero
                         else {"status": "fail", "reasons": ["no hero"]}, indent=2))
        return 0
    return run_item(a.path, write=not a.no_write, original_path=a.original)

if __name__ == "__main__":
    sys.exit(main())
```

(Define a temporary `run_batch` stub returning 0 so import works; real one in Task 9.) Run → PASS.
**Commit:** `... -m "feat(hero-qa): CLI single-item run writes label.json hero_qa block"`

---

### Task 9: CLI `--batch` back-fill / audit

**Files:** Modify `hero_qa.py`, `tests/test_hero_qa.py`

**Step 1 — failing test:**

```python
def test_batch_audits_and_flags_listed_failures(tmp_path, capsys):
    items = tmp_path / "items"; items.mkdir()
    good = items / "RG-1000"; good.mkdir()
    _save_png(str(good / "hero.png"), _straight_book_bgr())
    (good / "label.json").write_text(json.dumps({"product_name": "book", "state": "Listed"}))
    bad = items / "RG-1001"; bad.mkdir()
    _save_png(str(bad / "hero.png"), np.rot90(_straight_book_bgr(), 1))
    (bad / "label.json").write_text(json.dumps({"product_name": "widget", "state": "Listed"}))  # cutout class, sideways+opaque
    rc = hq.run_batch(str(items), write=True)
    assert rc == 1                                   # a Listed item failed
    assert json.loads((bad / "label.json").read_text())["hero_qa"]["status"] == "fail"
    assert json.loads((good / "label.json").read_text())["hero_qa"]["status"] == "pass"
```

Run → FAIL (stub returns 0).

**Step 2 — implement** (replace the stub):

```python
def run_batch(items_root: str, write: bool = True, as_json: bool = False) -> int:
    root = Path(items_root)
    item_dirs = sorted(d for d in root.glob("RG-*") if (d / "label.json").exists() or list(d.glob("hero.*")))
    listed_fail = 0; rows = []
    for d in item_dirs:
        hero = find_hero(str(d))
        if not hero:
            rows.append((d.name, "no-hero", "")); continue
        label = {}
        lp = d / "label.json"
        if lp.exists():
            try: label = json.loads(lp.read_text())
            except Exception: pass
        verdict = hero_qa_gate(hero, None, resolve_item_class(str(d)))
        if write: _write_hero_qa(str(d), verdict)
        state = label.get("state", "?")
        if verdict["status"] == "fail" and state == "Listed":
            listed_fail += 1
        rows.append((d.name, verdict["status"], f'{state}: {"; ".join(verdict["reasons"])}'))
    if as_json:
        print(json.dumps([{"sku": r[0], "status": r[1], "note": r[2]} for r in rows], indent=2))
    else:
        print(f"\nHero QA audit — {len(rows)} items:")
        for sku, status, note in rows:
            mark = "✓" if status == "pass" else "✗"
            print(f"  {mark} {sku:<10} {status:<6} {note}")
        print(f"\n{listed_fail} currently-Listed item(s) FAIL the gate." if listed_fail
              else "\nAll Listed items pass.")
    return 1 if listed_fail else 0
```

Run → PASS. **Commit:** `... -m "feat(hero-qa): --batch back-fill audit; non-zero exit if any Listed item fails"`

---

### Task 10: Orientation bake-once in `standardize.py`

**Files:** Modify `plugins/richmondgeneral/skills/image-processor/scripts/standardize.py`; test in `tests/test_standardize.py`

**Step 1 — failing test** (append to `test_standardize.py`):

```python
def test_bake_orientation_rights_exif_6_and_strips_tag(tmp_path):
    import standardize as st
    from PIL import Image
    # portrait 60x100 stored as landscape pixels + EXIF orientation 6 (rotate 90 CW to view)
    pixels = Image.new("RGB", (100, 60), (10, 20, 30))
    exif = pixels.getexif(); exif[0x0112] = 6
    src = tmp_path / "o6.jpg"; pixels.save(src, exif=exif)
    baked = st.bake_orientation(Image.open(src))
    assert baked.size == (60, 100)                  # transposed to true portrait
    assert baked.getexif().get(0x0112) in (None, 1) # tag stripped/normalized
```

Run → FAIL (`bake_orientation` undefined).

**Step 2 — implement.** Add to `standardize.py` (after imports):

```python
def bake_orientation(img: "Image.Image") -> "Image.Image":
    """Bake EXIF orientation into pixels ONCE and drop the tag, so every later
    tool/viewer agrees. Never apply a second blind rotation after this.
    (Root fix for the Atari batch double-rotation, 2026-06-20.)"""
    out = ImageOps.exif_transpose(img)
    if out is None:
        out = img
    exif = out.getexif()
    if 0x0112 in exif:
        del exif[0x0112]
        out.info["exif"] = exif.tobytes()
    return out
```

Then route ingest through it: at each `Image.open(input_path)` that feeds the standardize pipeline (around lines 415 and 430), wrap as `bake_orientation(Image.open(input_path))`. Add a one-line comment: `# orientation baked once here; downstream steps must NOT rotate again`.

Run the new test + the full `test_standardize.py` → PASS (no regressions). **Commit:** `... -m "fix(standardize): bake EXIF orientation once at ingest (Atari double-rotation root fix)"`

---

### Task 11: Blocking integration — `item_state.can_list()` + `process_batch` hook + dual-copy sync

**Files:** Modify `rg-full-auto/scripts/item_state.py`, `rg-full-auto/scripts/process_batch.py`; test `rg-full-auto/tests/test_hero_gate_integration.py` (new)

**Step 1 — failing tests:**

```python
import json, sys, os
from pathlib import Path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import item_state as ist

def test_can_list_false_without_pass(tmp_path):
    item = tmp_path / "RG-3000"; item.mkdir()
    (item / "label.json").write_text(json.dumps({"state": "Priced"}))           # no hero_qa
    ok, reason = ist.can_list(str(item))
    assert ok is False and "hero_qa" in reason

def test_can_list_true_with_pass(tmp_path):
    item = tmp_path / "RG-3001"; item.mkdir()
    (item / "label.json").write_text(json.dumps({"hero_qa": {"status": "pass"}}))
    assert ist.can_list(str(item))[0] is True
```

Run: `uv run --project $PROJ pytest .../rg-full-auto/tests/test_hero_gate_integration.py -v` → FAIL.

**Step 2 — implement `can_list`** in `item_state.py`:

```python
PUBLISH_PHASES = ("phase_4", "phase_7")   # Square primary upload, GitHub publishing

def can_list(item_dir: str) -> tuple[bool, str]:
    """True only if label.json -> hero_qa.status == 'pass'. The single read-side
    chokepoint for 'is this hero allowed to publish / go Listed'."""
    p = Path(item_dir) / "label.json"
    if not p.exists():
        return False, "no label.json — hero_qa gate not run"
    try:
        hq = (json.loads(p.read_text()).get("hero_qa") or {})
    except Exception as exc:
        return False, f"label.json unreadable: {exc}"
    status = hq.get("status")
    if status == "pass":
        return True, "hero_qa pass"
    return False, f"hero_qa status={status or 'not_checked'} (must be 'pass' before publish)"
```

**Step 3 — hook the gate into `_advance_item`** (`process_batch.py`, between `next_runnable_phase()` and `start_phase`, ~line 224). Add near the orchestrator imports: `from item_state import can_list, PUBLISH_PHASES` and a runner of the gate:

```python
            phase = state.next_runnable_phase()
            if phase is None:
                break
            # BLOCKING HERO QA GATE: no Square-primary / GitHub publish without a pass.
            if phase in PUBLISH_PHASES:
                ok, reason = can_list(item_dir)
                if not ok:
                    self._run_hero_qa(item_dir)               # populate label.json hero_qa
                    ok, reason = can_list(item_dir)
                if not ok:
                    q = PendingQuestion(question_id=f"q-heroqa-{phase}", phase=phase,
                                        question=f"Hero QA gate failed: {reason}. Fix the hero, then re-run.")
                    state.block_phase(phase, q); state.save(); self._sync_queue(state)
                    phases_run.append({"phase": phase, "result": "blocked", "reason": reason})
                    continue
            state.start_phase(phase)
```

And add the subprocess runner method on `BatchOrchestrator`:

```python
    def _run_hero_qa(self, item_dir: str) -> None:
        """Run the image-processor hero_qa CLI to write label.json -> hero_qa."""
        import subprocess
        script = Path(__file__).resolve().parents[2] / "image-processor" / "scripts" / "hero_qa.py"
        proj = Path(__file__).resolve().parents[4]    # plugins/richmondgeneral
        try:
            subprocess.run(["uv", "run", "--project", str(proj), "python", str(script), item_dir],
                           check=False, timeout=180)
        except Exception as exc:
            print(f"  ⚠ hero_qa runner failed for {item_dir}: {exc}", file=sys.stderr)
```

Run the integration tests → PASS. Then a manual end-to-end check: a bad-hero fixture item driven through `_advance_item` blocks at `phase_4` (do this as a quick scripted check or an added test using a stub `phase_runner`).

**Step 4 — DUAL-COPY SYNC.** Mirror both skills to the cache and validate:
```
rsync -a --exclude=__pycache__ --exclude='*.tmp' \
  ~/workspace/richmondgeneral/skills/plugins/richmondgeneral/skills/image-processor/ \
  ~/.claude/plugins/cache/richmondgeneral/skills/image-processor/
rsync -a --exclude=__pycache__ --exclude='.state.json' \
  ~/workspace/richmondgeneral/skills/plugins/richmondgeneral/skills/rg-full-auto/ \
  ~/.claude/plugins/cache/richmondgeneral/skills/rg-full-auto/
# validate the gate from the CACHE copy too (code-mode runs cache):
uv run --project ~/.claude/plugins/cache/richmondgeneral python \
  ~/.claude/plugins/cache/richmondgeneral/skills/image-processor/scripts/hero_qa.py --help
```
(If the cache plugin root has no pyproject, run the cache script against `$PROJ` instead; note which env the cache uses.)

**Step 5 — commit** (two repos if cache is git-tracked; otherwise just `skills/`):
```
git add plugins/richmondgeneral/skills/rg-full-auto/scripts/item_state.py \
        plugins/richmondgeneral/skills/rg-full-auto/scripts/process_batch.py \
        plugins/richmondgeneral/skills/rg-full-auto/tests/test_hero_gate_integration.py
git commit -m "feat(rg-full-auto): blocking hero-QA gate at publish phases (can_list + _advance_item hook)"
```

---

### Task 12: Catalog back-fill audit + close-out

**Steps:**
1. Run the real audit over the live catalog (writes `hero_qa` to every item, reports Listed failures):
   ```
   uv run --project $PROJ python \
     plugins/richmondgeneral/skills/image-processor/scripts/hero_qa.py --batch \
     /Users/scottybe/workspace/richmondgeneral/items | tee /tmp/hero_qa_audit.txt
   ```
2. Review failures. Expected suspects from the postmortems: RG-0036–0051 (re-check the orientation-fixed heroes now read upright), RG-0021–0030 (gate-less batch). For any **true** failure on a Listed item, surface it (do not auto-edit photos) — note it as a follow-up.
3. The `items/` `label.json` files now carry `hero_qa` blocks: commit them in the **items/** repo with an explicit path list (separate repo, separate commit), message `chore(items): back-fill hero_qa verdicts (pre-publish gate)`.
4. Full suite green: `uv run --project $PROJ pytest plugins/richmondgeneral/skills/image-processor/tests/ plugins/richmondgeneral/skills/rg-full-auto/tests/ -v`.
5. Update `CLAUDE.md` operating-rules with a one-paragraph "Hero QA gate is live (hero_qa.py); no publish without hero_qa.status==pass" note and the back-fill result.

---

## Acceptance criteria (from the handoff)
1. ✅ No item reaches `Listed`/publish without `hero_qa.status=="pass"` — `can_list()` + `_advance_item` hook (Task 11).
2. ✅ Three historical modes each caught by a unit test — 90° (Task 3), ≥1.5° tilt (Task 2), clipped face (Task 4).
3. ✅ Orientation baked once at ingest; no post-transpose blind rotation — `bake_orientation()` (Task 10).
4. ✅ Both skill copies updated; CLI + `--batch` back-fill work — Tasks 8, 9, 11(sync), 12.
