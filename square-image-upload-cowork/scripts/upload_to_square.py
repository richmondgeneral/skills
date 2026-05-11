#!/usr/bin/env python3
"""
Upload an image to Square Catalog from a Cowork session.

Stdlib only — no `requests`, no `python-dotenv`. Reads SQUARE_ACCESS_TOKEN
from the process env first, then from the workspace `.env` file.

Usage:
    python3 upload_to_square.py --source <path-or-url> --item-id <ID> [options]
    python3 upload_to_square.py --source <path-or-url> --variation-id <ID> [options]
    python3 upload_to_square.py --source <path-or-url> --image-id <ID>     # replace in place

Options:
    --source PATH_OR_URL     Required. Local file path or http(s) URL.
    --item-id ID             Attach new image to this Square item.
    --variation-id ID        Attach new image to this Square item variation.
    --image-id ID            Replace an existing CatalogImage in place.
    --name NAME              Display name for the image.
    --caption CAPTION        Caption shown on Square Online.
    --primary                Set as the item's primary (hero) image.
    --env-file PATH          Override the default .env location.
    --version VERSION        Square API version (default: 2026-04-21).
    --json                   Emit machine-readable JSON on success.
    --verbose                Log each resolution/HTTP step to stderr.

Exit codes:
    0 — success
    1 — generic error (network, validation, etc.)
    2 — auth not found (no token in env or .env)
    3 — Square API rejected the request (HTTP 4xx/5xx)
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Optional, Tuple

# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------

DEFAULT_ENV_PATH = "/Users/scottybe/workspace/richmondgeneral/.env"
DEFAULT_SQUARE_VERSION = "2026-04-21"
SQUARE_BASE = "https://connect.squareup.com"
TOKEN_KEYS = ("SQUARE_ACCESS_TOKEN", "SQUARE_TOKEN")  # primary, legacy fallback


# -----------------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------------

VERBOSE = False


def log(msg: str) -> None:
    if VERBOSE:
        print(f"[upload_to_square] {msg}", file=sys.stderr)


# -----------------------------------------------------------------------------
# Auth resolution: env var → workspace .env (in that order)
# -----------------------------------------------------------------------------

def parse_dotenv(path: str) -> dict:
    """Minimal .env parser — handles KEY=VALUE, ignores comments and blank lines.
    Doesn't do variable expansion; we don't need that here.
    """
    out: dict = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()
                # Strip wrapping quotes if present
                if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
                    value = value[1:-1]
                # Inline comment after value (only if value isn't quoted-out — simple rule)
                if "#" in value:
                    value = value.split("#", 1)[0].strip()
                out[key] = value
    except FileNotFoundError:
        log(f".env not found at {path}")
    except OSError as e:
        log(f".env read error at {path}: {e}")
    return out


def resolve_token(env_file: str) -> Optional[str]:
    """Resolve SQUARE_ACCESS_TOKEN in priority order; return None if not found."""
    for key in TOKEN_KEYS:
        v = os.environ.get(key)
        if v:
            log(f"token resolved from process env ({key})")
            return v
    parsed = parse_dotenv(env_file)
    for key in TOKEN_KEYS:
        v = parsed.get(key)
        if v:
            log(f"token resolved from {env_file} ({key})")
            return v
    return None


# -----------------------------------------------------------------------------
# Source resolution: file path or URL → (bytes, filename, mime_type)
# -----------------------------------------------------------------------------

def fetch_source(source: str) -> Tuple[bytes, str, str]:
    """Return (bytes, filename, mime_type) for a local path or http(s) URL."""
    if source.startswith("http://") or source.startswith("https://"):
        log(f"fetching from URL: {source}")
        req = urllib.request.Request(source, headers={"User-Agent": "rg-image-upload/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
            content_type = resp.headers.get("Content-Type", "").split(";")[0].strip()
            # Derive a filename from the URL path
            parsed_url = urllib.parse.urlparse(source)
            filename = os.path.basename(parsed_url.path) or "image"
            if not content_type:
                content_type = mimetypes.guess_type(filename)[0] or "image/jpeg"
            return data, filename, content_type
    # Local file
    p = Path(source).expanduser().resolve()
    log(f"reading from file: {p}")
    if not p.exists():
        raise FileNotFoundError(f"source file not found: {p}")
    with open(p, "rb") as f:
        data = f.read()
    content_type = mimetypes.guess_type(str(p))[0] or "image/jpeg"
    return data, p.name, content_type


# -----------------------------------------------------------------------------
# Multipart body construction (stdlib — no requests dependency)
# -----------------------------------------------------------------------------

def build_multipart(
    json_envelope: dict,
    image_bytes: bytes,
    image_filename: str,
    image_mime: str,
) -> Tuple[bytes, str]:
    """Build a multipart/form-data body with exactly two parts:
    1. `request` — application/json
    2. `image_file` — the binary image

    Returns (body_bytes, content_type_header_value).
    """
    boundary = f"----rgImageUpload{uuid.uuid4().hex}"
    parts: list[bytes] = []

    # Part 1: JSON envelope
    json_body = json.dumps(json_envelope, separators=(",", ":")).encode("utf-8")
    parts.append(f"--{boundary}\r\n".encode("ascii"))
    parts.append(b'Content-Disposition: form-data; name="request"\r\n')
    parts.append(b"Content-Type: application/json; charset=utf-8\r\n\r\n")
    parts.append(json_body)
    parts.append(b"\r\n")

    # Part 2: binary image
    safe_filename = image_filename.replace('"', "")
    parts.append(f"--{boundary}\r\n".encode("ascii"))
    parts.append(
        f'Content-Disposition: form-data; name="image_file"; filename="{safe_filename}"\r\n'.encode("ascii")
    )
    parts.append(f"Content-Type: {image_mime}\r\n\r\n".encode("ascii"))
    parts.append(image_bytes)
    parts.append(b"\r\n")

    # Closing boundary
    parts.append(f"--{boundary}--\r\n".encode("ascii"))

    body = b"".join(parts)
    content_type = f"multipart/form-data; boundary={boundary}"
    return body, content_type


# -----------------------------------------------------------------------------
# Square API calls
# -----------------------------------------------------------------------------

def square_request(
    method: str,
    path: str,
    token: str,
    api_version: str,
    body: Optional[bytes] = None,
    content_type: Optional[str] = None,
) -> Tuple[int, dict]:
    """Send a request to Square. Return (status_code, parsed_json)."""
    url = f"{SQUARE_BASE}{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Square-Version": api_version,
        "Accept": "application/json",
    }
    if content_type:
        headers["Content-Type"] = content_type

    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    log(f"{method} {path}")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            status = resp.status
            raw = resp.read().decode("utf-8") if resp.length != 0 else ""
            parsed = json.loads(raw) if raw else {}
            return status, parsed
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {"raw_response": raw}
        return e.code, parsed


def create_catalog_image(
    token: str,
    api_version: str,
    image_bytes: bytes,
    image_filename: str,
    image_mime: str,
    object_id: Optional[str] = None,
    name: Optional[str] = None,
    caption: Optional[str] = None,
    is_primary: bool = False,
) -> Tuple[int, dict]:
    """POST /v2/catalog/images — create a new CatalogImage and optionally
    attach it to an item or variation."""
    envelope: dict = {
        "idempotency_key": str(uuid.uuid4()),
        "image": {
            "type": "IMAGE",
            "id": "#image_" + uuid.uuid4().hex[:12],
            "image_data": {},
        },
    }
    if name:
        envelope["image"]["image_data"]["name"] = name
    if caption:
        envelope["image"]["image_data"]["caption"] = caption
    if object_id:
        envelope["object_id"] = object_id
    if is_primary:
        envelope["is_primary"] = True

    body, content_type = build_multipart(envelope, image_bytes, image_filename, image_mime)
    return square_request("POST", "/v2/catalog/images", token, api_version, body, content_type)


def update_catalog_image(
    token: str,
    api_version: str,
    image_id: str,
    image_bytes: bytes,
    image_filename: str,
    image_mime: str,
    name: Optional[str] = None,
    caption: Optional[str] = None,
) -> Tuple[int, dict]:
    """PUT /v2/catalog/images/{image_id} — replace existing image content."""
    envelope: dict = {
        "idempotency_key": str(uuid.uuid4()),
        "image": {
            "type": "IMAGE",
            "id": image_id,
            "image_data": {},
        },
    }
    if name:
        envelope["image"]["image_data"]["name"] = name
    if caption:
        envelope["image"]["image_data"]["caption"] = caption

    body, content_type = build_multipart(envelope, image_bytes, image_filename, image_mime)
    return square_request(
        "PUT",
        f"/v2/catalog/images/{image_id}",
        token,
        api_version,
        body,
        content_type,
    )


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Upload an image to Square Catalog (Cowork-native)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--source", required=True, help="Local file path or http(s) URL.")
    target = p.add_mutually_exclusive_group(required=True)
    target.add_argument("--item-id", help="Attach new image to this Square item.")
    target.add_argument("--variation-id", help="Attach new image to this variation.")
    target.add_argument("--image-id", help="Replace an existing CatalogImage in place.")
    p.add_argument("--name", help="Image display name.")
    p.add_argument("--caption", help="Image caption (shown on Square Online).")
    p.add_argument("--primary", action="store_true", help="Set as the item's primary image.")
    p.add_argument("--env-file", default=DEFAULT_ENV_PATH, help="Path to .env file.")
    p.add_argument("--version", default=DEFAULT_SQUARE_VERSION, help="Square-Version header.")
    p.add_argument("--json", action="store_true", help="Output JSON on success.")
    p.add_argument("--verbose", action="store_true", help="Log steps to stderr.")
    return p.parse_args()


def main() -> int:
    global VERBOSE
    args = parse_args()
    VERBOSE = args.verbose

    # --- Resolve auth ----------------------------------------------------
    token = resolve_token(args.env_file)
    if not token:
        print(
            f"ERROR: SQUARE_ACCESS_TOKEN not found in process env or {args.env_file}.\n"
            "  Set it in your shell (`export SQUARE_ACCESS_TOKEN=...`) or add it to the .env file.",
            file=sys.stderr,
        )
        return 2

    # --- Fetch the source image bytes ------------------------------------
    try:
        image_bytes, filename, mime = fetch_source(args.source)
    except Exception as e:
        print(f"ERROR fetching source: {e}", file=sys.stderr)
        return 1
    log(f"source: {len(image_bytes)} bytes, filename={filename}, mime={mime}")

    # --- Call Square ----------------------------------------------------
    if args.image_id:
        # Replace existing image
        status, body = update_catalog_image(
            token=token,
            api_version=args.version,
            image_id=args.image_id,
            image_bytes=image_bytes,
            image_filename=filename,
            image_mime=mime,
            name=args.name,
            caption=args.caption,
        )
    else:
        object_id = args.item_id or args.variation_id
        status, body = create_catalog_image(
            token=token,
            api_version=args.version,
            image_bytes=image_bytes,
            image_filename=filename,
            image_mime=mime,
            object_id=object_id,
            name=args.name,
            caption=args.caption,
            is_primary=args.primary,
        )

    # --- Result ---------------------------------------------------------
    if status >= 400:
        print(f"ERROR: Square returned HTTP {status}", file=sys.stderr)
        print(json.dumps(body, indent=2), file=sys.stderr)
        return 3

    if args.json:
        print(json.dumps(body, indent=2))
    else:
        image = body.get("image", {})
        image_data = image.get("image_data", {})
        print(f"Success.")
        print(f"  image_id: {image.get('id', '?')}")
        print(f"  url:      {image_data.get('url', '?')}")
        if args.item_id:
            print(f"  attached to item: {args.item_id}")
        if args.variation_id:
            print(f"  attached to variation: {args.variation_id}")
        if args.primary:
            print(f"  set as primary")

    return 0


if __name__ == "__main__":
    sys.exit(main())
