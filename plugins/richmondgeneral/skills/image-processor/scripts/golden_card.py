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
  (exit code 2 = source was opaque/degenerate and was skipped — not an error)
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
MIN_CUTOUT_PX = 64            # bbox long side below this => alpha speck/noise, not a real cutout => skip
CARD_FILENAME = "card.png"


def golden_size(width: int = DEFAULT_WIDTH) -> tuple[int, int]:
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
    out_path = Path(out_path) if out_path else hero_path.parent / CARD_FILENAME
    src = Image.open(hero_path)
    rgba = src.convert("RGBA")

    def _skip():
        # No valid cutout to float — ensure no stale card lingers for this hero.
        if out_path.exists():
            out_path.unlink()
        return None

    if not _has_cutout(rgba):
        return _skip()                 # opaque full-bleed (flat-goods / keep-bg)
    bbox = rgba.getchannel("A").getbbox()
    if bbox is None:
        return _skip()                 # fully transparent — nothing to float
    bx0, by0, bx1, by1 = bbox
    if max(bx1 - bx0, by1 - by0) < MIN_CUTOUT_PX:
        return _skip()                 # degenerate speck (alpha noise), not a real cutout
    obj = rgba.crop(bbox)
    ow, oh = obj.size

    cw, ch = golden_size(width)
    scale = min((fill * cw) / ow, (fill * ch) / oh)   # limiting dimension wins
    new_w, new_h = max(1, round(ow * scale)), max(1, round(oh * scale))
    obj = obj.resize((new_w, new_h), Image.LANCZOS)

    canvas = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    canvas.paste(obj, ((cw - new_w) // 2, (ch - new_h) // 2), obj)

    meta = PngInfo()                                   # carry provenance text chunks (Copyright/Title)
    for k, v in getattr(src, "text", {}).items():
        meta.add_text(k, v)
    canvas.save(out_path, "PNG", pnginfo=meta)
    return out_path


def record_photos_card(item_dir, card_filename: str = CARD_FILENAME) -> None:
    """Reconcile label.json -> photos.card with the card file's existence: set it when
    <item_dir>/<card_filename> exists, remove a stale entry when it does not. Writes ONLY
    when the value actually changes (so a bulk backfill never reformats unchanged files,
    and never adds an empty 'photos' block to a no-card item). No-op if label.json is absent."""
    p = Path(item_dir) / "label.json"
    if not p.exists():
        return
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"warning: {p}: {exc}", file=sys.stderr)
        return
    has_card = (Path(item_dir) / card_filename).exists()
    photos = data.get("photos")
    current = photos.get("card") if isinstance(photos, dict) else None
    desired = card_filename if has_card else None
    if current == desired:
        return  # already correct — do not rewrite the file
    photos = data.setdefault("photos", {})
    if desired is None:
        photos.pop("card", None)
    else:
        photos["card"] = desired
    try:
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
        record_photos_card(d)            # reconcile photos.card with card.png existence
        if out is None:
            skipped += 1
            print(f"  - {d.name}: no cutout, skipped")
        else:
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
