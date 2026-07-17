# Golden-Ratio Transparent Card Image — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a deterministic, non-generative `card.png` — the item's transparent cutout floated on a horizontal golden-ratio (φ ≈ 1.618 : 1) transparent canvas — produced by image-processing, shown on the GitHub item cards (gallery + detail), and pushed to Square as an additional image. `hero.png` is never modified.

**Architecture:** A new pure-PIL module `golden_card.py` composes the card from an existing transparent cutout (skipping opaque/non-cutout items via a min-alpha test). `standardize.py` calls it after producing its cutout, behind a default-on `--card` flag, and records `photos.card` in `label.json`. The website templates render `card.png` first with an `onerror` fallback to the hero (generator-independent), and their card containers move to the golden aspect ratio. Square gets `card.png` as an additional image via the existing upload skill.

**Tech Stack:** Python 3.11, Pillow (already a dep — no new dependency), pytest (`dev` extra), `uv`; HTML/CSS templates; Square Catalog API via the existing `square-image-upload` skill.

---

## Design reference
Full design + rationale: `skills/plugins/richmondgeneral/skills/rg-full-auto/docs/plans/2026-06-20-golden-ratio-card-image-design.md`.

## Pre-flight (read before starting)

- **Two git repos are touched.** Image code → the `skills/` repo (`/Users/scottybe/workspace/richmondgeneral/skills`). Templates + gallery → the `items/` repo (`/Users/scottybe/workspace/richmondgeneral/items`, which **deploys GitHub Pages on push**). Commit **per-repo**, stage **explicit paths only** — never `git add -A` (other sessions' untracked work sits alongside). Verify branch right before each commit; `git log origin/main..main` before any push; clean fast-forward only, never `--force`.
- **Dual-copy trap.** Every `image-processor` script edit must be mirrored into BOTH plugin-cache copies after the source change is green:
  - `/Users/scottybe/.claude/plugins/cache/richmondgeneral/skills/image-processor/scripts/`
  - `/Users/scottybe/.claude/plugins/cache/richmondgeneral/richmondgeneral/1.1.0/skills/image-processor/scripts/`
- **Test command** (run from the workspace root):
  ```bash
  cd /Users/scottybe/workspace/richmondgeneral && \
  uv run --project skills/plugins/richmondgeneral --extra dev \
    pytest skills/plugins/richmondgeneral/skills/image-processor/tests/ -v
  ```
  (Scope to a single file/test by appending the path / `::test_name`.)
- **Paths below** are relative to `/Users/scottybe/workspace/richmondgeneral` unless absolute. The image-processor source dir is `skills/plugins/richmondgeneral/skills/image-processor` (abbreviated **IP** below).

---

## Phase 1 — `golden_card.py` module (pure PIL, TDD)

### Task 1: Failing tests for the compose core

**Files:**
- Test: `IP/tests/test_golden_card.py` (create)

**Step 1: Write the failing tests**

Mirror the existing `tests/test_hero_qa.py` style (sys.path insert, self-generated fixtures, write to `tmp_path`).

```python
"""Tests for golden_card.py — deterministic golden-ratio card composition."""
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import golden_card as gc


def _cutout(w, h, mw, mh):
    """Transparent w×h RGBA with an opaque mw×mh white block centered (a fake cutout)."""
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    block = Image.new("RGBA", (mw, mh), (255, 255, 255, 255))
    img.paste(block, ((w - mw) // 2, (h - mh) // 2))
    return img


def test_output_is_horizontal_golden_ratio(tmp_path):
    src = tmp_path / "hero.png"
    _cutout(800, 800, 400, 600).save(src)
    out = gc.compose_golden_card(src, tmp_path / "card.png")
    assert out is not None and out.exists()
    im = Image.open(out)
    assert im.size == (2000, 1236)                 # default width 2000, height = round(2000/phi)
    assert abs(im.width / im.height - gc.PHI) < 0.01
    assert im.width > im.height                     # horizontal


def test_padding_is_transparent(tmp_path):
    src = tmp_path / "hero.png"
    _cutout(800, 800, 400, 600).save(src)
    im = Image.open(gc.compose_golden_card(src, tmp_path / "card.png")).convert("RGBA")
    assert im.getpixel((0, 0))[3] == 0             # corners fully transparent
    assert im.getpixel((im.width - 1, im.height - 1))[3] == 0


def test_object_centered(tmp_path):
    src = tmp_path / "hero.png"
    _cutout(800, 800, 300, 500).save(src)
    im = Image.open(gc.compose_golden_card(src, tmp_path / "card.png")).convert("RGBA")
    bbox = im.getchannel("A").getbbox()
    cx = (bbox[0] + bbox[2]) / 2
    cy = (bbox[1] + bbox[3]) / 2
    assert abs(cx - im.width / 2) <= 2
    assert abs(cy - im.height / 2) <= 2


def test_portrait_is_height_constrained(tmp_path):
    src = tmp_path / "hero.png"
    _cutout(800, 800, 200, 760).save(src)          # tall object
    im = Image.open(gc.compose_golden_card(src, tmp_path / "card.png")).convert("RGBA")
    bbox = im.getchannel("A").getbbox()
    obj_h = bbox[3] - bbox[1]
    assert abs(obj_h - gc.DEFAULT_FILL * im.height) <= 3   # fills ~fill of HEIGHT
    assert (bbox[2] - bbox[0]) < im.width                  # margins left/right


def test_wide_is_width_constrained(tmp_path):
    src = tmp_path / "hero.png"
    _cutout(800, 800, 760, 200).save(src)          # wide object
    im = Image.open(gc.compose_golden_card(src, tmp_path / "card.png")).convert("RGBA")
    bbox = im.getchannel("A").getbbox()
    obj_w = bbox[2] - bbox[0]
    assert abs(obj_w - gc.DEFAULT_FILL * im.width) <= 3    # fills ~fill of WIDTH


def test_opaque_input_is_skipped(tmp_path):
    src = tmp_path / "hero.png"
    Image.new("RGB", (800, 600), (120, 120, 120)).save(src)   # fully opaque, no alpha
    out = gc.compose_golden_card(src, tmp_path / "card.png")
    assert out is None
    assert not (tmp_path / "card.png").exists()


def test_custom_width_derives_golden_height(tmp_path):
    src = tmp_path / "hero.png"
    _cutout(800, 800, 400, 400).save(src)
    im = Image.open(gc.compose_golden_card(src, tmp_path / "card.png", width=1000))
    assert im.size == (1000, round(1000 / gc.PHI))           # 1000 x 618
```

**Step 2: Run to verify it fails**

Run: `cd /Users/scottybe/workspace/richmondgeneral && uv run --project skills/plugins/richmondgeneral --extra dev pytest skills/plugins/richmondgeneral/skills/image-processor/tests/test_golden_card.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'golden_card'`.

---

### Task 2: Implement `golden_card.py`

**Files:**
- Create: `IP/scripts/golden_card.py`

**Step 1: Write the implementation**

```python
#!/usr/bin/env python3
"""Compose a golden-ratio (phi) transparent CARD image from a transparent cutout.

Takes a standardized transparent hero (the square 1:1 cutout standardize.py
produces) and floats the object, centered, on a HORIZONTAL golden-ratio
transparent canvas (width:height = phi : 1, default 2000x1236), saved as a NEW
file (card.png) alongside the hero. The hero is never modified.

Deterministic, pure-PIL, NON-generative (only moves/scales existing pixels) —
safe for books/text/defects.

SKIP RULE: if the source has no real transparency (min alpha >= 250 — an opaque
full-bleed image such as a flat-goods scan or a keep-bg glass/silver photo),
there is no cutout to float, so compose returns None and writes nothing. That is
how flat-goods / keep-bg items are excluded automatically.

CLI:
  golden_card.py <hero.png> [--out card.png] [--width 2000] [--fill 0.85]
  golden_card.py --batch <items_dir>      # backfill every items/RG-*/ that has a cutout
"""
import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from PIL import Image
from PIL.PngImagePlugin import PngInfo

PHI = 1.6180339887            # golden ratio; height is ALWAYS width/PHI so the ratio can't drift
DEFAULT_WIDTH = 2000
DEFAULT_FILL = 0.85           # fraction of the canvas the object fills on its limiting dimension
OPAQUE_ALPHA_THRESHOLD = 250  # min alpha >= this => effectively opaque => no cutout => skip
CARD_FILENAME = "card.png"


def golden_size(width: int = DEFAULT_WIDTH) -> tuple:
    """(width, height) of a horizontal golden rectangle for the given width."""
    return width, int(round(width / PHI))


def _has_cutout(rgba: Image.Image) -> bool:
    """True if the image carries real transparency (an actual cutout to float)."""
    lo, _hi = rgba.getchannel("A").getextrema()
    return lo < OPAQUE_ALPHA_THRESHOLD


def compose_golden_card(hero_path, out_path=None, width: int = DEFAULT_WIDTH,
                        fill: float = DEFAULT_FILL) -> Optional[Path]:
    """Float the cutout in hero_path onto a transparent golden-ratio canvas.

    Returns the written Path, or None if the source is opaque (no cutout) and
    nothing was written.
    """
    hero_path = Path(hero_path)
    src = Image.open(hero_path)
    rgba = src.convert("RGBA")
    if not _has_cutout(rgba):
        return None  # opaque full-bleed (flat-goods / keep-bg) -> no card

    bbox = rgba.getchannel("A").getbbox() or rgba.getbbox()
    obj = rgba.crop(bbox) if bbox else rgba
    ow, oh = obj.size

    cw, ch = golden_size(width)
    scale = min((fill * cw) / ow, (fill * ch) / oh)   # limiting dimension wins
    new_w, new_h = max(1, round(ow * scale)), max(1, round(oh * scale))
    obj = obj.resize((new_w, new_h), Image.LANCZOS)

    canvas = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    canvas.paste(obj, ((cw - new_w) // 2, (ch - new_h) // 2), obj)

    out_path = Path(out_path) if out_path else hero_path.parent / CARD_FILENAME
    meta = PngInfo()                                   # carry provenance text chunks (Copyright/Title)
    for k, v in getattr(src, "text", {}).items():
        meta.add_text(k, v)
    canvas.save(out_path, "PNG", pnginfo=meta)
    return out_path


def record_photos_card(item_dir, card_filename: str = CARD_FILENAME) -> None:
    """Set label.json -> photos.card so channels/templates know a card exists. No-op if absent."""
    p = Path(item_dir) / "label.json"
    if not p.exists():
        return
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        data.setdefault("photos", {})["card"] = card_filename
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception as exc:
        print(f"warning: {p}: {exc}", file=sys.stderr)


def _find_cutout_hero(item_dir: Path) -> Optional[Path]:
    for name in ("hero-std.png", "hero.png", "hero.jpg", "hero.jpeg", "hero.webp"):
        if (item_dir / name).exists():
            return item_dir / name
    return None


def _batch(items_dir, width: int, fill: float) -> int:
    items_dir = Path(items_dir).expanduser().resolve()
    made = skipped = 0
    for d in sorted(items_dir.glob("RG-*")):
        if not d.is_dir():
            continue
        hero = _find_cutout_hero(d)
        if hero is None:
            continue
        try:
            out = compose_golden_card(hero, d / CARD_FILENAME, width=width, fill=fill)
        except Exception as exc:
            print(f"  ! {d.name}: {exc}", file=sys.stderr)
            continue
        if out is None:
            skipped += 1
            print(f"  - {d.name}: no cutout, skipped")
        else:
            record_photos_card(d)
            made += 1
            print(f"  ✓ {d.name}: {out.name}")
    print(f"\nbackfill: made={made} skipped={skipped}")
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description="Compose a golden-ratio transparent card from a cutout.")
    ap.add_argument("hero", nargs="?", help="path to the transparent hero/cutout PNG")
    ap.add_argument("--out", help="output card path (default: <hero dir>/card.png)")
    ap.add_argument("--width", type=int, default=DEFAULT_WIDTH, help="canvas width px (default 2000)")
    ap.add_argument("--fill", type=float, default=DEFAULT_FILL, help="object fill fraction (default 0.85)")
    ap.add_argument("--batch", metavar="ITEMS_DIR", help="backfill every items/RG-*/ that has a cutout")
    args = ap.parse_args()

    if args.batch:
        sys.exit(_batch(args.batch, args.width, args.fill))
    if not args.hero:
        ap.error("hero is required (or use --batch ITEMS_DIR)")
    out = compose_golden_card(args.hero, args.out, width=args.width, fill=args.fill)
    if out is None:
        print("skipped: opaque source (no cutout)", file=sys.stderr)
        sys.exit(2)
    print(out)


if __name__ == "__main__":
    main()
```

**Step 2: Run tests to verify they pass**

Run: `cd /Users/scottybe/workspace/richmondgeneral && uv run --project skills/plugins/richmondgeneral --extra dev pytest skills/plugins/richmondgeneral/skills/image-processor/tests/test_golden_card.py -v`
Expected: PASS (all 7).

**Step 3: Commit (skills repo, explicit paths)**

```bash
cd /Users/scottybe/workspace/richmondgeneral/skills
git rev-parse --abbrev-ref HEAD   # confirm: main
git add plugins/richmondgeneral/skills/image-processor/scripts/golden_card.py \
        plugins/richmondgeneral/skills/image-processor/tests/test_golden_card.py
git commit -m "feat(image-processor): golden_card.py — golden-ratio transparent card from a cutout

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Phase 2 — Wire into `standardize.py` (TDD)

### Task 3: Failing test — standardize emits card.png for a cutout, respects --no-card

**Files:**
- Test: `IP/tests/test_standardize_card.py` (create)

**Step 1: Write the failing tests** (offline — `do_bg=False` so no API call; a transparent input is already a "cutout").

```python
"""standardize.py golden-card wiring (offline: do_bg=False, transparent input)."""
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import standardize as st


def _transparent_input(path):
    img = Image.new("RGBA", (600, 600), (0, 0, 0, 0))
    img.paste(Image.new("RGBA", (300, 400), (200, 50, 50, 255)), (150, 100))
    img.save(path)


def test_standardize_emits_card_for_cutout(tmp_path):
    src = tmp_path / "hero.png"
    _transparent_input(src)
    out = tmp_path / "hero-std.png"
    st.standardize(str(src), str(out), do_color=False, do_bg=False, do_card=True)
    card = tmp_path / "card.png"
    assert card.exists()
    im = Image.open(card)
    assert im.size == (2000, 1236)


def test_standardize_no_card_when_disabled(tmp_path):
    src = tmp_path / "hero.png"
    _transparent_input(src)
    out = tmp_path / "hero-std.png"
    st.standardize(str(src), str(out), do_color=False, do_bg=False, do_card=False)
    assert not (tmp_path / "card.png").exists()
```

**Step 2: Run to verify it fails**

Run: `... pytest skills/plugins/richmondgeneral/skills/image-processor/tests/test_standardize_card.py -v`
Expected: FAIL — `standardize() got an unexpected keyword argument 'do_card'`.

---

### Task 4: Add `do_card` to `standardize()` and call the composer

**Files:**
- Modify: `IP/scripts/standardize.py` — function `standardize()` signature (line 422-425) and after the save (line 466).

**Step 1: Add `do_card=True` to the signature.** Change:

```python
def standardize(input_path, output_path, do_color=True, do_bg=True, fill=0.85, size=2000,
                shadow=False, copyright_text=None, sku=None, watermark=False,
                watermark_logo=DEFAULT_LOGO, wb="background", model=None, allow_rect_mask=False,
                do_deskew=False, perspective_correct=False, crop_to_face=False):
```
to add `do_card=True,` at the end of the parameter list:
```python
                do_deskew=False, perspective_correct=False, crop_to_face=False, do_card=True):
```

**Step 2: After the save, compose the card (lazy import, never crashes the pipeline).** Replace:

```python
        final_img.save(output_path, "PNG", pnginfo=metadata)
    return output_path, mask_quality
```
with:
```python
        final_img.save(output_path, "PNG", pnginfo=metadata)

        if do_card:
            # Float the cutout onto a golden-ratio transparent canvas (card.png).
            # Lazy import so a missing module degrades to "no card" instead of crashing.
            # Opaque full-bleed outputs (flat-goods / keep-bg) are skipped inside the composer.
            try:
                sys.path.insert(0, SCRIPT_DIR)
                from golden_card import compose_golden_card
                compose_golden_card(output_path, Path(output_path).parent / "card.png")
            except Exception as exc:
                print(f"warning: golden card compose failed: {exc}", file=sys.stderr)
    return output_path, mask_quality
```

**Step 3: Run the Task 3 tests to verify they pass**

Run: `... pytest skills/plugins/richmondgeneral/skills/image-processor/tests/test_standardize_card.py -v`
Expected: PASS (both).

**Step 4: Commit**

```bash
cd /Users/scottybe/workspace/richmondgeneral/skills
git rev-parse --abbrev-ref HEAD
git add plugins/richmondgeneral/skills/image-processor/scripts/standardize.py \
        plugins/richmondgeneral/skills/image-processor/tests/test_standardize_card.py
git commit -m "feat(image-processor): standardize() emits golden card.png (do_card, default on)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: CLI `--card/--no-card` + thread through both call sites + record photos.card

**Files:**
- Modify: `IP/scripts/standardize.py` — parser (after line 693, the `--json` arg), batch call site (line 564-566 region), single call site (line 764-766 region), and the batch "ok" branch (around line 601-609).

**Step 1: Add the mutually-exclusive flag to `_build_parser()`.** After the `--json` argument (line ~692-693), add:

```python
    # ---- golden-ratio card image (card.png) ----
    card_grp = p.add_mutually_exclusive_group()
    card_grp.add_argument("--card", dest="do_card", action="store_true", default=True,
                          help="also emit a golden-ratio transparent card.png (default on)")
    card_grp.add_argument("--no-card", dest="do_card", action="store_false",
                          help="do not emit card.png")
```

**Step 2: Pass `do_card` at the batch call site.** In `_run_batch`, the `standardize(...)` call (ends at line 566 with `crop_to_face=...`): add `do_card=getattr(item_args, "do_card", True),` as the final kwarg.

**Step 3: Pass `do_card` at the single call site.** In `main()`, the `standardize(...)` call (ends ~line 766): add `do_card=args.do_card,` as the final kwarg.

**Step 4: Record `photos.card` in the batch "ok" branch.** In `_run_batch`, locate the success block (line ~601-607). After `results.append(entry)` and before the verbose print, add:

```python
            if getattr(item_args, "do_card", True) and (item_dir / "card.png").exists():
                from golden_card import record_photos_card  # SCRIPT_DIR already on sys.path
                record_photos_card(item_dir)
```

**Step 5: Add a test that the flag wiring records photos.card.** Append to `IP/tests/test_standardize_card.py`:

```python
def test_cli_no_card_flag_parses_false():
    p = st._build_parser()
    assert p.parse_args(["x", "-o", "y"]).do_card is True
    assert p.parse_args(["x", "-o", "y", "--no-card"]).do_card is False
```

**Step 6: Run all standardize tests**

Run: `... pytest skills/plugins/richmondgeneral/skills/image-processor/tests/test_standardize_card.py skills/plugins/richmondgeneral/skills/image-processor/tests/test_standardize.py -v`
Expected: PASS (new tests + existing unchanged).

**Step 7: Commit**

```bash
cd /Users/scottybe/workspace/richmondgeneral/skills
git rev-parse --abbrev-ref HEAD
git add plugins/richmondgeneral/skills/image-processor/scripts/standardize.py \
        plugins/richmondgeneral/skills/image-processor/tests/test_standardize_card.py
git commit -m "feat(image-processor): --card/--no-card flag + record label.json photos.card

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Phase 3 — Full suite + dual-copy sync

### Task 6: Run the entire image-processor suite

**Step 1:** Run the full suite (Pre-flight test command). Expected: PASS — all prior tests (the CLAUDE.md baseline was 87 green) plus the new golden-card tests, 0 failures. If anything unrelated fails, STOP and use superpowers:systematic-debugging before continuing.

### Task 7: Mirror source → both plugin-cache copies

**Step 1: rsync the scripts + tests to both caches.**

```bash
SRC=/Users/scottybe/workspace/richmondgeneral/skills/plugins/richmondgeneral/skills/image-processor
for DST in \
  /Users/scottybe/.claude/plugins/cache/richmondgeneral/skills/image-processor \
  /Users/scottybe/.claude/plugins/cache/richmondgeneral/richmondgeneral/1.1.0/skills/image-processor; do
  rsync -a --exclude=__pycache__ "$SRC/scripts/" "$DST/scripts/"
  rsync -a --exclude=__pycache__ "$SRC/tests/"   "$DST/tests/"
done
```

**Step 2: Verify both caches have the new module + the `do_card` wiring.**

```bash
for DST in \
  /Users/scottybe/.claude/plugins/cache/richmondgeneral/skills/image-processor \
  /Users/scottybe/.claude/plugins/cache/richmondgeneral/richmondgeneral/1.1.0/skills/image-processor; do
  test -f "$DST/scripts/golden_card.py" && grep -q "do_card" "$DST/scripts/standardize.py" \
    && echo "OK  $DST" || echo "MISSING  $DST"
done
```
Expected: `OK` for both. (No commit — cache dirs are not the source repo.)

---

## Phase 4 — Detail item-card template → golden ratio + card-first (both copies)

> **Caveat to verify first:** the detail template has a variant-image system (`class="item-image variant-image" data-variant="as-found"`). Before editing, read the template's variant-switching JS (search the file for `variant` / `data-variant`) and confirm that setting the initial `src` to `card.png` with an `onerror` fallback does NOT break variant switching. If variant JS reassigns `.src` from a data attribute, point the "as-found" variant at `card.png` (fallback to the hero) so switching stays intact.

### Task 8: Items template — container to golden ratio + card-first hero

**Files:**
- Modify: `items/template/rg-item-card-template.html` — `.item-image-container` CSS (lines ~125-141) and the hero `<img>` (lines ~733-735).

**Step 1: Make the hero container hold the golden ratio.** In `.item-image-container`, add `aspect-ratio: 1.618;` and `width: 100%;` (keep the cream background + flex centering). The `.item-image` rule stays `object-fit: contain` so a non-cutout hero just letterboxes on cream.

**Step 2: Card-first with onerror fallback.** Change:
```html
<img src="{{IMAGE_URL}}" alt="{{ITEM_TITLE}}"
     class="item-image variant-image"
     data-variant="as-found">
```
to:
```html
<img src="./card.png"
     onerror="this.onerror=null;this.src='{{IMAGE_URL}}';"
     alt="{{ITEM_TITLE}}"
     class="item-image variant-image"
     data-variant="as-found"
     data-card="./card.png" data-hero="{{IMAGE_URL}}">
```
(`data-card`/`data-hero` let any variant JS choose deliberately; `onerror` covers items with no `card.png`.)

**Step 3: Verify**

Run: `grep -n "aspect-ratio: 1.618" items/template/rg-item-card-template.html && grep -n "this.src='{{IMAGE_URL}}'" items/template/rg-item-card-template.html`
Expected: both match.

### Task 9: Generator copy — same change

**Files:**
- Modify: `skills/plugins/richmondgeneral/skills/rg-full-auto/references/info-card-template.html` — `.item-image-container` CSS + hero `<img>` (line ~496, currently `<img src="./hero.png" ... class="item-image">`).

**Step 1:** Apply the same `aspect-ratio: 1.618;` container change.
**Step 2:** Change the hero img to card-first:
```html
<img src="./card.png" onerror="this.onerror=null;this.src='./hero.png';" alt="{{ITEM_TITLE}}" class="item-image">
```
**Step 3: Verify**
Run: `grep -n "aspect-ratio: 1.618" skills/plugins/richmondgeneral/skills/rg-full-auto/references/info-card-template.html && grep -n "this.src='./hero.png'" skills/plugins/richmondgeneral/skills/rg-full-auto/references/info-card-template.html`
Expected: both match.

### Task 10: Commit the detail-template changes (TWO repos)

```bash
# items repo (deploys on push — do NOT push yet; verify visually in Phase 7)
cd /Users/scottybe/workspace/richmondgeneral/items
git rev-parse --abbrev-ref HEAD
git add template/rg-item-card-template.html
git commit -m "feat(cards): detail card -> golden ratio, prefer card.png (onerror fallback to hero)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"

# skills repo (generator copy)
cd /Users/scottybe/workspace/richmondgeneral/skills
git rev-parse --abbrev-ref HEAD
git add plugins/richmondgeneral/skills/rg-full-auto/references/info-card-template.html
git commit -m "feat(rg-full-auto): info-card template -> golden ratio, prefer card.png

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Phase 5 — Gallery (`items/index.html`) → golden ratio + card-first

### Task 11: Gallery grid aspect ratio

**Files:**
- Modify: `items/index.html` — `.item-image` rule (lines ~237-251).

**Step 1:** Change `aspect-ratio: 4 / 3;` to `aspect-ratio: 1.618;` (keep cream bg + centering; the inner `img` keeps `object-fit: contain`).

**Step 2: Verify**
Run: `grep -n "aspect-ratio: 1.618" items/index.html`
Expected: matches; `grep -n "aspect-ratio: 4 / 3" items/index.html` returns nothing.

### Task 12: One JS snippet upgrades every card to card.png (generator-independent)

Rather than editing every hardcoded card, append a single script that, for each card image, derives the sibling `card.png` from the current hero `src`, tries it, and falls back to the hero on 404. Backfills current and future cards automatically.

**Files:**
- Modify: `items/index.html` — just before the closing `</body>`.

**Step 1:** Add:
```html
<script>
  // Prefer the golden-ratio card.png when an item has one; fall back to its hero on 404.
  document.querySelectorAll('.item-image img').forEach(function (img) {
    var hero = img.getAttribute('src');
    var card = hero.replace(/hero\.(jpe?g|png|webp)$/i, 'card.png');
    if (card !== hero) {
      img.addEventListener('error', function onErr() {
        img.removeEventListener('error', onErr);
        img.src = hero;
      });
      img.src = card;
    }
  });
</script>
```

**Step 2: Verify**
Run: `grep -n "card.png" items/index.html`
Expected: the snippet matches.

**Step 3: Commit (items repo — still no push)**
```bash
cd /Users/scottybe/workspace/richmondgeneral/items
git rev-parse --abbrev-ref HEAD
git add index.html
git commit -m "feat(gallery): grid -> golden ratio + prefer card.png with hero fallback

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Phase 6 — Square: card.png as an ADDITIONAL image

Square center-crops grid thumbnails to square, so `card.png` goes in as an extra image; the current hero stays primary. This is a runtime/ops step (not unit-testable) via the existing upload skill — see CLAUDE.md "Square add image".

### Task 13: Document + wire the additional-image upload

**Files:**
- Modify: `ops/docs/RG-listing-SOP.md` (the §4 photo/Square area) — add a line: after a cutout item gets `card.png`, upload it to Square **without `--primary`** so it appears as an additional catalog image; verify the new `image_id` is in `image_ids` and the primary is unchanged.

**Exact command (per item, over the bridge — omit `--primary`):**
```bash
uv run --project skills/plugins/richmondgeneral \
  python skills/plugins/richmondgeneral/skills/square-image-upload-cowork/upload_to_square.py \
  --item-id <SQUARE_ITEM_ID> --source items/RG-XXXX/card.png
```
(Resolve `<SQUARE_ITEM_ID>` from `items/RG-XXXX/label.json -> channels.square`.)

**Step 1:** Add the SOP line. **Step 2:** Commit:
```bash
cd /Users/scottybe/workspace/richmondgeneral/ops
git rev-parse --abbrev-ref HEAD
git add docs/RG-listing-SOP.md
git commit -m "docs(SOP): upload card.png to Square as an additional image (not primary)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Phase 7 — Backfill, verify, publish

### Task 14: Backfill cards for existing cutout items

**Step 1:** Dry list what has a cutout vs not:
```bash
cd /Users/scottybe/workspace/richmondgeneral
uv run --project skills/plugins/richmondgeneral \
  python skills/plugins/richmondgeneral/skills/image-processor/scripts/golden_card.py --batch items/
```
Expected: prints `✓` for items with a real cutout (writes `items/RG-XXXX/card.png` + sets `photos.card`), `-` skipped for opaque/flat-goods/no-cutout. Note the made/skipped counts.

### Task 15: Visual verification (REQUIRED before any push)

Use superpowers:verification-before-completion. Open one backfilled item locally and confirm:
- `items/RG-XXXX/card.png` is a horizontal golden rectangle, item centered, transparent margins.
- The detail page shows `card.png` in the golden frame; an item WITHOUT a card still shows its hero (onerror fallback works — check the console shows the fallback, not a broken image).
- The gallery grid renders golden-ratio cards; mixed card/hero items both look right.
```bash
cd /Users/scottybe/workspace/richmondgeneral/items && python3 -m http.server 8765
# visit http://localhost:8765/  and  http://localhost:8765/RG-XXXX/
```

### Task 16: Stage card.png files + push each repo (concurrency protocol)

For the items repo, add the backfilled cards with **explicit paths** (never `-A`):
```bash
cd /Users/scottybe/workspace/richmondgeneral/items
git rev-parse --abbrev-ref HEAD
git add $(printf 'RG-%s/card.png ' ...)   # only the card.png files that were created
git add $(printf 'RG-%s/label.json ' ...) # only labels that gained photos.card
git commit -m "chore(items): backfill golden card.png + photos.card for cutout items

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```
Then, for EACH repo touched (skills, items, ops), before pushing:
```bash
git fetch -q origin
git log --oneline origin/main..main      # confirm every listed commit is coherent/expected
git rev-list --left-right --count origin/main...main   # must show 0 behind for a clean fast-forward
git push origin main                     # never --force
```
Pushing `items/` deploys GitHub Pages. After deploy, spot-check the live gallery + one item page.

---

## Done criteria
- `golden_card.py` + tests green; full image-processor suite green; both cache copies synced and verified.
- Detail template (both copies) + gallery on the golden ratio, rendering `card.png` with a working hero fallback.
- Existing cutout items backfilled; `photos.card` recorded; opaque/flat-goods correctly skipped.
- Square SOP updated; at least one item's `card.png` uploaded as an additional image and verified in `image_ids`.
- All repos pushed via the concurrency protocol; live site spot-checked.

## Notes / skills to use
- @superpowers:test-driven-development for Phases 1-2 (red→green→commit).
- @superpowers:systematic-debugging if any test fails unexpectedly.
- @superpowers:verification-before-completion before Task 15/16 (evidence before claiming done).
- Out of scope (YAGNI): drop shadows, generative backgrounds, re-cutting non-cutout items, responsive multi-res variants, changing the Square primary image.
