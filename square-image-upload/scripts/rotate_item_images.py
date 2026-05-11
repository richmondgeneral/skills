#!/usr/bin/env python3
"""
Auto-detect and correct rotation on Square catalog item images.

Workflow per image:
  1. Download the current Square copy
  2. Apply any EXIF orientation tag (handles phone-camera rotation automatically)
  3. Score ALL four candidate orientations with Gemini 2.5 Flash ("is this upright?"),
     pick the highest-scoring one
  4. If the winner is non-zero AND high-confidence: rotate locally with PIL,
     PUT back to Square in place

Why score-all-four instead of one ask-the-model call: vision models reliably tell
whether a given image is upright, but are flakier at predicting which rotation
fixes it (text running sideways trips them up — they sometimes pick the wrong
direction). Scoring all four candidates trades 4x the inference cost (~$0.004/image
on Flash, still nothing) for deterministic results.

This is meant to be run BEFORE refresh_item_image.py — fix orientation first,
then run the expensive cleanup on the corrected image.

Examples:
  rotate_item_images.py --item-id <ID> --all-images --inspect    # detect only
  rotate_item_images.py --item-id <ID> --all-images              # detect + rotate
  rotate_item_images.py --title "Foo" --all-images --concurrency 4
  rotate_item_images.py --item-id <ID> --all-images --min-confidence 0.85

Requires: SQUARE_ACCESS_TOKEN, GEMINI_API_KEY.
"""
import argparse
import base64
import concurrent.futures
import json
import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Optional, List

try:
    import requests
except ImportError:
    print("Error: requests required (`pip install requests`)", file=sys.stderr)
    sys.exit(1)

try:
    from PIL import Image, ImageOps
except ImportError:
    print("Error: Pillow required (`pip install Pillow`)", file=sys.stderr)
    sys.exit(1)

import io

# Reuse all the Square/secret/CLI helpers from refresh_item_image.py.
from refresh_item_image import (
    DEFAULT_API_VERSION,
    ITEMS_DIR,
    download_image,
    ensure_gemini_key,
    get_image_object,
    get_token,
    guess_ext,
    resolve_item,
    sq_headers,
    update_catalog_image_inplace,
    SQUARE_API_BASE,
)

GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_URL = (f"https://generativelanguage.googleapis.com/v1beta/"
              f"models/{GEMINI_MODEL}:generateContent")

UPRIGHT_PROMPT = """You are inspecting an image to judge if it is displayed RIGHT-SIDE UP.

Cues for "upright":
- Any text reads left-to-right, top-to-bottom (the most reliable cue when present)
- Photographed physical objects: gravity points down — shadows fall below objects, liquids settle at the bottom
- Photographed pages of a book or label: the binding/spine of the book is the left or right edge, not the top or bottom
- Illustrations: subject is oriented as a viewer would naturally look at it

If you see any TEXT in the image, the text orientation is decisive. Ignore the
physical-object cues when text is present and legible — text orientation wins.

Return JSON exactly in this format:
{"is_upright": true|false, "confidence": F, "reasoning": "brief explanation, mention text orientation if any"}

Where F is a confidence score 0.0-1.0. Be honest about uncertainty: if you're
unsure, say so with a lower confidence — don't claim 0.9 unless you really are
that sure.
"""


def _mime_for(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".png":
        return "image/png"
    if suffix == ".webp":
        return "image/webp"
    return "image/jpeg"


def _gemini_call(image_bytes: bytes, mime: str, api_key: str,
                 timeout: int = 30) -> dict:
    """Send a single image to Gemini with the UPRIGHT_PROMPT; return parsed JSON."""
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    payload = {
        "contents": [{
            "parts": [
                {"text": UPRIGHT_PROMPT},
                {"inline_data": {"mime_type": mime, "data": b64}},
            ]
        }],
        "generationConfig": {
            "temperature": 0.0,
            "response_mime_type": "application/json",
        },
    }
    r = requests.post(f"{GEMINI_URL}?key={api_key}", json=payload,
                      timeout=timeout)
    if r.status_code != 200:
        raise RuntimeError(f"Gemini error {r.status_code}: {r.text[:300]}")
    body = r.json()
    try:
        text = body["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"unexpected Gemini response: {body}") from e
    parsed = json.loads(text)
    if "is_upright" not in parsed:
        raise RuntimeError(f"Gemini missing is_upright: {parsed}")
    return parsed


def _candidate_bytes(img: Image.Image, cw_degrees: int, fmt: str) -> bytes:
    """Render `img` rotated CW by `cw_degrees` and return encoded bytes."""
    if cw_degrees == 0:
        candidate = img
    else:
        candidate = img.rotate(-cw_degrees, expand=True)
    buf = io.BytesIO()
    save_kwargs = {}
    out_fmt = (fmt or "JPEG").upper()
    if out_fmt in ("JPEG", "JPG") and candidate.mode in ("RGBA", "P"):
        candidate = candidate.convert("RGB")
    candidate.save(buf, format=out_fmt, **save_kwargs)
    return buf.getvalue()


def detect_rotation_via_gemini(image_path: Path, api_key: str,
                               timeout: int = 30,
                               max_workers: int = 4) -> dict:
    """Score all four candidate orientations and return the best one.

    Returns dict with keys: rotation_cw_degrees, confidence, reasoning, scores
    (scores is a list of per-candidate Gemini judgements, useful for debugging).
    """
    base = Image.open(image_path)
    # Capture source format BEFORE exif_transpose — the transposed copy has
    # .format = None, so reading it later silently demotes PNG/WebP to JPEG.
    fmt = (base.format or "JPEG").upper()
    # Handle EXIF orientation tags up-front (saves a 90/180/270 ask).
    base = ImageOps.exif_transpose(base)
    mime = _mime_for(image_path)

    def score(cw: int) -> dict:
        body = _gemini_call(_candidate_bytes(base, cw, fmt), mime, api_key,
                            timeout=timeout)
        return {
            "cw_degrees": cw,
            "is_upright": bool(body.get("is_upright")),
            "confidence": float(body.get("confidence") or 0.0),
            "reasoning": body.get("reasoning", ""),
        }

    candidates = [0, 90, 180, 270]
    scores: List[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
        for s in ex.map(score, candidates):
            scores.append(s)
    # Tie-break preference: when ties happen on `confidence`, prefer NOT rotating
    # (0 degrees) over a coin-flip. Real rotations need to clearly beat "leave alone".
    scores.sort(key=lambda s: (not s["is_upright"], -s["confidence"],
                               s["cw_degrees"] != 0, s["cw_degrees"]))
    winner = scores[0]

    # If the top vote is is_upright=False (no orientation looked upright), bail
    # - that signals the image is genuinely ambiguous (e.g. textureless macro).
    if not winner["is_upright"]:
        return {
            "rotation_cw_degrees": 0,
            "confidence": 0.0,
            "reasoning": ("no orientation scored as upright; leaving alone. "
                          f"Top: cw={winner['cw_degrees']} conf={winner['confidence']:.2f}"),
            "scores": scores,
        }

    # Ambiguity penalty: when Gemini marks MORE than one orientation as "upright"
    # at high confidence, that's a model disagreement with itself. Penalize the
    # winner's confidence by 1/n_upright so the min_confidence threshold can
    # catch and skip these cases. (E.g. the model claiming both 90 and 180 are
    # upright with conf=1.0 -> effective conf = 0.5.)
    n_upright = sum(1 for s in scores if s["is_upright"])
    effective_conf = winner["confidence"] / max(n_upright, 1)

    return {
        "rotation_cw_degrees": winner["cw_degrees"],
        "confidence": effective_conf,
        "raw_confidence": winner["confidence"],
        "n_upright_candidates": n_upright,
        "reasoning": winner["reasoning"],
        "scores": scores,
    }


def rotate_to_correct(src: Path, dst: Path, cw_degrees: int) -> None:
    """Rotate src clockwise by cw_degrees (must be 0/90/180/270) - dst.
    Uses PIL.Image.rotate with a negative angle (PIL is CCW-positive).

    Applies EXIF orientation up-front via ImageOps.exif_transpose so the
    written file has no orientation tag that could re-rotate it downstream.
    """
    if cw_degrees not in (0, 90, 180, 270):
        raise ValueError(f"cw_degrees must be one of 0/90/180/270, got {cw_degrees}")

    img = Image.open(src)
    # Capture source format BEFORE exif_transpose — the transposed copy has
    # .format = None, so reading it later silently demotes PNG/WebP to JPEG.
    out_fmt = (img.format or "JPEG").upper()
    # Bake any EXIF orientation into the pixels, then strip the tag.
    img = ImageOps.exif_transpose(img)

    rotated = img if cw_degrees == 0 else img.rotate(-cw_degrees, expand=True)

    # JPEG can't carry alpha; coerce if PIL gave us RGBA.
    if out_fmt in ("JPEG", "JPG") and rotated.mode in ("RGBA", "P"):
        rotated = rotated.convert("RGB")

    # Do NOT propagate the original EXIF - we've already baked orientation into
    # the pixels; passing the old EXIF would cause double-rotation in viewers
    # that honor the tag.
    rotated.save(dst, format=out_fmt)


def _verb_for(s: dict, args) -> str:
    """Render the parenthesized status verb for a per-image summary line."""
    if s.get("applied"):
        return "applied"
    if s.get("skipped_reason"):
        return f"skipped — {s['skipped_reason']}"
    if s["rotation_cw"] and args.inspect:
        return "would rotate"
    if s["rotation_cw"]:
        return "rotation suggested but not applied"
    return "no rotation needed"


def _print_verbose(s: dict, indent: str = "    ") -> None:
    """Print the per-candidate Gemini scores plus the chosen reasoning."""
    if s.get("reasoning"):
        print(f"{indent}reason: {s['reasoning']}")
    scores = s.get("scores") or []
    if scores:
        # Original order in scores is sorted-best-first; re-sort by cw for the
        # debug view so it's easy to scan.
        by_cw = sorted(scores, key=lambda x: x["cw_degrees"])
        bits = [f"{x['cw_degrees']:>3}°: upright={x['is_upright']} "
                f"conf={x['confidence']:.2f}" for x in by_cw]
        print(f"{indent}all candidates: " + " | ".join(bits))


def backup_original(sku: Optional[str], src_path: Path, image_id: str) -> Optional[Path]:
    """Copy src_path into items/<sku>/before-rotation/<image_id>.<ext>.
    Returns the backup path, or None if no sku available."""
    if not sku:
        return None
    backup_dir = ITEMS_DIR / sku / "before-rotation"
    backup_dir.mkdir(parents=True, exist_ok=True)
    dst = backup_dir / f"{image_id}{src_path.suffix}"
    shutil.copy2(src_path, dst)
    return dst


def rotate_one_image(token: str, api_version: str, image_id: str,
                     sku: Optional[str], args, tmpdir: Path) -> dict:
    """Detect + (optionally) apply rotation for one image. Returns summary."""
    gemini_key = __import__("os").environ.get("GEMINI_API_KEY")
    if not gemini_key:
        raise RuntimeError("GEMINI_API_KEY missing (resolve via Keychain or .env)")

    img = get_image_object(token, api_version, image_id)
    img_data = img.get("image_data", {})
    img_url = img_data.get("url")
    if not img_url:
        raise RuntimeError(f"image {image_id} has no URL")

    head = requests.head(img_url, allow_redirects=True, timeout=15)
    ext = guess_ext(head.headers.get("content-type", ""), img_url)
    src_path = tmpdir / f"{image_id}-original{ext}"
    download_image(img_url, src_path)

    t0 = time.time()
    result = detect_rotation_via_gemini(src_path, gemini_key)
    detect_s = time.time() - t0

    cw = result["rotation_cw_degrees"]
    conf = float(result.get("confidence", 0.0))
    reason = result.get("reasoning", "")

    summary = {
        "image_id": image_id,
        "rotation_cw": cw,
        "confidence": conf,
        "reasoning": reason,
        "detect_s": round(detect_s, 2),
        "applied": False,
    }

    min_conf = float(getattr(args, "min_confidence", 0.75) or 0.0)
    summary["min_confidence"] = min_conf

    if args.inspect or cw == 0:
        return summary

    if conf < min_conf:
        summary["skipped_reason"] = (
            f"confidence {conf:.2f} below --min-confidence {min_conf:.2f}; "
            "re-run with --inspect --verbose to see all four candidate scores"
        )
        return summary

    backup_path = backup_original(sku, src_path, image_id)
    if backup_path:
        summary["backup"] = str(backup_path)

    rotated_path = tmpdir / f"{image_id}-rotated{ext}"
    rotate_to_correct(src_path, rotated_path, cw)
    update_catalog_image_inplace(token, api_version, image_id, rotated_path,
                                 img_data.get("name"), img_data.get("caption"))
    summary["applied"] = True
    return summary


def main():
    parser = argparse.ArgumentParser(
        description="Auto-detect and correct rotation on Square item images.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--item-id", help="Square catalog ITEM id")
    target.add_argument("--title", help="Title fragment for search (must be unique)")

    parser.add_argument("--all-images", action="store_true",
                        help="Process every attached image (default: primary only)")
    parser.add_argument("--concurrency", type=int, default=3,
                        help="Parallel workers for --all-images (default 3, capped at 8)")
    parser.add_argument("--inspect", action="store_true",
                        help="Detect rotation but don't modify Square")
    parser.add_argument("--min-confidence", type=float, default=0.75,
                        help="Skip applying rotation when winning candidate's "
                             "confidence is below this threshold (default 0.75)")
    parser.add_argument("--api-version", default=DEFAULT_API_VERSION)
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    token = get_token()
    ensure_gemini_key()

    print(f"→ Resolving item ({'id' if args.item_id else 'title'})...")
    item = resolve_item(token, args.api_version, args.item_id, args.title)
    item_id = item["id"]
    image_ids = item["item_data"].get("image_ids", [])
    if not image_ids:
        sys.exit(f"Error: item {item_id} has no attached images")
    name = item["item_data"].get("name", "?")
    sku = (item["item_data"].get("variations") or [{}])[0]\
        .get("item_variation_data", {}).get("sku")
    print(f"  Item: {item_id}  ({name})")
    print(f"  SKU : {sku or '—'}")
    targets = image_ids if args.all_images else [image_ids[0]]
    mode = "INSPECT (no writes)" if args.inspect else "DETECT + ROTATE"
    print(f"  Targets: {len(targets)} image(s) — mode: {mode}")

    tmpdir = Path(tempfile.gettempdir())
    summaries: List[dict] = []
    failures: List[dict] = []

    if args.all_images and len(targets) > 1:
        workers = min(max(1, args.concurrency), 8, len(targets))
        print_lock = threading.Lock()
        total = len(targets)
        done = 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_id = {
                executor.submit(rotate_one_image, token, args.api_version,
                                img_id, sku, args, tmpdir): img_id
                for img_id in targets
            }
            for future in concurrent.futures.as_completed(future_to_id):
                img_id = future_to_id[future]
                try:
                    s = future.result()
                    summaries.append(s)
                    with print_lock:
                        done += 1
                        verb = _verb_for(s, args)
                        print(f"[{done}/{total}] {img_id}: "
                              f"cw={s['rotation_cw']} conf={s['confidence']:.2f} "
                              f"({verb})  detect={s['detect_s']}s")
                        if args.verbose:
                            _print_verbose(s, indent="        ")
                except Exception as e:
                    failures.append({"image_id": img_id, "error": str(e)})
                    with print_lock:
                        done += 1
                        print(f"[{done}/{total}] {img_id} FAILED: {e}",
                              file=sys.stderr)
    else:
        for img_id in targets:
            try:
                s = rotate_one_image(token, args.api_version, img_id, sku,
                                     args, tmpdir)
                summaries.append(s)
                verb = _verb_for(s, args)
                print(f"  {img_id}: cw={s['rotation_cw']} "
                      f"conf={s['confidence']:.2f} ({verb})")
                if args.verbose:
                    _print_verbose(s, indent="      ")
            except Exception as e:
                failures.append({"image_id": img_id, "error": str(e)})
                print(f"  {img_id} FAILED: {e}", file=sys.stderr)

    print("\nDone.")
    n_rotated = sum(1 for s in summaries if s["applied"])
    n_zero = sum(1 for s in summaries if s["rotation_cw"] == 0)
    n_pending = sum(1 for s in summaries
                    if s["rotation_cw"] != 0 and not s["applied"])
    print(f"  Rotated: {n_rotated}  Already correct: {n_zero}  "
          f"Pending (inspect-only): {n_pending}  Failed: {len(failures)}")

    if failures:
        print("\nFailures:", file=sys.stderr)
        for f in failures:
            print(f"  ✗ {f['image_id']}: {f['error']}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
