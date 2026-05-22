#!/usr/bin/env python3
"""
Find and delete a Square payment link for a Richmond General item.

Used when an item has been sold and the Buy Now link must be killed so the
short URL (square.link/u/...) and the long checkout URL
(checkout.square.site/merchant/.../order/...) can no longer take a payment.

Stdlib only — no `requests`, no `python-dotenv`. Reads SQUARE_ACCESS_TOKEN
from the process env first, then from the workspace `.env` file.

Usage:
    # Discovery only (no delete) — see what would match:
    python3 delete_payment_link.py RG-XXXX

    # Confirm + delete:
    python3 delete_payment_link.py RG-XXXX --yes

    # Disambiguate when multiple links match the same SKU:
    python3 delete_payment_link.py RG-XXXX --id 6O42ERXZU4TBERKC --yes

Exit codes:
    0 — success (link deleted, OR no match found and that's fine)
    1 — generic error (network, validation, etc.)
    2 — auth not found (no token in env or .env)
    3 — Square API rejected the request (HTTP 4xx/5xx)
    4 — multiple links matched and --id was not supplied (refuse to guess)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional


# -----------------------------------------------------------------------------
# Constants — match square-image-upload-cowork conventions
# -----------------------------------------------------------------------------

# Layout: <workspace>/skills/rg-item-mark-sold/scripts/delete_payment_link.py
# → parents[3] is the workspace root.
_SCRIPT_PATH = Path(__file__).resolve()
_SCRIPT_RELATIVE_ENV = _SCRIPT_PATH.parents[3] / ".env"
_LEGACY_ABSOLUTE_ENV = Path("/Users/scottybe/workspace/richmondgeneral/.env")
DEFAULT_ENV_PATH = str(
    _SCRIPT_RELATIVE_ENV if _SCRIPT_RELATIVE_ENV.exists()
    else _LEGACY_ABSOLUTE_ENV
)
DEFAULT_ENV_PATH = os.environ.get("RG_ENV_FILE", DEFAULT_ENV_PATH)

DEFAULT_SQUARE_VERSION = "2026-04-21"
SQUARE_BASE = "https://connect.squareup.com"
TOKEN_KEYS = ("SQUARE_ACCESS_TOKEN", "SQUARE_TOKEN")  # primary, legacy fallback


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

VERBOSE = False


def log(msg: str) -> None:
    if VERBOSE:
        print(f"[delete_payment_link] {msg}", file=sys.stderr)


def parse_env_value(raw: str) -> str:
    """Strip whitespace, matching outer quotes, and unquoted inline `#`
    comments from a .env value.

    - Quoted value: take everything between the opening and the next matching
      quote verbatim — `#` inside quotes is part of the token. Anything after
      the closing quote (typically a trailing inline comment) is discarded.
    - Unquoted: everything from the first `#` onward is a comment.

    Without this, a perfectly normal `KEY=token # prod` produces a malformed
    `token # prod` and fails Square auth silently with a 401.

    Shared implementation with `parse_env_value` in
    `skills/square-image-upload-cowork/scripts/upload_to_square.py` and
    `skills/square-image-upload/scripts/refresh_item_image.py`. All three
    scripts are deliberately stdlib-only and self-contained for cowork
    sandbox portability, so the helper is duplicated rather than extracted
    — keep the three copies in sync when changing any one.
    """
    val = raw.strip()
    # Quoted value — find the next matching quote, discard everything after it.
    if val and val[0] in ("'", '"'):
        quote = val[0]
        close = val.find(quote, 1)
        if close >= 1:
            return val[1:close]
        # No closing quote on this line — fall through and treat as unquoted.
    # Unquoted: everything from the first `#` onward is a comment.
    if "#" in val:
        val = val.split("#", 1)[0].strip()
    return val


def parse_dotenv(path: str) -> dict:
    """Minimal .env parser — handles KEY=VALUE, ignores blank lines and
    full-line comments. Inline-comment handling delegated to parse_env_value.
    """
    out: dict = {}
    p = Path(path)
    if not p.exists():
        log(f".env not found at {path}")
        return out
    try:
        for raw in p.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            out[key.strip()] = parse_env_value(value)
    except OSError as e:
        log(f".env read error at {path}: {e}")
    return out


def resolve_token(env_file: str) -> str:
    """Look in process env first, then the .env file. Exit(2) if neither has it."""
    for k in TOKEN_KEYS:
        if os.environ.get(k):
            log(f"using token from process env: {k}")
            return os.environ[k]
    env = parse_dotenv(env_file)
    for k in TOKEN_KEYS:
        if env.get(k):
            log(f"using token from {env_file}: {k}")
            return env[k]
    print(
        f"ERROR: no Square access token found. Set SQUARE_ACCESS_TOKEN in env "
        f"or in {env_file}.",
        file=sys.stderr,
    )
    sys.exit(2)


def square_request(
    method: str,
    path: str,
    token: str,
    version: str,
    body: Optional[dict] = None,
) -> tuple[int, dict]:
    """Make a Square API call and return (status_code, parsed_json_or_empty)."""
    url = f"{SQUARE_BASE}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Square-Version", version)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    log(f"{method} {url}")
    try:
        with urllib.request.urlopen(req) as resp:
            payload = resp.read().decode("utf-8")
            return resp.status, (json.loads(payload) if payload else {})
    except urllib.error.HTTPError as e:
        payload = e.read().decode("utf-8")
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError:
            parsed = {"raw": payload}
        return e.code, parsed


def list_all_payment_links(token: str, version: str) -> list[dict]:
    """Paginated list of every payment link on the merchant account."""
    out: list[dict] = []
    cursor: Optional[str] = None
    while True:
        path = "/v2/online-checkout/payment-links?limit=100"
        if cursor:
            path += f"&cursor={cursor}"
        status, body = square_request("GET", path, token, version)
        if status >= 400:
            print(f"ERROR: Square returned {status}: {body}", file=sys.stderr)
            sys.exit(3)
        out.extend(body.get("payment_links", []))
        cursor = body.get("cursor")
        if not cursor:
            break
    return out


def match_links(links: list[dict], sku: str) -> list[dict]:
    """Find payment links whose description or payment_note contains the SKU.

    Match uses a word-boundary regex (`\\bSKU\\b`) so `RG-0002` does NOT
    match `RG-0020`–`RG-0029`. The hyphen in `RG-XXXX` is not a word
    character to Python's `\\b`, so we anchor with explicit non-digit /
    non-letter assertions on either side.

    The most common authoring convention is `"RG-0002 - 1892 Kings of the
    Forest"` in `description` and a similar string in `payment_note`. Either
    field can carry it depending on who created the link.
    """
    # (?<![A-Z0-9-]) and (?![A-Z0-9-]) prevent the SKU from being a prefix/
    # suffix of a longer alphanumeric+hyphen run like another SKU.
    pattern = re.compile(
        r"(?<![A-Z0-9-])" + re.escape(sku.upper()) + r"(?![A-Z0-9-])",
        re.IGNORECASE,
    )
    hits = []
    for L in links:
        desc = L.get("description") or ""
        note = L.get("payment_note") or ""
        if pattern.search(desc) or pattern.search(note):
            hits.append(L)
    return hits


def print_link(L: dict, prefix: str = "") -> None:
    print(f"{prefix}id:          {L.get('id')}")
    print(f"{prefix}url:         {L.get('url')}")
    print(f"{prefix}long_url:    {L.get('long_url')}")
    print(f"{prefix}description: {L.get('description')}")
    print(f"{prefix}payment_note:{L.get('payment_note')}")
    print(f"{prefix}order_id:    {L.get('order_id')}")
    print(f"{prefix}created_at:  {L.get('created_at')}")


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------


def main() -> int:
    global VERBOSE

    ap = argparse.ArgumentParser(
        description="Find and delete a Square payment link by SKU.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument(
        "sku",
        help="Item SKU to match (e.g. RG-0002). Matched as a case-insensitive "
        "substring against payment-link description and payment_note.",
    )
    ap.add_argument(
        "--id",
        help="Specific payment_link_id to delete. Required when multiple "
        "links match the same SKU.",
    )
    ap.add_argument(
        "--yes",
        action="store_true",
        help="Actually perform the DELETE. Without this flag the script only "
        "prints what it would delete (dry-run by default — fail-safe).",
    )
    ap.add_argument(
        "--env-file",
        default=DEFAULT_ENV_PATH,
        help=f"Path to .env (default: {DEFAULT_ENV_PATH}).",
    )
    ap.add_argument(
        "--version",
        default=DEFAULT_SQUARE_VERSION,
        help=f"Square API version (default: {DEFAULT_SQUARE_VERSION}).",
    )
    ap.add_argument("--verbose", action="store_true")

    args = ap.parse_args()
    VERBOSE = args.verbose

    token = resolve_token(args.env_file)

    log(f"listing payment links to match SKU {args.sku!r}…")
    links = list_all_payment_links(token, args.version)
    log(f"found {len(links)} total payment links on the merchant")

    matches = match_links(links, args.sku)

    # Filter by explicit --id if the user supplied one
    if args.id:
        matches = [L for L in matches if L.get("id") == args.id]
        if not matches:
            # Consistent with the bare-SKU "no match" path below — already-gone
            # is a success outcome for this skill, not an error. The operator
            # most likely passed a stale --id (the link was already deleted via
            # dashboard or an earlier run).
            print(
                f"No payment link with id={args.id} matched SKU {args.sku}. "
                f"It may already have been deleted."
            )
            return 0

    if not matches:
        print(
            f"No payment link found matching SKU {args.sku}. "
            f"It may have already been deleted, or it never existed "
            f"(off-channel sale, e.g. cash / FB Marketplace).",
        )
        return 0

    if len(matches) > 1 and not args.id:
        print(
            f"Multiple payment links matched SKU {args.sku} "
            f"({len(matches)} hits). Refusing to auto-delete — pass --id "
            f"to disambiguate.",
            file=sys.stderr,
        )
        for L in matches:
            print()
            print_link(L, prefix="  ")
        return 4

    target = matches[0]

    print(f"Matched payment link for {args.sku}:")
    print_link(target, prefix="  ")
    print()

    if not args.yes:
        print(
            "Dry-run — pass --yes to actually delete. Both the short URL "
            "(square.link/u/...) and the long URL "
            "(checkout.square.site/.../order/...) will return 303/404 after "
            "delete."
        )
        return 0

    link_id = target["id"]
    log(f"DELETE /v2/online-checkout/payment-links/{link_id}")
    status, body = square_request(
        "DELETE",
        f"/v2/online-checkout/payment-links/{link_id}",
        token,
        args.version,
    )
    if status >= 400:
        print(f"ERROR: Square returned {status}: {body}", file=sys.stderr)
        return 3

    print(json.dumps(body, indent=2))
    cancelled_order = body.get("cancelled_order_id")
    if cancelled_order:
        print()
        print(
            f"Deleted payment link {link_id}. Cancelled order: "
            f"{cancelled_order}."
        )
        print("Both URL forms should now 303/404 — verify with:")
        short_slug = (target.get("url") or "").rsplit("/", 1)[-1]
        print(
            f"  curl -sI https://square.link/u/{short_slug} "
            f"-o /dev/null -w 'short: %{{http_code}}\\n'"
        )
        print(
            f"  curl -sI https://checkout.square.site/merchant/"
            f"7MM9AFJAD0XHW/order/{cancelled_order} "
            f"-o /dev/null -w 'long:  %{{http_code}}\\n'"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
