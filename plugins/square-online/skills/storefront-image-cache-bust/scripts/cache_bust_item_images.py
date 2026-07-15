#!/usr/bin/env python3
"""
Cache-bust stale Square Online storefront images by re-uploading them
as fresh catalog image objects with new IDs.

Square Online's Weebly CDN serves product images keyed by Square's
catalog image ID. Updating an image in place (PUT /v2/catalog/images/{id})
does not invalidate that CDN cache. The only reliable bust is to mint
new image IDs and repoint the item.

Critical: this script uploads each replacement WITHOUT object_id. If
object_id is sent, Square's API may de-dup against an existing attached
image on the same item and return the existing ID (= same CDN URL =
no cache bust = if you then delete that ID you nuke your own live image).

Usage:

    python3 cache_bust_item_images.py \\
        --item-id <ITEM_ID> \\
        --stale <STALE_IMG_ID>:<local.jpeg>:<Image Name>:<Caption text> \\
        --stale <STALE_IMG_ID>:<local.jpeg>:<Image Name>:<Caption text> \\
        [--keep <UNCHANGED_IMG_ID> ...] \\
        [--delete-orphans] \\
        [--dry-run]

The --stale flag accepts a 4-part colon-separated value:
    <existing_image_id>:<path_to_local_file>:<name>:<caption>

The local file should be the CORRECT version of the image (e.g., the
already-rotated, already-cleaned bytes you want the CDN to serve).
You typically obtain it by downloading the catalog image's S3 URL
(image_data.url from batchGetobjects) — that URL is what API consumers
see, and is correct even when the storefront CDN is stale.

--keep lists image IDs already on the item that should remain at the
end of the new image_ids array (i.e., images that aren't stale and
don't need replacing). Order matters: the script writes
image_ids = [new_ids in --stale order...] + [--keep ids in order...]

--delete-orphans soft-deletes the old stale image objects after the
swap. They're already orphaned from the item at that point.

Requires: SQUARE_ACCESS_TOKEN in env or in <workspace>/.env.
Pure stdlib + requests. No Cloudinary, no Gemini, no AI.
"""
import argparse
import json
import os
import sys
import uuid
from pathlib import Path
from typing import List, Optional

try:
    import requests
except ImportError:
    print("ERROR: `requests` library required. pip install requests", file=sys.stderr)
    sys.exit(1)


SQUARE_API_BASE = "https://connect.squareup.com"
DEFAULT_API_VERSION = "2026-04-21"


# ---------------------------------------------------------------- auth ----

def load_token(env_file: Optional[str] = None) -> str:
    """Resolve SQUARE_ACCESS_TOKEN: env → --env-file → workspace .env."""
    tok = os.environ.get("SQUARE_ACCESS_TOKEN") or os.environ.get("SQUARE_TOKEN")
    if tok:
        return tok

    candidate_paths = []
    if env_file:
        candidate_paths.append(Path(env_file))
    # Cowork workspace
    candidate_paths.append(Path("/Users/scottybe/workspace/richmondgeneral/.env"))
    candidate_paths.append(Path("/sessions/elegant-youthful-cannon/mnt/richmondgeneral/.env"))
    # Script-relative (../../../../.env from skills/<plugin>/skills/<this>/scripts/)
    here = Path(__file__).resolve()
    for up in (3, 4, 5):
        if len(here.parents) > up:
            candidate_paths.append(here.parents[up] / ".env")

    for p in candidate_paths:
        if p and p.exists():
            for line in p.read_text().splitlines():
                line = line.strip()
                if line.startswith("SQUARE_ACCESS_TOKEN=") or line.startswith("SQUARE_TOKEN="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")

    print("ERROR: SQUARE_ACCESS_TOKEN not found in env or .env", file=sys.stderr)
    sys.exit(2)


def hdrs(token: str, api_version: str) -> dict:
    return {
        "Square-Version": api_version,
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }


# ---------------------------------------------------- Square API helpers ----

def upload_image_unattached(
    token: str,
    api_version: str,
    image_path: Path,
    name: str,
    caption: str,
    mime: str = "image/jpeg",
) -> str:
    """POST /v2/catalog/images WITHOUT object_id → always mints a fresh image ID."""
    url = f"{SQUARE_API_BASE}/v2/catalog/images"
    body = {
        "idempotency_key": str(uuid.uuid4()),
        # NOTE: deliberately no "object_id" key — see file docstring
        "image": {
            "id": "#TEMP",
            "type": "IMAGE",
            "image_data": {"name": name, "caption": caption},
        },
    }
    with image_path.open("rb") as f:
        files = {
            "file": (image_path.name, f, mime),
            "request": (None, json.dumps(body), "application/json"),
        }
        r = requests.post(url, headers=hdrs(token, api_version), files=files, timeout=120)
    if not r.ok:
        print(f"  UPLOAD FAILED ({r.status_code}): {r.text}", file=sys.stderr)
        r.raise_for_status()
    return r.json()["image"]["id"]


def get_item(token: str, api_version: str, item_id: str) -> dict:
    url = f"{SQUARE_API_BASE}/v2/catalog/object/{item_id}"
    r = requests.get(url, headers=hdrs(token, api_version), timeout=30)
    r.raise_for_status()
    return r.json()["object"]


def upsert_item(token: str, api_version: str, item_obj: dict) -> dict:
    url = f"{SQUARE_API_BASE}/v2/catalog/object"
    body = {"idempotency_key": str(uuid.uuid4()), "object": item_obj}
    r = requests.post(
        url,
        headers={**hdrs(token, api_version), "Content-Type": "application/json"},
        data=json.dumps(body),
        timeout=30,
    )
    if not r.ok:
        print(f"  UPSERT FAILED ({r.status_code}): {r.text}", file=sys.stderr)
        r.raise_for_status()
    return r.json()


def delete_object(token: str, api_version: str, obj_id: str) -> dict:
    url = f"{SQUARE_API_BASE}/v2/catalog/object/{obj_id}"
    r = requests.delete(url, headers=hdrs(token, api_version), timeout=30)
    if not r.ok:
        print(f"  DELETE FAILED for {obj_id} ({r.status_code}): {r.text}", file=sys.stderr)
        r.raise_for_status()
    return r.json()


# --------------------------------------------------------- arg parsing ----

def parse_stale(spec: str) -> dict:
    """`<stale_id>:<path>:<name>:<caption>` → dict."""
    parts = spec.split(":", 3)
    if len(parts) != 4:
        raise argparse.ArgumentTypeError(
            f"--stale must be id:path:name:caption (got {spec!r})"
        )
    sid, path, name, caption = parts
    p = Path(path).expanduser()
    if not p.exists():
        raise argparse.ArgumentTypeError(f"local file not found: {p}")
    return {"stale_id": sid, "local": p, "name": name, "caption": caption}


def mime_for(p: Path) -> str:
    ext = p.suffix.lower()
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }.get(ext, "image/jpeg")


# --------------------------------------------------------------- main ----

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--item-id", required=True, help="Square catalog item ID")
    ap.add_argument(
        "--stale",
        action="append",
        required=True,
        type=parse_stale,
        metavar="ID:PATH:NAME:CAPTION",
        help="Replace this existing image ID with the file at PATH (new name/caption applied). Repeat per stale image.",
    )
    ap.add_argument(
        "--keep",
        action="append",
        default=[],
        metavar="IMG_ID",
        help="Existing image IDs to keep (in this order, after the new IDs). Repeat per kept image.",
    )
    ap.add_argument(
        "--delete-orphans",
        action="store_true",
        help="After repointing the item, delete the old stale image objects (soft delete in Square).",
    )
    ap.add_argument("--dry-run", action="store_true", help="Print plan, don't call any write endpoints.")
    ap.add_argument(
        "--api-version",
        default=os.environ.get("SQUARE_API_VERSION", DEFAULT_API_VERSION),
        help=f"Square API version header (default {DEFAULT_API_VERSION})",
    )
    ap.add_argument("--env-file", help="Path to .env containing SQUARE_ACCESS_TOKEN (optional)")
    args = ap.parse_args()

    print(f"\n=== Storefront image cache-bust for item {args.item_id} ===")
    print(f"Replacing {len(args.stale)} stale image(s); keeping {len(args.keep)} unchanged.")
    if args.dry_run:
        print("\n[DRY RUN] Would do:")
        for s in args.stale:
            print(f"  upload {s['local']} ({mime_for(s['local'])}) as new image, name={s['name']!r}")
        print(f"  patch item.image_ids = [<new ids in stale order>] + {args.keep}")
        if args.delete_orphans:
            print(f"  delete stale ids: {[s['stale_id'] for s in args.stale]}")
        return

    token = load_token(args.env_file)

    # Step 1: upload each replacement
    print("\n[1/3] Upload each replacement (no object_id)...")
    new_ids = []
    for s in args.stale:
        print(f"  • {s['name']!r}  ←  {s['local']} ({s['local'].stat().st_size:,} bytes)")
        new_id = upload_image_unattached(
            token, args.api_version, s["local"], s["name"], s["caption"], mime_for(s["local"]),
        )
        print(f"      new image_id: {new_id}    (was {s['stale_id']})")
        s["new_id"] = new_id
        new_ids.append(new_id)

    # Step 2: patch item.image_ids
    print("\n[2/3] Patch item.image_ids...")
    item = get_item(token, args.api_version, args.item_id)
    new_image_ids = new_ids + list(args.keep)
    item["item_data"]["image_ids"] = new_image_ids
    upsert_item(token, args.api_version, item)
    print(f"  image_ids now = {new_image_ids}")

    # Step 3: optional delete orphans
    if args.delete_orphans:
        print("\n[3/3] Deleting orphaned stale image objects...")
        for s in args.stale:
            print(f"  • delete {s['stale_id']} ({s['name']})")
            delete_object(token, args.api_version, s["stale_id"])
    else:
        print("\n[3/3] Skipped --delete-orphans. Old image objects remain (soft-orphaned).")

    print("\nDone. Storefront CDN will serve fresh files under the new IDs.")
    print("\nMapping (stale → new):")
    for s in args.stale:
        print(f"  {s['stale_id']}  →  {s['new_id']}    {s['name']}")
    for k in args.keep:
        print(f"  {k}  →  (unchanged)")


if __name__ == "__main__":
    main()
