# Combo collage (`combo.py`) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add `image-processor/scripts/combo.py` — a deterministic, non-generative PIL tool that builds a 1:1 / 1600px "hero-dominant magazine" marketplace collage (big hero + a rail of auto-selected, captioned detail crops) for an RG item.

**Architecture:** Mirror `golden_card.py` exactly — a pure-PIL `compose_combo()` returning `Optional[Path]`, an idempotent `record_photos_combo()` label.json reconciler, a `_batch()` backfiller, and an argparse `main()` with exit-code-2 = skipped. Slots are auto-mapped from semantic `detail-*` filenames (provenance / feature / condition) with a `label.json → combo_captions` override. Crops are center-cover (subject-bbox crop deferred). Reuses `enhance_common.append_pipeline` for the `image_pipeline[]` record.

**Tech Stack:** Python ≥3.11, Pillow (already a dep), pytest (already a dev dep). No torch — the compositor is pure PIL, so it runs inline over the Cowork bridge.

**Design:** `docs/plans/2026-06-21-combo-collage-design.md`

**v1 scope notes (intentional simplifications — DRY/YAGNI):**
- Crops are **center-cover** (cover, never letterbox; alpha flattened onto white). Subject-bbox/saliency cropping from the matte alpha is **deferred** — center-cover is the design's stated fallback and keeps `combo.py` torch-free.
- "Specific" captions come from an explicit `label.json → combo_captions` block (`{provenance,feature,condition}` → text); auto-deriving them from `attributes` is deferred. Default = generic role label.
- Layouts other than `magazine` (filmstrip/quad/insets) are out of scope for v1; `--layout` accepts only `magazine`.

**Conventions to copy (read first):**
- `skills/plugins/richmondgeneral/skills/image-processor/scripts/golden_card.py` — compose/record/_batch/main shape, exit-code-2 skip, idempotent label.json writes.
- `skills/plugins/richmondgeneral/skills/image-processor/scripts/enhance_common.py:55` — `append_pipeline(item_dir, entry)`.
- `skills/plugins/richmondgeneral/skills/image-processor/tests/test_golden_card.py` — synthetic-PIL-image test style, `tmp_path`, `sys.path.insert(.../scripts)`.

**Paths (all relative to repo root `/Users/scottybe/workspace/richmondgeneral`):**
- Create: `skills/plugins/richmondgeneral/skills/image-processor/scripts/combo.py`
- Create: `skills/plugins/richmondgeneral/skills/image-processor/tests/test_combo.py`

**Run tests (from repo root):**
```
uv run --project skills/plugins/richmondgeneral python -m pytest \
  skills/plugins/richmondgeneral/skills/image-processor/tests/test_combo.py -v
```

**Commit:** the skills repo is its own git repo. Commit with explicit paths (multi-agent workspace rule — never `git add -A`). Shown as `git -C skills ...` below. End every commit message with the `Co-Authored-By: Claude Opus 4.8` trailer. Do an isolated commit per task. Hold pushing until Task 7.

---

### Task 1: Slot selection (`select_slots`) — pure logic, no images composited

**Files:**
- Create: `.../image-processor/scripts/combo.py`
- Create: `.../image-processor/tests/test_combo.py`

**Step 1: Write the failing tests**

```python
"""Tests for combo.py — deterministic 1:1 marketplace combo collage."""
import json
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import combo as cb


def _img(path, color, size=(600, 600)):
    Image.new("RGB", size, color).save(path)


def _item(tmp_path, details=("detail-maker-mark", "detail-lid", "detail-bottom"),
          hero=True, label=None):
    d = tmp_path / "RG-9999"
    d.mkdir()
    if hero:
        _img(d / "hero.jpeg", (200, 30, 30))
    palette = [(30, 160, 30), (30, 30, 200), (200, 160, 30), (160, 30, 160), (30, 160, 160)]
    for i, name in enumerate(details):
        _img(d / f"{name}.jpeg", palette[i % len(palette)])
    if label is not None:
        (d / "label.json").write_text(json.dumps(label), encoding="utf-8")
    return d


def test_selects_hero_and_three_roles(tmp_path):
    d = _item(tmp_path)
    sel = cb.select_slots(d)
    assert sel is not None
    assert sel["hero"].name == "hero.jpeg"
    assert [s["role"] for s in sel["rail"]] == ["provenance", "feature", "condition"]


def test_skips_when_too_few_details(tmp_path):
    d = _item(tmp_path, details=("detail-maker-mark", "detail-lid"))
    assert cb.select_slots(d) is None


def test_skips_when_no_hero(tmp_path):
    d = _item(tmp_path, hero=False)
    assert cb.select_slots(d) is None


def test_caption_generic_fallback(tmp_path):
    d = _item(tmp_path)
    prov = cb.select_slots(d)["rail"][0]
    assert prov["caption"] == "Maker's mark"


def test_caption_override_from_label_json(tmp_path):
    d = _item(tmp_path, label={"sku": "RG-9999",
                               "combo_captions": {"provenance": "Kreamer · Size 50"}})
    prov = cb.select_slots(d)["rail"][0]
    assert prov["caption"] == "Kreamer · Size 50"
```

**Step 2: Run tests to verify they fail**

Run: `uv run --project skills/plugins/richmondgeneral python -m pytest skills/plugins/richmondgeneral/skills/image-processor/tests/test_combo.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'combo'`.

**Step 3: Write minimal implementation** (`combo.py` — module header, constants, selection)

```python
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
            overrides = json.loads(lj.read_text(encoding="utf-8")).get("combo_captions") or {}
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
```

**Step 4: Run tests to verify they pass**

Run: same pytest command as Step 2.
Expected: PASS (5 passed).

**Step 5: Commit**

```bash
git -C skills add plugins/richmondgeneral/skills/image-processor/scripts/combo.py \
                  plugins/richmondgeneral/skills/image-processor/tests/test_combo.py
git -C skills commit -m "feat(combo): slot selection from semantic detail filenames

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Cover-crop primitive (`crop_cover`)

**Files:**
- Modify: `.../scripts/combo.py` (append functions)
- Modify: `.../tests/test_combo.py` (append tests)

**Step 1: Write the failing tests**

```python
def test_crop_cover_exact_size(tmp_path):
    out = cb.crop_cover(Image.new("RGB", (800, 400), (10, 20, 30)), 300, 300)
    assert out.size == (300, 300)


def test_crop_cover_is_cover_not_contain(tmp_path):
    out = cb.crop_cover(Image.new("RGB", (800, 400), (200, 30, 30)), 300, 300)
    assert out.getpixel((0, 0)) == (200, 30, 30)        # filled, no white letterbox
    assert out.getpixel((299, 299)) == (200, 30, 30)


def test_crop_cover_flattens_alpha_on_white(tmp_path):
    src = Image.new("RGBA", (400, 400), (0, 0, 0, 0))    # fully transparent
    out = cb.crop_cover(src, 200, 200)
    assert out.mode == "RGB"
    assert out.getpixel((100, 100)) == cb.PANEL_BG       # transparency -> white, not black
```

**Step 2: Run to verify fail** — `AttributeError: module 'combo' has no attribute 'crop_cover'`.

**Step 3: Implement** (append to `combo.py`)

```python
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
```

**Step 4: Run to verify pass** (8 passed total).

**Step 5: Commit**

```bash
git -C skills add plugins/richmondgeneral/skills/image-processor/scripts/combo.py \
                  plugins/richmondgeneral/skills/image-processor/tests/test_combo.py
git -C skills commit -m "feat(combo): cover-crop primitive with alpha flatten

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Canvas composition geometry (`compose_combo`, panels only — no text yet)

**Files:** Modify `combo.py` + `test_combo.py`.

**Step 1: Write the failing tests**

```python
def test_output_size_is_1600(tmp_path):
    out = cb.compose_combo(_item(tmp_path))
    assert out is not None and out.exists()
    assert Image.open(out).size == (1600, 1600)


def test_hero_region_from_hero(tmp_path):
    im = Image.open(cb.compose_combo(_item(tmp_path))).convert("RGB")
    assert im.getpixel((12, 800)) == (200, 30, 30)       # hero is solid red, left/mid


def test_gutter_between_hero_and_rail_is_cream(tmp_path):
    im = Image.open(cb.compose_combo(_item(tmp_path))).convert("RGB")
    hero_w = round(1600 * cb.HERO_FRAC)                   # 992
    assert im.getpixel((hero_w + cb.GUTTER // 2, 800)) == cb.CREAM


def test_first_rail_cell_present(tmp_path):
    im = Image.open(cb.compose_combo(_item(tmp_path))).convert("RGB")
    rail_x = round(1600 * cb.HERO_FRAC) + cb.GUTTER       # 1008
    assert im.getpixel((rail_x + 6, 18)) == (30, 160, 30)  # first detail is solid green, top of cell


def test_skip_removes_stale_combo(tmp_path):
    d = _item(tmp_path, details=("detail-maker-mark",))   # too few
    (d / cb.COMBO_FILENAME).write_bytes(b"stale")
    assert cb.compose_combo(d) is None
    assert not (d / cb.COMBO_FILENAME).exists()
```

**Step 2: Run to verify fail** — `crop_cover` exists but `compose_combo` does not.

**Step 3: Implement** (append; panels only — wordmark/caption added in Task 4)

```python
def _sku(item_dir) -> str:
    lj = Path(item_dir) / "label.json"
    if lj.exists():
        try:
            s = json.loads(lj.read_text(encoding="utf-8")).get("sku")
            if s:
                return s
        except Exception:
            pass
    return Path(item_dir).name


def compose_combo(item_dir, out=None, rail: int = RAIL_DEFAULT,
                  caption_mode: str = "specific", layout: str = "magazine") -> Optional[Path]:
    item_dir = Path(item_dir)
    out_path = Path(out) if out else item_dir / COMBO_FILENAME
    sel = select_slots(item_dir, rail=rail, caption_mode=caption_mode)
    if sel is None:
        if out_path.exists():
            out_path.unlink()
        return None

    canvas = Image.new("RGB", (CANVAS, CANVAS), CREAM)
    hero_w = round(CANVAS * HERO_FRAC)
    canvas.paste(crop_cover(Image.open(sel["hero"]), hero_w, CANVAS, pos=(0.5, 0.42)), (0, 0))

    rail_x = hero_w + GUTTER
    rail_w = CANVAS - rail_x
    n = len(sel["rail"])
    cell_h = (CANVAS - (n - 1) * GUTTER) // n
    for i, slot in enumerate(sel["rail"]):
        y = i * (cell_h + GUTTER)
        h = cell_h if i < n - 1 else CANVAS - y          # last cell absorbs rounding to the edge
        canvas.paste(crop_cover(Image.open(slot["path"]), rail_w, h), (rail_x, y))

    canvas.save(out_path, "PNG")
    return out_path
```

**Step 4: Run to verify pass** (13 passed).

**Step 5: Commit**

```bash
git -C skills add plugins/richmondgeneral/skills/image-processor/scripts/combo.py \
                  plugins/richmondgeneral/skills/image-processor/tests/test_combo.py
git -C skills commit -m "feat(combo): hero-dominant magazine canvas geometry

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Captions + faint wordmark

**Files:** Modify `combo.py` + `test_combo.py`.

**Step 1: Write the failing tests**

```python
def _luma(im, box):
    px = im.convert("RGB").crop(box).getdata()
    return sum(0.299 * r + 0.587 * g + 0.114 * b for r, g, b in px) / len(px)


def test_caption_darkens_cell_lower_left(tmp_path):
    # first detail cell is solid green; the caption scrim must darken its lower-left
    im = Image.open(cb.compose_combo(_item(tmp_path))).convert("RGB")
    rail_x = round(1600 * cb.HERO_FRAC) + cb.GUTTER
    cell_h = (1600 - 2 * cb.GUTTER) // 3
    top = _luma(im, (rail_x + 4, 4, rail_x + 180, 60))
    low = _luma(im, (rail_x + 4, cell_h - 70, rail_x + 180, cell_h - 6))
    assert low < top - 20            # scrim pill present in lower-left


def test_compose_with_captions_keeps_size(tmp_path):
    im = Image.open(cb.compose_combo(_item(tmp_path)))
    assert im.size == (1600, 1600)   # wordmark + captions don't break the canvas
```

**Step 2: Run to verify fail** — lower-left still solid green (no scrim) → `low < top - 20` fails.

**Step 3: Implement** — add font + draw helpers, and call them in `compose_combo`.

Append helpers:
```python
_FONT_CANDIDATES = (
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/Library/Fonts/Arial.ttf",
)


def _load_font(size: int):
    for path in _FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    try:
        return ImageFont.load_default(size)   # Pillow >= 10.1
    except TypeError:
        return ImageFont.load_default()


def _draw_caption(canvas: Image.Image, rect, text: str) -> None:
    x, y, w, h = rect
    font = _load_font(max(22, h // 14))
    draw = ImageDraw.Draw(canvas, "RGBA")
    pad = 12
    tb = draw.textbbox((0, 0), text, font=font)
    tw, th = tb[2] - tb[0], tb[3] - tb[1]
    bx0, by1 = x + pad, y + h - pad
    bx1, by0 = bx0 + tw + 2 * pad, by1 - th - 2 * pad
    draw.rounded_rectangle((bx0, by0, bx1, by1), radius=10, fill=(*CAP_SCRIM, 178))
    draw.text((bx0 + pad - tb[0], by0 + pad - tb[1]), text, font=font, fill=(*CAP_TEXT, 255))


def _draw_wordmark(canvas: Image.Image, rect, sku: str) -> None:
    x, y, w, h = rect
    font = _load_font(26)
    draw = ImageDraw.Draw(canvas, "RGBA")
    text = f"RICHMOND GENERAL · {sku}"
    tx, ty = x + 22, y + h - 46
    draw.text((tx + 1, ty + 1), text, font=font, fill=(0, 0, 0, 150))      # legibility shadow
    draw.text((tx, ty), text, font=font, fill=(247, 242, 231, 205))        # faint cream
```

Then in `compose_combo`, add the wordmark after the hero paste and a caption after each cell paste:
```python
    canvas.paste(crop_cover(Image.open(sel["hero"]), hero_w, CANVAS, pos=(0.5, 0.42)), (0, 0))
    _draw_wordmark(canvas, (0, 0, hero_w, CANVAS), _sku(item_dir))
```
```python
        canvas.paste(crop_cover(Image.open(slot["path"]), rail_w, h), (rail_x, y))
        _draw_caption(canvas, (rail_x, y, rail_w, h), slot["caption"])
```

**Step 4: Run to verify pass** (15 passed).

**Step 5: Commit**

```bash
git -C skills add plugins/richmondgeneral/skills/image-processor/scripts/combo.py \
                  plugins/richmondgeneral/skills/image-processor/tests/test_combo.py
git -C skills commit -m "feat(combo): micro-captions + faint wordmark

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: label.json — `record_photos_combo` + `image_pipeline` entry

**Files:** Modify `combo.py` + `test_combo.py`.

**Step 1: Write the failing tests**

```python
def test_records_photos_combo(tmp_path):
    d = _item(tmp_path, label={"sku": "RG-9999"})
    cb.compose_combo(d)
    cb.record_photos_combo(d, made=True)
    data = json.loads((d / "label.json").read_text())
    assert data["photos"]["combo"] == "combo.png"


def test_record_is_idempotent(tmp_path):
    d = _item(tmp_path, label={"sku": "RG-9999"})
    cb.compose_combo(d)
    cb.record_photos_combo(d, made=True)
    first = (d / "label.json").read_text()
    cb.record_photos_combo(d, made=True)                 # second call must not rewrite
    assert (d / "label.json").read_text() == first


def test_records_image_pipeline_entry(tmp_path):
    d = _item(tmp_path, label={"sku": "RG-9999"})
    cb.compose_combo(d)
    data = json.loads((d / "label.json").read_text())
    ops = [e.get("op") for e in data.get("image_pipeline", [])]
    assert "combo" in ops


def test_record_removes_combo_when_skipped(tmp_path):
    d = _item(tmp_path, label={"sku": "RG-9999", "photos": {"combo": "combo.png"}})
    cb.record_photos_combo(d, made=False)
    data = json.loads((d / "label.json").read_text())
    assert "combo" not in data.get("photos", {})
```

**Step 2: Run to verify fail** — `record_photos_combo` missing; `image_pipeline` not yet written by compose.

**Step 3: Implement**

Append the reconciler (copy `golden_card.record_photos_card` shape):
```python
def record_photos_combo(item_dir, made: bool) -> None:
    """Idempotently reconcile label.json -> photos.combo with combo.png; write only on change."""
    p = Path(item_dir) / "label.json"
    if not p.exists():
        return
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"warning: {p}: {exc}", file=sys.stderr)
        return
    photos = data.get("photos") if isinstance(data.get("photos"), dict) else None
    current = photos.get("combo") if photos else None
    desired = COMBO_FILENAME if made else None
    if current == desired:
        return
    photos = data.setdefault("photos", {})
    if desired is None:
        photos.pop("combo", None)
    else:
        photos["combo"] = desired
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
```

In `compose_combo`, just before `return out_path`, record the pipeline entry:
```python
    canvas.save(out_path, "PNG")
    append_pipeline(str(item_dir), {
        "op": "combo",
        "tool": "combo.py",
        "layout": layout,
        "out": out_path.name,
        "hero": sel["hero"].name,
        "rail": [s["path"].name for s in sel["rail"]],
    })
    return out_path
```
(`append_pipeline` is a no-op when there's no label.json, so Task 1–4 tests with bare item dirs stay green.)

**Step 4: Run to verify pass** (19 passed).

**Step 5: Commit**

```bash
git -C skills add plugins/richmondgeneral/skills/image-processor/scripts/combo.py \
                  plugins/richmondgeneral/skills/image-processor/tests/test_combo.py
git -C skills commit -m "feat(combo): label.json photos.combo reconcile + image_pipeline record

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: `_batch` backfiller + `main()` CLI (exit-code-2 skip)

**Files:** Modify `combo.py` + `test_combo.py`.

**Step 1: Write the failing tests**

```python
import subprocess

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "scripts", "combo.py")


def test_cli_builds_and_records(tmp_path):
    d = _item(tmp_path, label={"sku": "RG-9999"})
    rc = subprocess.run([sys.executable, SCRIPT, "--item-dir", str(d)]).returncode
    assert rc == 0
    assert (d / "combo.png").exists()
    assert json.loads((d / "label.json").read_text())["photos"]["combo"] == "combo.png"


def test_cli_exit_2_on_skip(tmp_path):
    d = _item(tmp_path, details=("detail-maker-mark",))   # too few details
    rc = subprocess.run([sys.executable, SCRIPT, "--item-dir", str(d)]).returncode
    assert rc == 2


def test_batch_backfills_eligible_only(tmp_path):
    items = tmp_path / "items"
    items.mkdir()
    _item(items, details=("detail-maker-mark", "detail-lid", "detail-bottom"))      # RG-9999 eligible
    thin = items / "RG-0001"
    thin.mkdir()
    _img(thin / "hero.jpeg", (10, 10, 10))
    _img(thin / "detail-mark.jpeg", (20, 20, 20))                                   # only 1 detail
    made, skipped = cb._batch(items)
    assert made == 1 and skipped == 1
```

**Step 2: Run to verify fail** — `_batch` / `main` missing.

**Step 3: Implement** (append; mirror `golden_card._batch` + `main`)

```python
def _batch(items_dir, rail: int = RAIL_DEFAULT, caption_mode: str = "specific"):
    items_dir = Path(items_dir).expanduser().resolve()
    made = skipped = 0
    for d in sorted(items_dir.glob("RG-*")):
        if not d.is_dir():
            continue
        try:
            out = compose_combo(d, rail=rail, caption_mode=caption_mode)
        except Exception as exc:
            print(f"  ! {d.name}: {exc}", file=sys.stderr)
            continue
        record_photos_combo(d, made=out is not None)
        if out is None:
            skipped += 1
            print(f"  - {d.name}: too few views, skipped")
        else:
            made += 1
            print(f"  ✓ {d.name}: {out.name}")
    print(f"\nbackfill: made={made} skipped={skipped}")
    return made, skipped


def main() -> None:
    ap = argparse.ArgumentParser(description="Compose a 1:1 marketplace combo collage.")
    ap.add_argument("--item-dir", help="item dir (items/RG-XXXX)")
    ap.add_argument("--out", help="output path (default: <item-dir>/combo.png)")
    ap.add_argument("--rail", type=int, default=RAIL_DEFAULT, help="rail cells, 3 or 4 (default 3)")
    ap.add_argument("--caption-mode", choices=("specific", "generic"), default="specific")
    ap.add_argument("--layout", choices=("magazine",), default="magazine")
    ap.add_argument("--batch", metavar="ITEMS_DIR", help="backfill every items/RG-*/ with enough views")
    args = ap.parse_args()

    if args.batch:
        _batch(args.batch, rail=args.rail, caption_mode=args.caption_mode)
        sys.exit(0)
    if not args.item_dir:
        ap.error("--item-dir is required (or use --batch ITEMS_DIR)")
    out = compose_combo(args.item_dir, out=args.out, rail=args.rail,
                        caption_mode=args.caption_mode, layout=args.layout)
    record_photos_combo(args.item_dir, made=out is not None)
    if out is None:
        print("skipped: no hero or too few detail views", file=sys.stderr)
        sys.exit(2)
    print(out)


if __name__ == "__main__":
    main()
```

**Step 4: Run to verify pass** (22 passed).

**Step 5: Commit**

```bash
git -C skills add plugins/richmondgeneral/skills/image-processor/scripts/combo.py \
                  plugins/richmondgeneral/skills/image-processor/tests/test_combo.py
git -C skills commit -m "feat(combo): batch backfill + CLI (exit-2 skip)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 7: Full suite, real-item smoke, dual-copy sync, SKILL.md, push

**Files:**
- Modify: `.../image-processor/SKILL.md` (version bump + one-line combo.py entry)
- Sync: source scripts/tests → `~/.claude/plugins/cache/richmondgeneral/.../image-processor/` (dual-copy trap)

**Step 1: Run the FULL image-processor suite (no regressions)**

Run: `uv run --project skills/plugins/richmondgeneral python -m pytest skills/plugins/richmondgeneral/skills/image-processor/tests/ -q`
Expected: all prior tests + the new 22 pass.

**Step 2: Smoke-run on a real item (RG-0055, the design's worked example)**

Run:
```bash
cp -r items/RG-0055 /tmp/rg55-combo-smoke
uv run --project skills/plugins/richmondgeneral python \
  skills/plugins/richmondgeneral/skills/image-processor/scripts/combo.py \
  --item-dir /tmp/rg55-combo-smoke
```
Expected: prints `/tmp/rg55-combo-smoke/combo.png`; open it and eyeball — full pail hero left, maker-mark / lid / bottom in the rail with captions, faint `RICHMOND GENERAL · RG-0055` in the hero corner. (Smoke only — do NOT write into the real `items/RG-0055`.)

**Step 3: Add `combo_captions` to RG-0055 for the specific-caption check (optional eyeball)**

In `/tmp/rg55-combo-smoke/label.json` add:
```json
"combo_captions": {"provenance": "Kreamer · Size 50", "feature": "Lid & bail fit", "condition": "Honest patina"}
```
Re-run Step 2; confirm the rail captions change to the specific text.

**Step 4: Bump SKILL.md**

Set `version: "1.13"` and add one line under the scripts list, e.g.:
`- combo.py — 1:1 marketplace "combo" collage (hero-dominant magazine; auto-mapped detail crops + captions; non-generative).`

**Step 5: Dual-copy sync (the dual-copy trap)** — copy ONLY the two new/changed files, never `rsync -a` the whole dir (clobber trap):
```bash
CACHE=~/.claude/plugins/cache/richmondgeneral/*/skills/image-processor
cp skills/plugins/richmondgeneral/skills/image-processor/scripts/combo.py $CACHE/scripts/combo.py
cp skills/plugins/richmondgeneral/skills/image-processor/tests/test_combo.py $CACHE/tests/test_combo.py
cp skills/plugins/richmondgeneral/skills/image-processor/SKILL.md $CACHE/SKILL.md
```
Then run the suite against the cache copy to confirm parity:
`uv run --project skills/plugins/richmondgeneral python -m pytest $CACHE/tests/test_combo.py -q`

**Step 6: Commit + push (mandatory pre-push checks)**

```bash
git -C skills add plugins/richmondgeneral/skills/image-processor/SKILL.md
git -C skills commit -m "feat(combo): ship v1 — SKILL.md v1.13 + dual-copy sync

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
git -C skills fetch origin -q
git -C skills log --oneline origin/main..HEAD          # confirm ALL commits are yours + coherent
git -C skills rev-list --left-right --count origin/main...HEAD   # require behind=0
git -C skills push origin main                          # clean fast-forward only; never --force
```
If `behind` > 0 or any foreign WIP commit appears, STOP and reconcile per the CLAUDE.md multi-agent rules (rebase/worktree), do not force.

---

## Definition of done

- 22 new `test_combo.py` tests green; full image-processor suite green (source AND cache copy).
- `combo.py` produces a faithful 1600² combo on RG-0055 (eyeballed): hero-dominant, captioned rail, faint wordmark; specific captions honored from `combo_captions`.
- SKILL.md v1.13; both copies synced; committed + pushed clean to skills `main`.

## Follow-ups (not this plan)
- Subject-bbox / saliency crops for the rail (replace center-cover) once the BEN2-vs-BiRefNet matte work lands.
- Auto-attach `combo.png` as an extra photo on eBay / FB / Whatnot (channel write paths).
- Catalog-wide `combo.py --batch items/` backfill → then surface on channels.
- Optional alternate layouts (filmstrip for wide items) behind `--layout`.
