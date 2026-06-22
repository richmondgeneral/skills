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
    _draw_wordmark(canvas, (0, 0, hero_w, CANVAS), _sku(item_dir))

    rail_x = hero_w + GUTTER
    rail_w = CANVAS - rail_x
    n = len(sel["rail"])
    cell_h = (CANVAS - (n - 1) * GUTTER) // n
    for i, slot in enumerate(sel["rail"]):
        y = i * (cell_h + GUTTER)
        h = cell_h if i < n - 1 else CANVAS - y          # last cell absorbs rounding to the edge
        canvas.paste(crop_cover(Image.open(slot["path"]), rail_w, h), (rail_x, y))
        _draw_caption(canvas, (rail_x, y, rail_w, h), slot["caption"])

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
