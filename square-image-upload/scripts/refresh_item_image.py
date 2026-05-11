#!/usr/bin/env python3
"""
End-to-end Square item-image refresh.

Workflow:
  1. Resolve a Square catalog item by ID or title fragment
  2. For each target image (primary by default, all with --all-images):
       a. Auto-pick source: items/RG-XXXX/original.png if larger than Square's
          copy and the image is the primary, else Square's stored copy
       b. Download to local backup
       c. Run clean.py
       d. Upload result back to Square (in-place PUT)
  3. With --both: produce preserved AND fixed variants. The "chosen" variant
     (default: preserved; --prefer fixed to invert; --prefer ask to prompt)
     replaces the Square primary in place. The other variant is saved as
     a museum-style before/after companion in items/RG-XXXX/:
       - chosen=preserved → companion saved as items/RG-XXXX/restored.jpg
       - chosen=fixed     → companion saved as items/RG-XXXX/as-found.jpg

     Richmond General is more museum than storefront — the GitHub Pages
     item card can show both variants for transparent provenance, while
     Square shows only the chosen one.

Examples:
  refresh_item_image.py --item-id TJSHQTHOKYUDORWURROAQCNZ
  refresh_item_image.py --title "Lionel Pennsylvania GG-1" --inspect
  refresh_item_image.py --item-id <ID> --both                  # preserved→Square, fixed→items/restored.jpg
  refresh_item_image.py --item-id <ID> --both --prefer ask     # interactive choice
  refresh_item_image.py --item-id <ID> --all-images
  refresh_item_image.py --item-id <ID> --fix-damage --remove "the dust"

Damage is preserved by default. --fix-damage restores; --both produces
both versions. --both and --all-images are mutually exclusive.

Requires: SQUARE_ACCESS_TOKEN, GEMINI_API_KEY (Keychain or project .env).
"""
import argparse
import concurrent.futures
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Optional, List

try:
    import requests
except ImportError:
    print("Error: requests required (`pip install requests`)", file=sys.stderr)
    sys.exit(1)

SQUARE_API_BASE = "https://connect.squareup.com"
DEFAULT_API_VERSION = "2026-04-21"

# Rough per-call costs for Gemini image-edit (Nov 2025 published rates).
# Used by the --max-cost pre-flight estimator; an estimate, not a billing source.
COST_PER_CALL_FLASH = 0.57
COST_PER_CALL_PRO = 2.13

THIS = Path(__file__).resolve()
PROJECT_ROOT = THIS.parents[3]
CLEAN_PY = PROJECT_ROOT / "skills" / "image-processor" / "scripts" / "clean.py"
ITEMS_DIR = PROJECT_ROOT / "items"


# ──────────────────────────────────────────────────────────────────
# Secret resolution
# ──────────────────────────────────────────────────────────────────

def resolve_secret(*service_names: str) -> Optional[str]:
    for name in service_names:
        if os.environ.get(name):
            return os.environ[name]
    for name in service_names:
        try:
            r = subprocess.run(
                ["security", "find-generic-password",
                 "-a", os.environ.get("USER", ""), "-s", name, "-w"],
                capture_output=True, text=True, timeout=5,
            )
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip()
        except (FileNotFoundError, subprocess.SubprocessError):
            continue
    env_file = PROJECT_ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            for name in service_names:
                if line.startswith(f"{name}="):
                    val = parse_env_value(line.split("=", 1)[1])
                    if val:
                        return val
    return None


def parse_env_value(raw: str) -> str:
    """Strip whitespace, matching outer quotes, and unquoted inline `#`
    comments from a .env value. Quoted values are taken verbatim — a `#`
    inside `"..."` or `'...'` is part of the token, not a comment marker.
    Without this, a perfectly normal `KEY=token # prod` produces a malformed
    `token # prod` and fails auth silently.
    """
    val = raw.strip()
    if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
        return val[1:-1]
    # Unquoted: everything from the first `#` onward is a comment.
    if "#" in val:
        val = val.split("#", 1)[0].strip()
    return val


def get_token() -> str:
    t = resolve_secret("SQUARE_ACCESS_TOKEN", "SQUARE_TOKEN")
    if not t:
        sys.exit("Error: no SQUARE_ACCESS_TOKEN found in env, Keychain, or .env")
    return t


def ensure_gemini_key() -> None:
    if os.environ.get("GEMINI_API_KEY"):
        return
    k = resolve_secret("GEMINI_API_KEY", "NANO_BANANA_API_KEY")
    if k:
        os.environ["GEMINI_API_KEY"] = k
        os.environ.setdefault("NANO_BANANA_API_KEY", k)
    else:
        print("Warning: no GEMINI_API_KEY found — clean.py will fail.",
              file=sys.stderr)


# ──────────────────────────────────────────────────────────────────
# Square Catalog API helpers
# ──────────────────────────────────────────────────────────────────

def sq_headers(token: str, api_version: str, content_json: bool = True) -> dict:
    h = {
        "Square-Version": api_version,
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    if content_json:
        h["Content-Type"] = "application/json"
    return h


def resolve_item(token: str, api_version: str, item_id: Optional[str],
                 title: Optional[str]) -> dict:
    if item_id:
        url = f"{SQUARE_API_BASE}/v2/catalog/object/{item_id}"
        r = requests.get(url, headers=sq_headers(token, api_version), timeout=15)
        r.raise_for_status()
        obj = r.json().get("object", {})
        if obj.get("type") != "ITEM":
            raise ValueError(f"Object {item_id} is type {obj.get('type')}, not ITEM")
        return obj
    # limit=50 surfaces more collisions than the older default of 5 — a quiet
    # wrong-target update is the worst category of bug here. Better to error
    # with a long list than auto-pick one.
    url = f"{SQUARE_API_BASE}/v2/catalog/search-catalog-items"
    r = requests.post(url, headers=sq_headers(token, api_version),
                      json={"text_filter": title, "limit": 50}, timeout=20)
    r.raise_for_status()
    items = r.json().get("items", [])
    if not items:
        raise ValueError(f"No catalog items match title fragment: {title!r}")
    if len(items) > 1:
        names = "\n  ".join(f"{i['id']}  {i['item_data'].get('name', '?')}"
                            for i in items)
        raise ValueError(
            f"Title {title!r} matches {len(items)} items; pass --item-id "
            f"to disambiguate:\n  {names}"
        )
    return items[0]


def get_image_object(token: str, api_version: str, image_id: str) -> dict:
    url = f"{SQUARE_API_BASE}/v2/catalog/object/{image_id}"
    r = requests.get(url, headers=sq_headers(token, api_version), timeout=15)
    r.raise_for_status()
    return r.json().get("object", {})


def update_catalog_image_inplace(token: str, api_version: str, image_id: str,
                                 new_path: Path, name: Optional[str],
                                 caption: Optional[str]) -> dict:
    url = f"{SQUARE_API_BASE}/v2/catalog/images/{image_id}"
    headers = sq_headers(token, api_version, content_json=False)
    image_data = {}
    if name:
        image_data["name"] = name
    if caption:
        image_data["caption"] = caption
    body = {
        "idempotency_key": str(uuid.uuid4()),
        "image": {"type": "IMAGE", "image_data": image_data},
    }
    mime = detect_mime(new_path)
    with open(new_path, "rb") as f:
        files = {
            "file": (new_path.name, f, mime),
            "request": (None, json.dumps(body), "application/json"),
        }
        r = requests.put(url, headers=headers, files=files, timeout=120)
    r.raise_for_status()
    return r.json()


def create_catalog_image_attached(token: str, api_version: str, item_id: str,
                                  new_path: Path, name: Optional[str],
                                  caption: Optional[str],
                                  is_primary: bool) -> dict:
    url = f"{SQUARE_API_BASE}/v2/catalog/images"
    headers = sq_headers(token, api_version, content_json=False)
    image_data = {}
    if name:
        image_data["name"] = name
    if caption:
        image_data["caption"] = caption
    body = {
        "idempotency_key": str(uuid.uuid4()),
        "object_id": item_id,
        "is_primary": is_primary,
        "image": {"id": "#TEMP_ID", "type": "IMAGE", "image_data": image_data},
    }
    mime = detect_mime(new_path)
    with open(new_path, "rb") as f:
        files = {
            "file": (new_path.name, f, mime),
            "request": (None, json.dumps(body), "application/json"),
        }
        r = requests.post(url, headers=headers, files=files, timeout=120)
    r.raise_for_status()
    return r.json()


# ──────────────────────────────────────────────────────────────────
# Local helpers
# ──────────────────────────────────────────────────────────────────

def detect_mime(path: Path) -> str:
    """Use real bytes via `file`, fall back to extension."""
    try:
        r = subprocess.run(["file", "-b", "--mime-type", str(path)],
                           capture_output=True, text=True, timeout=5)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except (FileNotFoundError, subprocess.SubprocessError):
        pass
    ext = path.suffix.lower()
    return {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
            ".webp": "image/webp"}.get(ext, "application/octet-stream")


def parse_dimensions(text: str) -> Optional[str]:
    """Pick the largest 'WxH' substring from `file` output.

    `file` reports several NxM-shaped fields for JFIF JPEGs: the density
    ('density 1x1') comes BEFORE the real pixel dimensions ('1500x2000'),
    so a naive first-match regex returns '1x1'. We collect every match and
    pick the largest by area, which reliably skips density and any thumbnail
    fields that may appear."""
    if not text:
        return None
    matches = re.findall(r"(\d+)\s*x\s*(\d+)", text)
    if not matches:
        return None
    w, h = max(((int(a), int(b)) for a, b in matches), key=lambda wh: wh[0] * wh[1])
    return f"{w}x{h}"


def image_dimensions(path: Path) -> Optional[str]:
    """Return '<W>x<H>' string via `file`, or None."""
    try:
        r = subprocess.run(["file", str(path)], capture_output=True, text=True, timeout=5)
        return parse_dimensions(r.stdout)
    except (FileNotFoundError, subprocess.SubprocessError):
        return None


def guess_ext(content_type: str, url: str) -> str:
    ct = (content_type or "").lower()
    if "png" in ct: return ".png"
    if "jpeg" in ct or "jpg" in ct: return ".jpg"
    if "webp" in ct: return ".webp"
    if "gif" in ct: return ".gif"
    m = re.search(r"\.(png|jpe?g|webp|gif)(?:\?|$)", url, re.IGNORECASE)
    return f".{m.group(1).lower()}" if m else ".jpg"


def download_image(url: str, dest: Path) -> None:
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=64 * 1024):
                f.write(chunk)


def pixels(dim: Optional[str]) -> int:
    if not dim:
        return 0
    try:
        w, h = dim.split("x")
        return int(w) * int(h)
    except (ValueError, AttributeError):
        return 0


def find_local_hires(sku: str) -> Optional[Path]:
    """Return path to items/RG-XXXX/original.png if it exists."""
    if not sku:
        return None
    candidate = ITEMS_DIR / sku / "original.png"
    return candidate if candidate.exists() else None


def save_to_items_folder(sku: Optional[str], src: Path, filename: str) -> Optional[Path]:
    """Copy src into items/RG-XXXX/<filename> if the item folder exists.
    Returns the destination path, or None if the folder doesn't exist."""
    if not sku:
        return None
    item_dir = ITEMS_DIR / sku
    if not item_dir.is_dir():
        return None
    dest = item_dir / filename
    shutil.copy2(src, dest)
    return dest


def ask_variant_choice() -> str:
    """Interactive prompt — returns 'preserved' or 'fixed'.

    Errors out (rather than hanging on input()) if stdin isn't a TTY. This
    matters for launchd, cron, and any context where the script is piped to
    or run non-interactively — without the guard, a `--prefer ask` invocation
    would block forever waiting for keyboard input that will never come.
    """
    if not sys.stdin.isatty():
        sys.exit(
            "Error: --prefer ask requires an interactive terminal "
            "(stdin is not a TTY). Use --prefer preserved or --prefer fixed "
            "explicitly when running non-interactively (launchd/cron/pipes)."
        )
    print("\nWhich variant should be the Square primary?")
    print("  preserved — shows damage (honest condition; recommended for books, antiques)")
    print("  fixed     — damage repaired (better for items where condition is incidental)")
    while True:
        ans = input("Choose [preserved/fixed, default=preserved]: ").strip().lower()
        if not ans or ans.startswith("p"):
            return "preserved"
        if ans.startswith("f"):
            return "fixed"
        print("  try 'preserved' or 'fixed'.")


# ──────────────────────────────────────────────────────────────────
# Cleanup driver
# ──────────────────────────────────────────────────────────────────

def run_clean(input_path: Path, output_path: Path,
              fix_damage: bool, both: bool, pro: bool,
              extra: Optional[str], verbose: bool) -> dict:
    cmd = [str(CLEAN_PY), "-i", str(input_path), "-o", str(output_path), "--json"]
    if fix_damage:
        cmd.append("--fix-damage")
    if both:
        cmd.append("--both")
    if pro:
        cmd.append("--pro")
    if extra:
        cmd += ["--remove", extra]
    if verbose:
        cmd.append("--verbose")
        print(f"  $ {' '.join(cmd)}", file=sys.stderr)
    r = subprocess.run(cmd, capture_output=True, text=True)
    if verbose and r.stderr:
        sys.stderr.write(r.stderr)
    if r.returncode != 0:
        msg = f"clean.py failed (exit {r.returncode})\n"
        if r.stdout.strip():
            msg += f"stdout:\n{r.stdout}\n"
        if r.stderr.strip() and not verbose:
            msg += f"stderr:\n{r.stderr}"
        raise RuntimeError(msg)
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        raise RuntimeError(f"clean.py produced non-JSON:\n{r.stdout}")


# ──────────────────────────────────────────────────────────────────
# Mode: --inspect
# ──────────────────────────────────────────────────────────────────

def cmd_inspect(token: str, api_version: str, item: dict) -> None:
    item_data = item["item_data"]
    sku = (item_data.get("variations") or [{}])[0].get("item_variation_data", {}).get("sku")
    print(f"\nItem    : {item['id']}")
    print(f"Name    : {item_data.get('name', '?')}")
    print(f"SKU     : {sku or '—'}")
    print(f"Created : {item.get('created_at', '?')}")
    print(f"Updated : {item.get('updated_at', '?')}")
    image_ids = item_data.get("image_ids", [])
    print(f"\nImages attached: {len(image_ids)}")
    for idx, img_id in enumerate(image_ids):
        try:
            img = get_image_object(token, api_version, img_id)
            d = img.get("image_data", {})
            url = d.get("url", "")
            head = requests.head(url, allow_redirects=True, timeout=15) if url else None
            size = head.headers.get("content-length") if head is not None else None
            ctype = head.headers.get("content-type") if head is not None else None
            tag = "primary" if idx == 0 else f"#{idx+1}"
            print(f"  [{tag}] {img_id}")
            print(f"        name    : {d.get('name') or '—'}")
            print(f"        caption : {d.get('caption') or '—'}")
            print(f"        URL     : {url}")
            print(f"        type    : {ctype or '?'}     size: "
                  f"{f'{int(size):,} bytes' if size else '?'}")
        except Exception as e:
            print(f"  [#{idx+1}] {img_id}   inspection failed: {e}")
    if sku:
        local = find_local_hires(sku)
        if local:
            dim = image_dimensions(local)
            print(f"\nLocal hi-res source available:")
            print(f"  {local}  ({dim or '?'}, {local.stat().st_size:,} bytes)")
        else:
            print(f"\nLocal hi-res source: none at items/{sku}/original.png")


# ──────────────────────────────────────────────────────────────────
# Mode: refresh primary (default or with --fix-damage / --both)
# ──────────────────────────────────────────────────────────────────

def fetch_source(token: str, api_version: str, image_id: str,
                 sku: Optional[str], allow_local: bool, tmpdir: Path,
                 verbose: bool):
    """Return (local_source_path, source_label, original_image_metadata_dict)."""
    img = get_image_object(token, api_version, image_id)
    img_data = img.get("image_data", {})
    img_url = img_data.get("url")
    if not img_url:
        raise RuntimeError(f"image {image_id} has no URL")

    head = requests.head(img_url, allow_redirects=True, timeout=15)
    ext = guess_ext(head.headers.get("content-type", ""), img_url)
    # Disambiguate by image_id so parallel workers under --all-images don't
    # collide on a single shared SKU-based path. Same item, multiple images,
    # three workers writing to /tmp/RG-0042-from-square.jpg would race.
    sq_path = tmpdir / f"{sku or 'item'}-{image_id}-from-square{ext}"
    download_image(img_url, sq_path)
    sq_dim = image_dimensions(sq_path)

    local_path = find_local_hires(sku) if (allow_local and sku) else None
    if local_path:
        local_dim = image_dimensions(local_path)
        if pixels(local_dim) > pixels(sq_dim):
            if verbose:
                print(f"  source: local {local_dim} (preferred over Square {sq_dim})",
                      file=sys.stderr)
            return local_path, f"local hi-res ({local_dim})", img_data
        if verbose:
            print(f"  source: Square {sq_dim} (local {local_dim} not larger)",
                  file=sys.stderr)
    elif verbose:
        print(f"  source: Square {sq_dim} (no local hi-res available)",
              file=sys.stderr)
    return sq_path, f"Square ({sq_dim})", img_data


_PRESERVE_SOURCE_EXTS = (".jpg", ".jpeg", ".png", ".webp")


def cleaned_output_path(tmpdir: Path, sku: Optional[str], image_id: str,
                        source_path: Path) -> Path:
    """Build the temp output path for clean.py, preserving the source format.

    clean.py infers output format from the file extension we hand it, so
    hardcoding `.jpg` here silently re-encodes PNG/WebP sources as lossy JPEG.
    Pick the source's extension when it's something Square accepts and clean.py
    handles; fall back to `.jpg` for anything unfamiliar.
    """
    src_ext = source_path.suffix.lower()
    if src_ext not in _PRESERVE_SOURCE_EXTS:
        src_ext = ".jpg"
    return tmpdir / f"{sku or 'item'}-{image_id}-cleaned{src_ext}"


def refresh_one_image(token: str, api_version: str, item_id: str, image_id: str,
                      sku: Optional[str], args, tmpdir: Path) -> dict:
    """Clean + upload (in-place) for one image_id. Returns summary dict."""
    print(f"\n→ Image {image_id}  (sku={sku or '—'})")
    source_path, source_label, img_meta = fetch_source(
        token, api_version, image_id, sku, allow_local=True, tmpdir=tmpdir,
        verbose=args.verbose)
    print(f"  source : {source_label}")
    print(f"  backup : {source_path}")

    # Image-id-scoped name prevents parallel-worker collisions; see fetch_source.
    out_base = cleaned_output_path(tmpdir, sku, image_id, source_path)
    t0 = time.time()
    result = run_clean(source_path, out_base,
                       fix_damage=args.fix_damage, both=args.both, pro=args.pro,
                       extra=args.remove, verbose=args.verbose)
    if not result.get("success"):
        raise RuntimeError(f"clean.py failed: {json.dumps(result, indent=2)}")
    elapsed = time.time() - t0
    print(f"  cleaned in {elapsed:.1f}s  model={result['results'][0]['model']}")

    img_meta_name = img_meta.get("name")
    img_meta_caption = img_meta.get("caption")

    summary = {
        "image_id": image_id,
        "source": source_label,
        "elapsed_s": round(elapsed, 1),
        "cleaned_paths": [r["output_path"] for r in result["results"]],
    }

    if args.both:
        preserved_path = Path(result["results"][0]["output_path"])
        fixed_path = Path(result["results"][1]["output_path"])

        # Museum model (Richmond General is more museum than storefront):
        # Square primary = the one the customer should see at checkout. Default
        # is preserved-damage (honest condition for picky collectors). Books
        # especially: never hide damage from the buyer.
        # The not-chosen variant gets saved to items/RG-XXXX/ as the
        # before/after companion for the GitHub Pages museum view.
        choice = args.prefer
        if choice == "ask":
            choice = ask_variant_choice()
        if choice == "preserved":
            square_path, items_path, items_name = (
                preserved_path, fixed_path, "restored.jpg")
            square_label, items_label = "preserved-damage", "fixed-damage"
        else:  # "fixed"
            square_path, items_path, items_name = (
                fixed_path, preserved_path, "as-found.jpg")
            square_label, items_label = "fixed-damage", "preserved-damage"

        print(f"  PUT  {square_label} → Square image {image_id} (in-place primary)")
        update_catalog_image_inplace(token, api_version, image_id, square_path,
                                     img_meta_name, img_meta_caption)

        items_dest = save_to_items_folder(sku, items_path, items_name)
        if items_dest:
            print(f"  COPY {items_label} → {items_dest}  (museum companion)")
            summary["items_companion"] = str(items_dest)
        else:
            print(f"  ! items/{sku}/ not found — companion left at {items_path}")
            summary["items_companion"] = str(items_path)
        summary["square_variant"] = square_label
    else:
        only_path = Path(result["results"][0]["output_path"])
        label = "fix-damage" if args.fix_damage else "preserve-damage"
        print(f"  PUT  {label} → image {image_id} (in-place replace)")
        update_catalog_image_inplace(token, api_version, image_id, only_path,
                                     img_meta_name, img_meta_caption)

    return summary


# ──────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Square item-image refresh (clean + upload).",
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
    parser.add_argument("--fix-damage", action="store_true",
                        help="Repair visible damage (default: preserve it)")
    parser.add_argument("--both", action="store_true",
                        help="Produce both preserved and fixed versions (mutex with --all-images). "
                             "Chosen variant → Square primary; companion → items/RG-XXXX/")
    parser.add_argument("--prefer", choices=["preserved", "fixed", "ask"],
                        default="preserved",
                        help="With --both: which variant goes to Square as primary "
                             "(default: preserved; 'ask' prompts interactively)")
    parser.add_argument("--pro", action="store_true",
                        help="Use gemini-3-pro-image-preview (~$2.13/call vs ~$0.57)")
    parser.add_argument("--remove", help="Freeform additional direction for the prompt")
    parser.add_argument("--max-cost", type=float, default=None, metavar="USD",
                        help="Abort if the estimated Gemini cost for this run exceeds USD. "
                             "Estimate = (Flash $0.57 or Pro $2.13) × image_count × (2 if --both else 1). "
                             "No default — set this when running ad-hoc batches.")
    parser.add_argument("--inspect", action="store_true",
                        help="Report item + image state without modifying anything")
    parser.add_argument("--api-version", default=DEFAULT_API_VERSION)
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    if args.both and args.all_images:
        parser.error("--both and --all-images are mutually exclusive "
                     "(would multiply image count and cost). Run twice if you "
                     "really need both versions for every image.")
    if args.both and args.fix_damage:
        parser.error("--both already produces both versions; drop --fix-damage")

    token = get_token()
    if not args.inspect:
        ensure_gemini_key()

    print(f"→ Resolving item ({'id' if args.item_id else 'title'})...")
    item = resolve_item(token, args.api_version, args.item_id, args.title)

    if args.inspect:
        cmd_inspect(token, args.api_version, item)
        return

    item_id = item["id"]
    image_ids = item["item_data"].get("image_ids", [])
    if not image_ids:
        sys.exit(f"Error: item {item_id} has no attached images")
    sku = (item["item_data"].get("variations") or [{}])[0]\
        .get("item_variation_data", {}).get("sku")
    name = item["item_data"].get("name", "?")
    print(f"  Item: {item_id}  ({name})")
    print(f"  SKU : {sku or '—'}")
    targets = image_ids if args.all_images else [image_ids[0]]
    print(f"  Targets: {len(targets)} image(s) {'(all)' if args.all_images else '(primary only)'}")

    # Pre-flight cost estimate. Lets ad-hoc batch loops (e.g. `for id in ...;
    # do refresh_item_image.py --item-id $id; done`) catch a runaway before
    # racking up a four-figure Gemini bill. Per-item only — full batch
    # protection would need a shared counter across invocations.
    per_call = COST_PER_CALL_PRO if args.pro else COST_PER_CALL_FLASH
    calls = len(targets) * (2 if args.both else 1)
    estimated = per_call * calls
    print(f"  Cost  : ~${estimated:.2f}  ({calls} call(s) × ${per_call:.2f}, "
          f"{'pro' if args.pro else 'flash'})")
    if args.max_cost is not None and estimated > args.max_cost:
        sys.exit(
            f"Error: estimated cost ${estimated:.2f} exceeds --max-cost "
            f"${args.max_cost:.2f}. Use --max-cost to raise the ceiling, "
            f"or process fewer images."
        )

    tmpdir = Path(tempfile.gettempdir())
    summaries: List[dict] = []
    failures: List[dict] = []

    if args.all_images and len(targets) > 1:
        workers = min(max(1, args.concurrency), 8, len(targets))
        print_lock = threading.Lock()
        total = len(targets)
        done_count = 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_id = {
                executor.submit(refresh_one_image, token, args.api_version,
                                item_id, img_id, sku, args, tmpdir): img_id
                for img_id in targets
            }
            for future in concurrent.futures.as_completed(future_to_id):
                img_id = future_to_id[future]
                try:
                    s = future.result()
                    summaries.append(s)
                    with print_lock:
                        done_count += 1
                        print(f"[{done_count}/{total}] image {img_id} done in "
                              f"{s['elapsed_s']}s  (source={s['source']})")
                except Exception as e:
                    failures.append({"image_id": img_id, "error": str(e)})
                    with print_lock:
                        done_count += 1
                        print(f"[{done_count}/{total}] image {img_id} FAILED: {e}",
                              file=sys.stderr)
    else:
        for img_id in targets:
            s = refresh_one_image(token, args.api_version, item_id, img_id,
                                  sku, args, tmpdir)
            summaries.append(s)

    print("\nDone.")
    for s in summaries:
        print(f"  • {s['image_id']}  {s['elapsed_s']}s  source={s['source']}")
        for p in s["cleaned_paths"]:
            print(f"      cleaned: {p}")
        if "fixed_image_id" in s:
            print(f"      fixed variant attached as: {s['fixed_image_id']}")

    if failures:
        print(f"\n{len(failures)} image(s) FAILED:", file=sys.stderr)
        for f in failures:
            print(f"  ✗ {f['image_id']}: {f['error']}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
