#!/usr/bin/env python3
"""
Auto-detect and correct rotation on Square catalog item images.

Workflow per image:
  1. Download the current Square copy
  2. Ask Gemini 2.5 Flash which CW rotation (0/90/180/270) makes it right-side up
  3. If non-zero: rotate locally with PIL, PUT back to Square in place

This is meant to be run BEFORE refresh_item_image.py — fix orientation first,
then run the expensive cleanup on the corrected image.

Detection is ~$0.001/image (Flash, text-only output). Rotation itself is free
(local PIL). The only Square side effect is the in-place PUT, which preserves
the image's name, caption, and attachment to the item.

Examples:
  rotate_item_images.py --item-id <ID> --all-images --inspect    # detect only
  rotate_item_images.py --item-id <ID> --all-images              # detect + rotate
  rotate_item_images.py --title "Foo" --all-images --concurrency 4

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
    from PIL import Image
except ImportError:
    print("Error: Pillow required (`pip install Pillow`)", file=sys.stderr)
    sys.exit(1)

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

ROTATION_PROMPT = """Determine the clockwise rotation needed to make this image display right-side up.

Use these cues:
- Text should read left-to-right, top-to-bottom
- For photos of physical objects: gravity points down
- For illustrations: subject should be oriented as intended for viewing

Return JSON exactly in this format:
{"rotation_cw_degrees": N, "confidence": F, "reasoning": "brief explanation"}

Where:
- N is one of: 0, 90, 180, 270 (clockwise degrees to APPLY to correct the image)
- F is a confidence score 0.0–1.0
- 0 means the image is already correctly oriented
"""


def detect_rotation_via_gemini(image_path: Path, api_key: str,
                               timeout: int = 30) -> dict:
    """Ask Gemini what CW rotation corrects the image. Returns parsed JSON."""
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")

    mime = "image/jpeg"
    suffix = image_path.suffix.lower()
    if suffix == ".png":
        mime = "image/png"
    elif suffix == ".webp":
        mime = "image/webp"

    payload = {
        "contents": [{
            "parts": [
                {"text": ROTATION_PROMPT},
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

    deg = parsed.get("rotation_cw_degrees")
    if deg not in (0, 90, 180, 270):
        raise RuntimeError(f"Gemini returned invalid rotation: {deg!r}")
    return parsed


def rotate_to_correct(src: Path, dst: Path, cw_degrees: int) -> None:
    """Rotate src clockwise by cw_degrees (must be 0/90/180/270) → dst.
    Uses PIL.Image.rotate with a negative angle (PIL is CCW-positive)."""
    if cw_degrees == 0:
        if src != dst:
            dst.write_bytes(src.read_bytes())
        return
    if cw_degrees not in (90, 180, 270):
        raise ValueError(f"cw_degrees must be one of 0/90/180/270, got {cw_degrees}")

    img = Image.open(src)
    # Preserve any EXIF (in case Square or downstream tools look at it).
    exif = img.info.get("exif")
    rotated = img.rotate(-cw_degrees, expand=True)
    save_kwargs = {}
    if exif:
        save_kwargs["exif"] = exif

    out_fmt = (img.format or "JPEG").upper()
    # JPEG can't carry alpha; coerce if PIL gave us RGBA.
    if out_fmt in ("JPEG", "JPG") and rotated.mode in ("RGBA", "P"):
        rotated = rotated.convert("RGB")

    rotated.save(dst, format=out_fmt, **save_kwargs)


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

    if args.inspect or cw == 0:
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
                        verb = "applied" if s["applied"] else (
                            "would rotate" if (s["rotation_cw"] and args.inspect)
                            else "no rotation needed")
                        print(f"[{done}/{total}] {img_id}: "
                              f"cw={s['rotation_cw']}° conf={s['confidence']:.2f} "
                              f"({verb})  detect={s['detect_s']}s")
                        if args.verbose and s["reasoning"]:
                            print(f"        reason: {s['reasoning']}")
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
                verb = "applied" if s["applied"] else (
                    "would rotate" if (s["rotation_cw"] and args.inspect)
                    else "no rotation needed")
                print(f"  {img_id}: cw={s['rotation_cw']}° "
                      f"conf={s['confidence']:.2f} ({verb})")
                if args.verbose and s["reasoning"]:
                    print(f"      reason: {s['reasoning']}")
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
