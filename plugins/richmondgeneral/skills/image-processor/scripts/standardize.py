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
import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image, ImageOps, ImageStat, ImageFilter
from PIL.PngImagePlugin import PngInfo

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROCESS_PY = os.path.join(SCRIPT_DIR, "process.py")

OVERRIDE_FILE = "label.json"
PHOTO_PROFILES_FILE = os.path.expanduser("~/workspace/richmondgeneral/ops/docs/photo-profiles.json")

# Maps photo_overrides keys → (argparse dest, coerce fn).
# Fields listed here are the only ones the JSON file may influence.
# "notes" is intentionally omitted — it's documentation-only.
OVERRIDE_FIELDS: Dict[str, tuple] = {
    "no_color":       ("no_color",       bool),
    "no_bg":          ("no_bg",          bool),
    "deskew":         ("deskew",         bool),
    "perspective_correct": ("perspective_correct", bool),
    "crop_to_face":   ("crop_to_face",   bool),
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

def load_item_metadata(item_dir) -> Dict[str, Any]:
    """Load metadata (label.json) from item_dir.
    Returns {} on missing or invalid.
    """
    path = Path(item_dir) / OVERRIDE_FILE
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        print(f"warning: {path}: {exc}", file=sys.stderr)
        return {}


def update_label_json_status(item_dir, status: str):
    path = Path(item_dir) / OVERRIDE_FILE
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if "photo_overrides" not in data:
            data["photo_overrides"] = {}
        data["photo_overrides"]["status"] = status
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception as exc:
        print(f"warning: failed to update {path}: {exc}", file=sys.stderr)


def load_photo_profiles() -> Dict[str, Any]:
    path = Path(PHOTO_PROFILES_FILE)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"warning: {path}: {exc}", file=sys.stderr)
        return {}


def infer_material(label_data: Dict[str, Any], profiles_json: Dict[str, Any]) -> Optional[str]:
    search_fields = profiles_json.get("material_source", {}).get("search_fields", ["attributes", "product_name"])
    
    text_to_search = ""
    for field in search_fields:
        val = label_data.get(field)
        if val and isinstance(val, str):
            text_to_search += " " + val.lower()
            
    if not text_to_search:
        return None
        
    for material in profiles_json.get("material_to_profile", {}).keys():
        if material.lower() in text_to_search:
            return material
            
    return None

def resolve_profile(label_data: Dict[str, Any], profiles_json: Dict[str, Any]) -> str:
    if not profiles_json:
        return "standard"
    
    overrides = label_data.get("photo_overrides", {})
    if "profile" in overrides:
        return overrides["profile"]
    
    material = infer_material(label_data, profiles_json)
    if material and material in profiles_json.get("material_to_profile", {}):
        return profiles_json["material_to_profile"][material]
    
    category = label_data.get("category")
    if category and category in profiles_json.get("category_fallback", {}):
        return profiles_json["category_fallback"][category]
    
    return profiles_json.get("default_profile", "standard")


def evaluate_mask_gate(mask_quality: Dict[str, Any], profile: str, profiles_json: Dict[str, Any]) -> Optional[str]:
    """Evaluate mask quality against gate rules. Returns trip reason if gated, else None."""
    gate_rules = profiles_json.get("mask_gate", {})
    if profile in gate_rules.get("skip_gate_for_profiles", []):
        return None
        
    for rule in gate_rules.get("force_manual_if_any", []):
        if "unless_profile" in rule and rule["unless_profile"] == profile:
            continue
            
        field = rule.get("field")
        op = rule.get("op")
        val = mask_quality.get(field)
        
        if val is None:
            continue
            
        if op == "is_true" and val:
            return field
        elif op == "gte" and val >= rule.get("value", float('inf')):
            return field
        elif op == "lte" and val <= rule.get("value", -float('inf')):
            return field
            
    return None


def apply_overrides(
    args: argparse.Namespace,
    profile_flags: Dict[str, Any],
    overrides: Dict[str, Any],
    parser: argparse.ArgumentParser,
    sys_args: Optional[List[str]] = None
) -> List[str]:
    """Merge JSON overrides into already-parsed args; CLI-explicit values win.

    Defaults < profile_flags < photo_overrides < CLI explicit args.
    """
    changed: List[str] = []
    
    combined = dict(profile_flags)
    combined.update(overrides)
    
    if sys_args is None:
        sys_args = sys.argv[1:]
        
    cli_args_set = set()
    for arg in sys_args:
        if arg.startswith("--"):
            clean_arg = arg.lstrip("-").split("=")[0]
            cli_args_set.add(clean_arg.replace("-", "_"))

    for json_key, (dest, coerce) in OVERRIDE_FIELDS.items():
        if json_key not in combined:
            continue
        if dest in cli_args_set:
            continue  # user set this explicitly on CLI — respect it
        try:
            setattr(args, dest, coerce(combined[json_key]))
            changed.append(json_key)
        except (ValueError, TypeError):
            print(
                f"warning: invalid value for '{json_key}'",
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


def remove_background(src, dst, model=None, allow_rect_mask=False) -> Optional[Dict[str, Any]]:
    """Reuse process.py's routing/fallbacks for the transparent cutout (same interpreter).
    Surfaces process.py's own error (rect-mask / credits / etc.) instead of swallowing it.
    Returns mask_quality dictionary if available."""
    cmd = [sys.executable, PROCESS_PY, src, "-o", dst, "--task", "remove-bg", "--json"]
    if model:
        cmd += ["--model", model]
    if allow_rect_mask:
        cmd += ["--allow-rect-mask"]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=SCRIPT_DIR)
    
    mask_quality = None
    if r.stdout:
        try:
            data = json.loads(r.stdout)
            mask_quality = data.get("metadata", {}).get("mask_quality")
        except Exception:
            pass
            
    if r.returncode != 0:
        err_msg = r.stderr.strip() or r.stdout.strip()
        try:
            data = json.loads(r.stdout)
            if "error" in data:
                err_msg = data["error"]
        except Exception:
            pass
        raise RuntimeError("background removal failed:\n" + err_msg)
        
    return mask_quality


def _deskew_flat_goods(src_path, input_path, size):
    """flat-goods path: perspective-correct the flat item's face to straight-on.

    Returns (final_img_or_None, mask_quality). On low confidence / non-rectangular
    / missing cv2 returns (None, {"deskew_needs_manual": True, ...}) so the batch
    routes the item to the manual queue instead of emitting a bad crop.
    """
    try:
        sys.path.insert(0, SCRIPT_DIR)
        from deskew import deskew_to_face, residual_tilt_deg, _CV2_OK
        import cv2  # provided by opencv-python-headless (plugin dep, 2026-06-20)
    except Exception:
        return None, {"deskew_needs_manual": True, "reason": "cv2_unavailable"}
    if not _CV2_OK:
        return None, {"deskew_needs_manual": True, "reason": "cv2_unavailable"}
    bgr = cv2.imread(src_path)
    if bgr is None:
        bgr = cv2.imread(input_path)
    if bgr is None:
        return None, {"deskew_needs_manual": True, "reason": "unreadable_input"}
    res = deskew_to_face(bgr)
    if not res.get("ok"):
        return None, {"deskew_needs_manual": True,
                      "reason": res.get("reason", "deskew_failed"),
                      "residual_tilt_deg": res.get("angle_in")}
    out_bgr = res["image"]
    after = residual_tilt_deg(out_bgr).get("tilt_deg")
    pil = Image.fromarray(out_bgr[:, :, ::-1])  # BGR -> RGB, opaque full-bleed face
    if size and size > 0:
        w0, h0 = pil.size
        if max(w0, h0) > size:
            if w0 >= h0:
                pil = pil.resize((size, max(1, round(h0 * size / w0))), Image.LANCZOS)
            else:
                pil = pil.resize((max(1, round(w0 * size / h0)), size), Image.LANCZOS)
    return pil, {"residual_tilt_deg": after, "flat_goods": True,
                 "method": res.get("method"), "aspect": res.get("aspect"),
                 "deskew_confidence": res.get("confidence")}


def bake_orientation(img: Image.Image) -> Image.Image:
    """Bake EXIF orientation into pixels ONCE and drop the tag, so every later
    tool/viewer agrees and no second blind rotation is ever needed. This is the
    root fix for the Atari batch (RG-0036–0051), which shipped 90° sideways
    because a hardcoded rotation was applied ON TOP of exif_transpose. After
    this, downstream steps must NOT rotate again."""
    out = ImageOps.exif_transpose(img)
    if out is None:
        out = img
    exif = out.getexif()
    if 0x0112 in exif:                # belt-and-suspenders; exif_transpose usually clears it
        del exif[0x0112]
        out.info["exif"] = exif.tobytes()
    return out


def standardize(input_path, output_path, do_color=True, do_bg=True, fill=0.85, size=2000,
                shadow=False, copyright_text=None, sku=None, watermark=False,
                watermark_logo=DEFAULT_LOGO, wb="background", model=None, allow_rect_mask=False,
                do_deskew=False, perspective_correct=False, crop_to_face=False, do_card=True):
    mask_quality = None
    with tempfile.TemporaryDirectory() as td:
        # Bake EXIF orientation into pixels ONCE, up front, so EVERY downstream
        # step sees correctly-oriented pixels — including the cv2 deskew path,
        # which re-reads input_path and would otherwise ignore EXIF orientation.
        # No step after this may apply a second rotation.
        baked = os.path.join(td, "baked.png")
        bake_orientation(Image.open(input_path)).save(baked)
        input_path = baked
        cur = input_path
        if do_color:
            cc = os.path.join(td, "cc.png")
            color_correct(Image.open(input_path), wb=wb).save(cc)
            cur = cc

        if do_deskew or perspective_correct or crop_to_face:
            # flat-goods: deskew + perspective-correct + full-bleed face crop.
            # No cutout (transparent bg N/A) and no square pad — the item's own
            # edges are the frame. Low-confidence/non-rectangular -> manual.
            final_img, mask_quality = _deskew_flat_goods(cur, input_path, size)
            if final_img is None:
                return None, mask_quality
        else:
            if do_bg:
                transp = os.path.join(td, "transp.png")
                mask_quality = remove_background(cur, transp, model=model, allow_rect_mask=allow_rect_mask)
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

    profiles_json = load_photo_profiles()

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
        
        label_data = load_item_metadata(item_dir)
        overrides = label_data.get("photo_overrides", {})
        notes = overrides.pop("notes", "")  # documentation-only; not passed to pipeline
        
        profile = resolve_profile(label_data, profiles_json)
        profile_config = profiles_json.get("profiles", {}).get(profile, {})
        profile_flags = profile_config.get("flags", {})
        
        changed = apply_overrides(item_args, profile_flags, overrides, parser) if (overrides or profile_flags) else []
        if changed and args.verbose:
            print(f"  [{item_dir.name}] overrides (profile: {profile}): {', '.join(changed)}", file=sys.stderr)

        # Skip logic if manual
        if profile_config.get("ship") is False:
            print(f"  \u26a0 {item_dir.name}  -> skipped (profile: {profile})")
            update_label_json_status(item_dir, "needs_manual")
            results.append({"item": item_dir.name, "status": "skipped", "reason": f"profile_{profile}"})
            continue

        # Default the embedded SKU to the item directory name (e.g. "RG-0001")
        effective_sku = item_args.sku or item_dir.name

        try:
            out_path, mask_quality = standardize(
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
                do_deskew=getattr(item_args, "deskew", False),
                perspective_correct=getattr(item_args, "perspective_correct", False),
                crop_to_face=getattr(item_args, "crop_to_face", False),
                do_card=getattr(item_args, "do_card", True),
            )

            # flat-goods deskew routed to manual (low confidence / non-rectangular / no cv2)
            if out_path is None and mask_quality and mask_quality.get("deskew_needs_manual"):
                reason = mask_quality.get("reason", "deskew_needs_manual")
                print(f"  ⚠ {item_dir.name}  -> deskew needs manual ({reason}); sent to manual queue", file=sys.stderr)
                update_label_json_status(item_dir, "needs_manual")
                queue_path = os.path.expanduser("~/workspace/richmondgeneral/" + profiles_json.get("manual_queue", {}).get("report_path", "ops/reports/photo-manual-queue.jsonl"))
                os.makedirs(os.path.dirname(queue_path), exist_ok=True)
                with open(queue_path, "a", encoding="utf-8") as f:
                    ts = datetime.datetime.utcnow().isoformat() + "Z"
                    f.write(json.dumps({"sku": effective_sku, "reason": f"deskew_{reason}", "src": str(hero), "ts": ts}) + "\n")
                results.append({"item": item_dir.name, "status": "needs_manual", "reason": f"deskew_{reason}"})
                continue

            # Mask Gate Check
            tripped_gate = None
            if mask_quality:
                tripped_gate = evaluate_mask_gate(mask_quality, profile, profiles_json)

            if tripped_gate:
                print(f"  \u26a0 {item_dir.name}  -> gate tripped ({tripped_gate}); sent to manual queue", file=sys.stderr)
                update_label_json_status(item_dir, "needs_manual")
                
                # Append to queue
                queue_path = os.path.expanduser("~/workspace/richmondgeneral/" + profiles_json.get("manual_queue", {}).get("report_path", "ops/reports/photo-manual-queue.jsonl"))
                os.makedirs(os.path.dirname(queue_path), exist_ok=True)
                with open(queue_path, "a", encoding="utf-8") as f:
                    ts = datetime.datetime.utcnow().isoformat() + "Z"
                    f.write(json.dumps({"sku": effective_sku, "reason": f"gate_{tripped_gate}", "src": str(hero), "ts": ts}) + "\n")
                    
                results.append({"item": item_dir.name, "status": "needs_manual", "reason": f"gate_{tripped_gate}", "output": str(output)})
                continue

            entry: Dict[str, Any] = {"item": item_dir.name, "status": "ok",
                                     "output": str(output)}
            if notes:
                entry["notes"] = notes
            if changed:
                entry["overrides"] = changed
            results.append(entry)
            if getattr(item_args, "do_card", True) and (item_dir / "card.png").exists():
                sys.path.insert(0, SCRIPT_DIR)
                from golden_card import record_photos_card
                record_photos_card(item_dir)
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

    # ---- golden-ratio card image (card.png) ----
    card_grp = p.add_mutually_exclusive_group()
    card_grp.add_argument("--card", dest="do_card", action="store_true", default=True,
                          help="also emit a golden-ratio transparent card.png (default on)")
    card_grp.add_argument("--no-card", dest="do_card", action="store_false",
                          help="do not emit card.png")

    # ---- flat-goods deskew (books/paper/cards/boxed/framed) ----
    p.add_argument("--deskew", action="store_true",
                   help="detect the flat item's rectangular face and perspective-"
                        "correct it to straight-on (the flat-goods path; no cutout)")
    p.add_argument("--perspective-correct", dest="perspective_correct",
                   action="store_true",
                   help="alias/companion to --deskew (kept for flag symmetry)")
    p.add_argument("--crop-to-face", dest="crop_to_face", action="store_true",
                   help="with --deskew, output the tight full-bleed face crop")

    # ---- misc ----
    p.add_argument("--straighten", action="store_true",
                   help="deprecated alias for --deskew (now implemented via opencv)")
    p.add_argument("-v", "--verbose", action="store_true")
    return p


def main() -> None:
    p = _build_parser()
    args = p.parse_args()

    if args.straighten:
        # --straighten is now a deprecated alias for --deskew (opencv implemented).
        args.deskew = True

    # ---- batch mode ----
    if args.batch_items_dir:
        _run_batch(args, p)
        return  # _run_batch calls sys.exit internally

    # ---- single-image mode ----
    if not args.input:
        p.error("input is required (or use --batch-items-dir for batch mode)")
    if not args.output:
        p.error("-o/--output is required in single-image mode")

    # Auto-load label.json from the input's parent directory.
    # JSON values only fill in what the CLI left at its default; explicit
    # flags always win.  Log applied overrides so the caller can audit them.
    label_data = load_item_metadata(Path(args.input).parent)
    overrides = label_data.get("photo_overrides", {})
    overrides.pop("notes", None)  # documentation-only key
    
    profiles_json = load_photo_profiles()
    profile = resolve_profile(label_data, profiles_json)
    profile_flags = profiles_json.get("profiles", {}).get(profile, {}).get("flags", {})
    
    if overrides or profile_flags:
        changed = apply_overrides(args, profile_flags, overrides, p)
        if changed:
            print(
                f"info: applied overrides (profile: {profile}): {', '.join(changed)}",
                file=sys.stderr,
            )

    out, mq = standardize(
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
        do_deskew=args.deskew,
        perspective_correct=args.perspective_correct,
        crop_to_face=args.crop_to_face,
        do_card=args.do_card,
    )
    if out is None:
        reason = (mq or {}).get("reason", "needs_manual")
        print(f"needs_manual: {reason}", file=sys.stderr)
        sys.exit(2)
    print(out)


if __name__ == "__main__":
    main()
