#!/usr/bin/env python3
"""Standardize a photo into a catalog-quality PUBLIC image per the RG listing SOP.

Produces a cohesive "thematic thread" public image: **square 1:1, object centered,
color-corrected toward neutral lighting, background removed (transparent)**. It only
changes color and geometry — it never edits the object's content, so physical flaws
(chips, crazing, wear) are preserved per the honesty rule.

Pipeline: color-correct (gray-world white balance + mild auto-contrast) -> background
removal (reuses process.py's model routing/fallbacks) -> square pad + center -> resize.
Output is a transparent PNG. The raw input is never modified; results go to --output.

Run via `uv run python standardize.py ...` (Pillow lives in the uv env). Background
removal is an AI call (Gemini / remove.bg) and needs the usual keys + credits; the
color + square steps are deterministic and offline. `--no-bg` skips bg removal (e.g.
to re-square an already-transparent hero without another API call).
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image, ImageOps, ImageStat, ImageFilter
from PIL.PngImagePlugin import PngInfo

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROCESS_PY = os.path.join(SCRIPT_DIR, "process.py")

OVERRIDE_FILE = "label.json"

# Maps photo_overrides keys → (argparse dest, coerce fn).
# Fields listed here are the only ones the JSON file may influence.
# "notes" is intentionally omitted — it's documentation-only.
OVERRIDE_FIELDS: Dict[str, tuple] = {
    "no_color":       ("no_color",       bool),
    "no_bg":          ("no_bg",          bool),
    "allow_rect_mask": ("allow_rect_mask", bool),
    "shadow":         ("shadow",         bool),
    "fill":           ("fill",           float),
    "model":          ("model",          str),
    "size":           ("size",           int),
    "copyright":      ("copyright",      str),
    "sku":            ("sku",            str),
    "wb":             ("wb",             str),
}
DEFAULT_LOGO = os.path.expanduser("~/workspace/richmondgeneral/brand/assets/richmond-general-logo.png")


# ---------------------------------------------------------------------------
# Per-item override helpers
# ---------------------------------------------------------------------------

def load_item_overrides(item_dir) -> Dict[str, Any]:
    """Load the `photo_overrides` block from label.json in item_dir.
    Returns {} on missing or invalid.
    """
    path = Path(item_dir) / OVERRIDE_FILE
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        overrides = data.get("photo_overrides", {})
        return overrides if isinstance(overrides, dict) else {}
    except Exception as exc:
        print(f"warning: {path}: {exc}", file=sys.stderr)
        return {}


def apply_overrides(
    args: argparse.Namespace,
    overrides: Dict[str, Any],
    parser: argparse.ArgumentParser,
) -> List[str]:
    """Merge JSON overrides into already-parsed args; CLI-explicit values win.

    For every field in OVERRIDE_FIELDS: if the arg's current value still
    matches the argparse default (i.e. the user did not set it on the CLI),
    replace it with the JSON value.  Returns the list of field names changed.
    """
    defaults = {a.dest: a.default for a in parser._actions if hasattr(a, "dest")}
    changed: List[str] = []
    for json_key, (dest, coerce) in OVERRIDE_FIELDS.items():
        if json_key not in overrides:
            continue
        if getattr(args, dest, None) != defaults.get(dest):
            continue  # user set this explicitly on CLI — respect it
        try:
            setattr(args, dest, coerce(overrides[json_key]))
            changed.append(json_key)
        except (ValueError, TypeError):
            print(
                f"warning: {OVERRIDE_FILE}: invalid value for '{json_key}'",
                file=sys.stderr,
            )
    return changed


def _split_alpha(img):
    """(rgb, alpha-or-None) — so color ops never destroy a transparent background."""
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        return rgba.convert("RGB"), rgba.getchannel("A")
    return img.convert("RGB"), None


def _merge_alpha(rgb, alpha):
    if alpha is None:
        return rgb
    out = rgb.convert("RGBA")
    out.putalpha(alpha)
    return out


def gray_world_white_balance(img, clamp=(0.6, 1.7)):
    """Neutralize a lighting color cast: scale R/G/B so each channel mean matches the
    overall gray mean. Clamped so we correct the cast without wild shifts. Preserves alpha."""
    rgb, alpha = _split_alpha(img)
    r, g, b = ImageStat.Stat(rgb).mean
    gray = (r + g + b) / 3.0

    def scale(m):
        s = gray / m if m > 1e-6 else 1.0
        return max(clamp[0], min(clamp[1], s))

    sr, sg, sb = scale(r), scale(g), scale(b)
    rC, gC, bC = rgb.split()
    rC = rC.point(lambda v: min(255, int(v * sr)))
    gC = gC.point(lambda v: min(255, int(v * sg)))
    bC = bC.point(lambda v: min(255, int(v * sb)))
    return _merge_alpha(Image.merge("RGB", (rC, gC, bC)), alpha)


def background_reference_white_balance(img, border_frac=0.06, clamp=(0.6, 1.7), min_brightness=40):
    """White-balance from the image BORDER (the backdrop) as the neutral reference, so a
    warm/patinated OBJECT (brass, Bakelite, parchment) keeps its true color — only the room's
    lighting cast is removed. Falls back to gray-world if the border isn't a usable neutral
    (too dark, or strongly colored — e.g. a colored cloth backdrop rather than a lighting cast)."""
    rgb, alpha = _split_alpha(img)
    w, h = rgb.size
    bw = max(1, int(min(w, h) * border_frac))
    mask = Image.new("L", (w, h), 0)
    mask.paste(255, (0, 0, w, h))
    mask.paste(0, (bw, bw, w - bw, h - bw))  # 255 ring around the edge, 0 in the center
    r, g, b = ImageStat.Stat(rgb, mask).mean
    gray = (r + g + b) / 3.0
    if gray < min_brightness or (max(r, g, b) - min(r, g, b)) > 0.6 * gray:
        return gray_world_white_balance(img, clamp=clamp)  # border unusable -> whole-image fallback

    def scale(m):
        s = gray / m if m > 1e-6 else 1.0
        return max(clamp[0], min(clamp[1], s))

    sr, sg, sb = scale(r), scale(g), scale(b)
    rC, gC, bC = rgb.split()
    rC = rC.point(lambda v: min(255, int(v * sr)))
    gC = gC.point(lambda v: min(255, int(v * sg)))
    bC = bC.point(lambda v: min(255, int(v * sb)))
    return _merge_alpha(Image.merge("RGB", (rC, gC, bC)), alpha)


_WB_METHODS = {
    "background": background_reference_white_balance,
    "grayworld": gray_world_white_balance,
}


def color_correct(img, wb="background"):
    """White-balance (default: backdrop-referenced, patina-safe) + a mild auto-contrast (exposure
    tidy). Content-safe; preserves a transparent background. wb='none' skips white balance entirely
    (keeps the auto-contrast — useful for color-critical patina you don't want shifted at all)."""
    balanced = img if wb == "none" else _WB_METHODS.get(wb, background_reference_white_balance)(img)
    rgb, alpha = _split_alpha(balanced)
    return _merge_alpha(ImageOps.autocontrast(rgb, cutoff=0.5), alpha)


def square_pad_centered(img, fill=0.85, size=2000, shadow=False, bg=(0, 0, 0, 0)):
    """Crop to the object (alpha bbox when present), then center it on a transparent
    square canvas so the longest side fills `fill` fraction of the canvas.
    Adds an optional soft drop shadow for grounding."""
    rgba = img.convert("RGBA")
    bbox = rgba.getchannel("A").getbbox() or rgba.getbbox() or (0, 0, rgba.width, rgba.height)
    obj = rgba.crop(bbox)
    w, h = obj.size
    
    # Calculate canvas side to ensure object fills `fill` of the frame
    side = int(round(max(w, h) / fill)) if fill > 0 else max(w, h)
    canvas = Image.new("RGBA", (side, side), bg)
    
    paste_x = (side - w) // 2
    paste_y = (side - h) // 2
    
    # Apply grounding shadow if requested (blur/offset scale with size so it reads the
    # same on a 400px and a 4000px source — a fixed 10px blur vanishes on big objects).
    if shadow:
        blur = max(6, int(side * 0.012))
        drop = max(4, int(side * 0.02))
        shadow_mask = obj.getchannel("A").point(lambda a: int(a * 0.4))
        shadow_img = Image.new("RGBA", obj.size, (0, 0, 0, 0))
        shadow_img.putalpha(shadow_mask)
        shadow_img = shadow_img.filter(ImageFilter.GaussianBlur(blur))
        canvas.paste(shadow_img, (paste_x, paste_y + drop), shadow_img)

    canvas.paste(obj, (paste_x, paste_y), obj)
    if size and side != size:
        canvas = canvas.resize((size, size), Image.LANCZOS)
    return canvas


def apply_watermark(img, logo_path=DEFAULT_LOGO, opacity=0.45, scale=0.16, margin=0.03):
    """Composite a subtle, semi-transparent logo into the bottom-right corner.

    For SOCIAL / share variants (Facebook, Pinterest, Marketplace) — NOT the eBay or
    Square catalog hero, where added artwork on the primary image hurts listing quality.
    """
    base = img.convert("RGBA")
    logo = Image.open(logo_path).convert("RGBA")
    target_w = max(1, int(base.width * scale))
    logo = logo.resize((target_w, max(1, round(logo.height * target_w / logo.width))), Image.LANCZOS)
    logo.putalpha(logo.getchannel("A").point(lambda v: int(v * opacity)))
    m = int(base.width * margin)
    base.alpha_composite(logo, (base.width - logo.width - m, base.height - logo.height - m))
    return base


def remove_background(src, dst, model=None, allow_rect_mask=False):
    """Reuse process.py's routing/fallbacks for the transparent cutout (same interpreter).
    Surfaces process.py's own error (rect-mask / credits / etc.) instead of swallowing it."""
    cmd = [sys.executable, PROCESS_PY, src, "-o", dst, "--task", "remove-bg"]
    if model:
        cmd += ["--model", model]
    if allow_rect_mask:
        cmd += ["--allow-rect-mask"]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=SCRIPT_DIR)
    if r.returncode != 0:
        raise RuntimeError("background removal failed:\n" + (r.stderr.strip() or r.stdout.strip()))


def standardize(input_path, output_path, do_color=True, do_bg=True, fill=0.85, size=2000,
                shadow=False, copyright_text=None, sku=None, watermark=False,
                watermark_logo=DEFAULT_LOGO, wb="background", model=None, allow_rect_mask=False):
    with tempfile.TemporaryDirectory() as td:
        cur = input_path
        if do_color:
            cc = os.path.join(td, "cc.png")
            color_correct(Image.open(input_path), wb=wb).save(cc)
            cur = cc
        if do_bg:
            transp = os.path.join(td, "transp.png")
            remove_background(cur, transp, model=model, allow_rect_mask=allow_rect_mask)
            cur = transp
            
        final_img = square_pad_centered(Image.open(cur), fill=fill, size=size, shadow=shadow)
        if watermark:
            final_img = apply_watermark(final_img, logo_path=watermark_logo)

        # PIL drops GPS and device EXIF automatically when saving without `exif` kwarg.
        # We explicitly inject our provenance metadata here.
        metadata = PngInfo()
        if copyright_text:
            metadata.add_text("Copyright", copyright_text)
        if sku:
            metadata.add_text("Title", sku)
            
        final_img.save(output_path, "PNG", pnginfo=metadata)
    return output_path


# ---------------------------------------------------------------------------
# Batch helpers
# ---------------------------------------------------------------------------

SUPPORTED_HERO_EXTENSIONS = {".jpeg", ".jpg", ".png", ".webp", ".heic"}


def _find_hero(item_dir: Path, glob: str = "hero.*") -> Optional[Path]:
    """Return the first hero image in item_dir matching glob, or None."""
    candidates = sorted(
        p for p in item_dir.glob(glob)
        if p.suffix.lower() in SUPPORTED_HERO_EXTENSIONS
    )
    return candidates[0] if candidates else None


def _run_batch(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    """Process every item subdirectory under --batch-items-dir.

    For each subdirectory:
      1. Locate the hero image (default glob: ``hero.*``).
      2. Load ``standardize.json`` from that directory.
      3. Merge JSON overrides on top of global CLI defaults (CLI wins).
      4. Call standardize() and write ``{hero_stem}{suffix}.png`` in-place.

    Exits non-zero if any item fails.
    """
    items_dir = Path(args.batch_items_dir).expanduser().resolve()
    if not items_dir.is_dir():
        print(f"error: --batch-items-dir not found: {items_dir}", file=sys.stderr)
        sys.exit(1)

    hero_glob: str = args.hero_glob
    suffix: str = args.suffix
    results: List[Dict[str, Any]] = []

    item_dirs = sorted(d for d in items_dir.iterdir() if d.is_dir())
    if not item_dirs:
        print("No item subdirectories found.", file=sys.stderr)
        sys.exit(0)

    for item_dir in item_dirs:
        hero = _find_hero(item_dir, hero_glob)
        if hero is None:
            continue  # no hero image — skip silently

        output = item_dir / f"{hero.stem}{suffix}.png"
        if output.exists() and not args.overwrite:
            results.append({"item": item_dir.name, "status": "skipped",
                            "reason": "output_exists", "output": str(output)})
            continue

        # Clone the parsed args so per-item overrides don't bleed between items
        item_args = argparse.Namespace(**vars(args))
        overrides = load_item_overrides(item_dir)
        notes = overrides.pop("notes", "")  # documentation-only; not passed to pipeline
        changed = apply_overrides(item_args, overrides, parser) if overrides else []
        if changed and args.verbose:
            print(f"  [{item_dir.name}] overrides: {', '.join(changed)}", file=sys.stderr)

        # Default the embedded SKU to the item directory name (e.g. "RG-0001")
        effective_sku = item_args.sku or item_dir.name

        try:
            standardize(
                str(hero), str(output),
                do_color=not item_args.no_color,
                do_bg=not item_args.no_bg,
                fill=item_args.fill,
                size=item_args.size,
                shadow=item_args.shadow,
                copyright_text=item_args.copyright,
                sku=effective_sku,
                watermark=item_args.watermark,
                watermark_logo=item_args.watermark_logo,
                model=item_args.model,
                allow_rect_mask=item_args.allow_rect_mask,
                wb=item_args.wb,
            )
            entry: Dict[str, Any] = {"item": item_dir.name, "status": "ok",
                                     "output": str(output)}
            if notes:
                entry["notes"] = notes
            if changed:
                entry["overrides"] = changed
            results.append(entry)
            if not args.json_out:
                print(f"  \u2713 {item_dir.name}  -> {output.name}")
        except Exception as exc:
            entry = {"item": item_dir.name, "status": "error", "error": str(exc)}
            if notes:
                entry["notes"] = notes
            results.append(entry)
            print(f"  \u2717 {item_dir.name}: {exc}", file=sys.stderr)
            if args.fail_fast:
                break

    n_ok = sum(1 for r in results if r["status"] == "ok")
    n_skip = sum(1 for r in results if r["status"] == "skipped")
    n_err = sum(1 for r in results if r["status"] == "error")

    if args.json_out:
        print(json.dumps({"ok": n_ok, "skipped": n_skip, "errors": n_err,
                          "results": results}, indent=2))
    else:
        print(f"\nBatch complete: ok={n_ok}  skipped={n_skip}  errors={n_err}")

    sys.exit(0 if n_err == 0 else 1)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Standardize a photo into a public catalog image.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Per-item overrides\n"
            "  Place a standardize.json next to the input image (or inside the item\n"
            "  subdirectory in --batch-items-dir mode).  Supported keys mirror the\n"
            "  long-form flags below: no_color, no_bg, allow_rect_mask, shadow,\n"
            "  fill, model, size, copyright, sku.  CLI flags always win.\n"
            "  Add a \"notes\" key for human-readable documentation; it is ignored.\n"
        ),
    )

    # ---- input / output (optional when --batch-items-dir is used) ----
    p.add_argument("input", nargs="?", help="input image path (omit with --batch-items-dir)")
    p.add_argument("-o", "--output", help="output PNG path (omit with --batch-items-dir)")

    # ---- pipeline stages ----
    p.add_argument("--no-color", action="store_true", help="skip color correction")
    p.add_argument("--wb", choices=["background", "grayworld", "none"], default="background",
                   help="white balance method (default: background reference)")
    p.add_argument("--no-bg", action="store_true",
                   help="skip background removal (input already transparent)")
    p.add_argument("--fill", type=float, default=0.85,
                   help="fraction of canvas the object fills (default 0.85)")
    p.add_argument("--shadow", action="store_true", help="add a grounding drop shadow")
    p.add_argument("--size", type=int, default=2000,
                   help="output square side in px (0 = keep native, default 2000)")
    p.add_argument("--model", choices=["nano-banana", "gemini25", "removebg", "auto"],
                   help="bg-removal model (default auto; removebg gives best cutouts)")
    p.add_argument("--allow-rect-mask", action="store_true",
                   help="accept a rectangular bg-removal mask instead of failing")

    # ---- metadata ----
    p.add_argument("--copyright", type=str,
                   help="embed Copyright PNG metadata (e.g. 'Richmond General')")
    p.add_argument("--sku", type=str, help="embed SKU as PNG Title metadata")

    # ---- social watermark (opt-in; NOT for Square/eBay hero) ----
    p.add_argument("--watermark", action="store_true",
                   help="composite RG logo bottom-right (social/share variant only)")
    p.add_argument("--watermark-logo", default=DEFAULT_LOGO,
                   help="logo PNG for --watermark")

    # ---- batch mode ----
    p.add_argument("--batch-items-dir", metavar="DIR",
                   help="process every subdirectory of DIR as an item folder")
    p.add_argument("--hero-glob", default="hero.*",
                   help="glob for the hero image inside each item dir (default: hero.*)")
    p.add_argument("--suffix", default="-std",
                   help="output filename suffix in batch mode (default: -std)")
    p.add_argument("--overwrite", action="store_true",
                   help="overwrite existing output files (batch mode)")
    p.add_argument("--fail-fast", action="store_true",
                   help="stop on first error (batch mode)")
    p.add_argument("--json", dest="json_out", action="store_true",
                   help="emit JSON result summary")

    # ---- misc ----
    p.add_argument("--straighten", action="store_true",
                   help="(no-op — auto-deskew needs opencv; shoot straight for now)")
    p.add_argument("-v", "--verbose", action="store_true")
    return p


def main() -> None:
    p = _build_parser()
    args = p.parse_args()

    if args.straighten:
        print("warning: --straighten is not implemented; skipping.", file=sys.stderr)

    # ---- batch mode ----
    if args.batch_items_dir:
        _run_batch(args, p)
        return  # _run_batch calls sys.exit internally

    # ---- single-image mode ----
    if not args.input:
        p.error("input is required (or use --batch-items-dir for batch mode)")
    if not args.output:
        p.error("-o/--output is required in single-image mode")

    # Auto-load standardize.json from the input's parent directory.
    # JSON values only fill in what the CLI left at its default; explicit
    # flags always win.  Log applied overrides so the caller can audit them.
    overrides = load_item_overrides(Path(args.input).parent)
    overrides.pop("notes", None)  # documentation-only key
    if overrides:
        changed = apply_overrides(args, overrides, p)
        if changed:
            print(
                f"info: applied overrides from {OVERRIDE_FILE}: {', '.join(changed)}",
                file=sys.stderr,
            )

    out = standardize(
        args.input, args.output,
        do_color=not args.no_color,
        do_bg=not args.no_bg,
        fill=args.fill,
        size=args.size,
        shadow=args.shadow,
        copyright_text=args.copyright,
        sku=args.sku,
        watermark=args.watermark,
        watermark_logo=args.watermark_logo,
        model=args.model,
        allow_rect_mask=args.allow_rect_mask,
        wb=args.wb,
    )
    print(out)


if __name__ == "__main__":
    main()
