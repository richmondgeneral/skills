#!/usr/bin/env python3
"""
Find and delete a Square payment link for a Richmond General item.

Used when an item has been sold and the Buy Now link must be killed so the
short URL (square.link/u/...) and the long checkout URL
(checkout.square.site/merchant/.../order/...) can no longer take a payment.

Stdlib only — no `requests`, no `python-dotenv`. Reads SQUARE_ACCESS_TOKEN
from the process env first, then from the workspace `.env` file.

Discovery matches a SKU only when it appears in the link's `description` or
`payment_note`. A link with BOTH fields null (Square allows this) is invisible
to a SKU search — so an explicit selector is the only way to reach it:

    --id <payment_link_id>   delete that link directly (bypasses SKU metadata)
    --url <slug-or-url>      match the short square.link slug or full checkout URL
    --order-id <order_id>    match the link's order_id

Usage:
    # Discovery only (no delete) — see what a SKU would match:
    python3 delete_payment_link.py RG-XXXX

    # Confirm + delete:
    python3 delete_payment_link.py RG-XXXX --yes

    # Reach a link the SKU can't see (null description/payment_note) — by id,
    # short-URL slug, or order_id; any one works even with no SKU:
    python3 delete_payment_link.py --id 2PE4WMYVYB6TXE2V --yes
    python3 delete_payment_link.py --url WYk1Yl12 --yes
    python3 delete_payment_link.py --order-id Td1qji0tORadRLBNfgZGWR0WIjFZY --yes

    # Read-only sweep: flag every live link whose item is already marked sold:
    python3 delete_payment_link.py --audit

Exit codes:
    0 — success (link deleted, OR the link is confirmably already gone)
    1 — generic error (network, validation, etc.)
    2 — auth not found (no token in env or .env)
    3 — Square API rejected the request (HTTP 4xx/5xx)
    4 — multiple links matched a non-id selector (pass --id to pick one)
    5 — SKU matched nothing but live links exist; could be a null-metadata link
        (re-run with --id/--url/--order-id, or --audit) — refuses "all clear"
    6 — audit found a sold item with a live payment link (phantom-charge risk)
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


def _slug(u: Optional[str]) -> str:
    """Last path segment of a URL (or a bare slug), lowercased.

    ``https://square.link/u/WYk1Yl12`` -> ``wyk1yl12``; a bare ``WYk1Yl12`` ->
    the same. Lets ``--url`` accept the short link, the long checkout URL, or
    just the slug a human copied off a printed QR label.
    """
    if not u:
        return ""
    return u.rstrip("/").rsplit("/", 1)[-1].strip().lower()


def select_links(
    links: list[dict],
    sku: Optional[str] = None,
    *,
    link_id: Optional[str] = None,
    url: Optional[str] = None,
    order_id: Optional[str] = None,
) -> list[dict]:
    """Resolve the payment link(s) the operator means, from the FULL link list.

    Explicit selectors win over SKU and search *every* link regardless of its
    ``description`` / ``payment_note``. This is the fix for the RG-0014 gap:
    that link had both metadata fields null, so it was invisible to a SKU search
    and the old ``--id`` (which filtered *within* SKU matches) could not rescue
    it. Here ``--id`` / ``--url`` / ``--order-id`` go straight at the full list.

    Precedence when several are passed: link_id > order_id > url > sku.
    """
    if link_id:
        return [L for L in links if L.get("id") == link_id]
    if order_id:
        return [L for L in links if L.get("order_id") == order_id]
    if url:
        want = _slug(url)
        if not want:
            return []
        return [
            L
            for L in links
            if _slug(L.get("url")) == want or _slug(L.get("long_url")) == want
        ]
    if sku:
        return match_links(links, sku)
    return []


# -----------------------------------------------------------------------------
# Audit — read-only cross-check of every live link against the item ledger
# -----------------------------------------------------------------------------


def load_item_records(items_dir: str) -> list[dict]:
    """Read every ``items/RG-*/`` folder into ``{sku, status, blob}`` records.

    ``status`` comes from ``status.json`` (``None`` if absent/unreadable → the
    item is treated as available). ``blob`` is the lowercased concatenation of
    ``status.json``, ``label.json`` and ``index.html`` so the audit can attribute
    a null-metadata link to its item by finding the link's id / order_id /
    url-slug anywhere in that item's own files.
    """
    base = Path(items_dir)
    out: list[dict] = []
    if not base.is_dir():
        log(f"items dir not found: {items_dir}")
        return out
    for d in sorted(base.glob("RG-*")):
        if not d.is_dir():
            continue
        status: Optional[str] = None
        parts: list[str] = []
        for fn in ("status.json", "label.json", "index.html"):
            f = d / fn
            if not f.exists():
                continue
            try:
                text = f.read_text(encoding="utf-8")
            except OSError as e:
                log(f"read error {f}: {e}")
                continue
            parts.append(text)
            if fn == "status.json":
                try:
                    status = json.loads(text).get("status")
                except (json.JSONDecodeError, AttributeError):
                    pass
        out.append(
            {"sku": d.name, "status": status, "blob": "\n".join(parts).lower()}
        )
    return out


def _normalize_text(s: str) -> str:
    """Lowercase and collapse every run of non-alphanumeric chars to one space.

    Makes line-item-name matching robust to punctuation/dash differences between
    a Square order name ("Atari 1050 Disk Drive — Happy Upgrade") and the same
    name as it appears in an item's index.html / label.json.
    """
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def batch_retrieve_orders(
    token: str, version: str, order_ids: list[str]
) -> dict:
    """Fetch orders by id (read-only) → ``{order_id: order}``.

    Lets the audit attribute a null-metadata payment link to its item via the
    order's line items (``catalog_object_id`` → recorded variation id, or the
    line-item name → the item's product name). Square's batch endpoint caps at
    100 ids/call, so we chunk. A failed chunk is logged and skipped — a link
    whose order can't be read simply stays unattributed (WARN), never crashes.
    """
    out: dict = {}
    ids = [o for o in dict.fromkeys(order_ids) if o]  # de-dupe, drop falsy
    for i in range(0, len(ids), 100):
        chunk = ids[i : i + 100]
        status, body = square_request(
            "POST",
            "/v2/orders/batch-retrieve",
            token,
            version,
            {"order_ids": chunk},
        )
        if status >= 400:
            log(f"order batch-retrieve returned {status}: {body}")
            continue
        for o in body.get("orders", []):
            oid = o.get("id")
            if oid:
                out[oid] = o
    return out


# Generic line-item names that identify no specific item — never attribute on these.
_GENERIC_LINE_NAMES = {
    "custom amount",
    "custom",
    "item",
    "payment",
    "deposit",
    "balance",
    "order",
}


def order_signals(order: Optional[dict]) -> list[str]:
    """Attribution strings derived from an order's line items, strongest first.

    - ``catalog_object_id`` (exact, lowercased) — matches a modern item's
      recorded variation/object id in its ``label.json``.
    - ``"name:" + normalized line-item name`` (>= 6 chars, not generic) —
      matches the item's product name in ``index.html`` / ``label.json``. This
      is what catches a pre-ledger sold item like RG-0003 whose order line
      carried no ``catalog_object_id`` and whose link had null metadata.
    """
    sigs: list[str] = []
    for li in (order or {}).get("line_items", []):
        cid = li.get("catalog_object_id")
        if cid:
            sigs.append(cid.lower())
        name = _normalize_text(li.get("name") or "")
        if len(name) >= 6 and name not in _GENERIC_LINE_NAMES:
            sigs.append("name:" + name)
    return sigs


def _link_identifiers(link: dict) -> list[str]:
    """The strings that uniquely tie a link to an item, lowercased."""
    raw = [
        link.get("id"),
        link.get("order_id"),
        _slug(link.get("url")),
        _slug(link.get("long_url")),
    ]
    return [s.lower() for s in raw if s]


def attribute_link(
    link: dict, items: list[dict]
) -> tuple[Optional[dict], Optional[str]]:
    """Map a live link to the item it belongs to, returning ``(item, how)``.

    ``how`` is ``"record"`` (a link identifier appears in the item's files),
    ``"metadata"`` (the item's SKU appears in the link's description/payment_note),
    ``"order-catalog"`` / ``"order-name"`` (the link's order line items — set on
    the link as ``_order_signals`` by the audit — match the item's recorded
    catalog id or product name), or ``(None, None)`` when the link can't be tied
    to any item (a true orphan worth flagging).
    """
    idents = _link_identifiers(link)
    for it in items:
        blob = it.get("blob") or ""
        if any(ident and ident in blob for ident in idents):
            return it, "record"
    haystack = f"{link.get('description') or ''}\n{link.get('payment_note') or ''}"
    for it in items:
        sku = it.get("sku") or ""
        if not sku:
            continue
        pat = re.compile(
            r"(?<![A-Z0-9-])" + re.escape(sku.upper()) + r"(?![A-Z0-9-])",
            re.IGNORECASE,
        )
        if pat.search(haystack):
            return it, "metadata"
    # Third pass — order line items (populated by the audit's order lookup).
    # catalog_object_id matches a modern item's recorded variation/object id; a
    # normalized line-item name matches the item's product name. This closes the
    # gap that let RG-0003 (sold, pre-ledger, null-metadata link) slip to WARN.
    for sig in link.get("_order_signals", []):
        if sig.startswith("name:"):
            needle = sig[len("name:"):]
            for it in items:
                nb = it.get("norm_blob")
                if nb is None:
                    nb = _normalize_text(it.get("blob") or "")
                    it["norm_blob"] = nb
                if needle and needle in nb:
                    return it, "order-name"
        else:
            for it in items:
                if sig and sig in (it.get("blob") or ""):
                    return it, "order-catalog"
    return None, None


def audit_links(links: list[dict], items: list[dict]) -> list[dict]:
    """Classify every live payment link against the item ledger (read-only).

    - **CRITICAL**: link maps to an item whose ``status.json`` says ``sold`` — a
      live checkout URL on a sold item (phantom-charge risk; should be deleted).
    - **WARN**: link can't be attributed to any item — e.g. a null-metadata link
      like RG-0014's. Could be a sold item's orphaned link; needs a human look.
    - **OK**: link maps to a still-available item (an expected active listing).
    """
    findings: list[dict] = []
    for L in links:
        it, how = attribute_link(L, items)
        if it is None:
            severity, sku, status = "WARN", None, None
        elif (it.get("status") or "").lower() == "sold":
            severity, sku, status = "CRITICAL", it.get("sku"), "sold"
        else:
            severity, sku, status = "OK", it.get("sku"), it.get("status")
        findings.append(
            {
                "severity": severity,
                "sku": sku,
                "status": status,
                "attributed_by": how,
                "link_id": L.get("id"),
                "url": L.get("url"),
                "order_id": L.get("order_id"),
                "description": L.get("description"),
                "payment_note": L.get("payment_note"),
            }
        )
    return findings


def audit_has_critical(findings: list[dict]) -> bool:
    return any(f.get("severity") == "CRITICAL" for f in findings)


def format_audit_report(findings: list[dict], item_count: int) -> str:
    crit = [f for f in findings if f["severity"] == "CRITICAL"]
    warn = [f for f in findings if f["severity"] == "WARN"]
    ok = [f for f in findings if f["severity"] == "OK"]
    lines = [
        f"Payment-link audit — {len(findings)} live link(s) vs "
        f"{item_count} item record(s)",
        f"  CRITICAL: {len(crit)}   WARN: {len(warn)}   OK: {len(ok)}",
        "",
    ]
    if crit:
        lines.append("CRITICAL — sold item still has a LIVE payment link:")
        for f in crit:
            lines.append(
                f"  • {f['sku']}  id={f['link_id']}  {f['url']}  "
                f"order={f['order_id']}  (matched by {f['attributed_by']})"
            )
            lines.append(
                f"      delete: delete_payment_link.py "
                f"--id {f['link_id']} --yes"
            )
        lines.append("")
    if warn:
        lines.append(
            "WARN — live link not attributable to any item (manual review; "
            "may be a sold item's null-metadata link):"
        )
        for f in warn:
            lines.append(
                f"  • id={f['link_id']}  {f['url']}  order={f['order_id']}  "
                f"desc={f['description']!r} note={f['payment_note']!r}"
            )
        lines.append("")
    if not crit and not warn:
        lines.append(
            "All live payment links map to still-available items. "
            "No phantom-charge risk found."
        )
    return "\n".join(lines).rstrip()


def print_link(L: dict, prefix: str = "") -> None:
    print(f"{prefix}id:          {L.get('id')}")
    print(f"{prefix}url:         {L.get('url')}")
    print(f"{prefix}long_url:    {L.get('long_url')}")
    print(f"{prefix}description: {L.get('description')}")
    print(f"{prefix}payment_note:{L.get('payment_note')}")
    print(f"{prefix}order_id:    {L.get('order_id')}")
    print(f"{prefix}created_at:  {L.get('created_at')}")


def run_audit(token: str, args) -> int:
    """Read-only phantom-charge sweep. Never deletes (ignores --yes)."""
    links = list_all_payment_links(token, args.version)
    log(f"auditing {len(links)} live links against {args.items_dir}")
    items = load_item_records(args.items_dir)
    # Cheap attribution first (record/metadata). Only links that STILL don't
    # resolve get an order lookup — keeps API calls and fuzzy name-matching to
    # the minimum needed to catch a null-metadata link on a sold item.
    unresolved_order_ids = [
        L.get("order_id")
        for L in links
        if attribute_link(L, items)[0] is None and L.get("order_id")
    ]
    if unresolved_order_ids:
        orders = batch_retrieve_orders(token, args.version, unresolved_order_ids)
        log(
            f"fetched {len(orders)} order(s) for "
            f"{len(set(unresolved_order_ids))} unresolved link(s)"
        )
        for L in links:
            oid = L.get("order_id")
            if oid in orders:
                L["_order_signals"] = order_signals(orders[oid])
    findings = audit_links(links, items)
    print(format_audit_report(findings, len(items)))
    if audit_has_critical(findings):
        # Non-zero so an automated caller / CI treats a sold item with a live
        # link as the failure it is.
        return 6
    return 0


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------


def main() -> int:
    global VERBOSE

    ap = argparse.ArgumentParser(
        description="Find and delete a Square payment link by SKU, id, url, or "
        "order_id; or --audit every live link against the item ledger.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument(
        "sku",
        nargs="?",
        help="Item SKU to match (e.g. RG-0002), as a word-boundary match against "
        "payment-link description and payment_note. Optional — omit it and pass "
        "--id/--url/--order-id to reach a link with empty metadata.",
    )
    ap.add_argument(
        "--id",
        help="Delete this payment_link_id directly, from the FULL link list — "
        "bypasses the SKU metadata match, so it reaches a link whose "
        "description/payment_note are null (the RG-0014 case).",
    )
    ap.add_argument(
        "--url",
        help="Select by short-URL slug or full URL (e.g. WYk1Yl12 or "
        "https://square.link/u/WYk1Yl12). Matches the link's url or long_url; "
        "also bypasses the SKU metadata match.",
    )
    ap.add_argument(
        "--order-id",
        dest="order_id",
        help="Select by the link's order_id. Also bypasses the SKU match.",
    )
    ap.add_argument(
        "--audit",
        action="store_true",
        help="Read-only: list every live payment link and flag any whose item is "
        "already marked sold (status.json status=sold) — phantom-charge sweep. "
        "Never deletes; ignores --yes.",
    )
    ap.add_argument(
        "--items-dir",
        dest="items_dir",
        default=os.environ.get(
            "RG_ITEMS_DIR", "/Users/scottybe/workspace/richmondgeneral/items"
        ),
        help="Item ledger root for --audit (default: the GitHub Pages items "
        "repo, override with --items-dir or RG_ITEMS_DIR).",
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

    if not (args.sku or args.id or args.url or args.order_id or args.audit):
        ap.error("supply a SKU, or one of --id/--url/--order-id, or --audit")

    token = resolve_token(args.env_file)

    if args.audit:
        return run_audit(token, args)

    log("listing all payment links…")
    links = list_all_payment_links(token, args.version)
    log(f"found {len(links)} total payment links on the merchant")

    explicit = bool(args.id or args.url or args.order_id)
    targets = select_links(
        links,
        sku=args.sku,
        link_id=args.id,
        url=args.url,
        order_id=args.order_id,
    )

    if not targets:
        if explicit:
            # An explicit selector that matches nothing means the link is already
            # gone — the desired end state. Success, not an error.
            sel = args.id or args.order_id or args.url
            print(
                f"No live payment link matched the selector ({sel}). "
                f"It may already have been deleted."
            )
            return 0
        if links:
            # FIX (RG-0014): a SKU search finding nothing is NOT proof the link is
            # gone. A link with null description/payment_note cannot match by SKU
            # — exactly the phantom-charge gap. Refuse the old "all clear":
            # surface every live link so the operator re-runs with an explicit
            # selector (or --audit), and exit non-zero so an automated caller
            # can't mistake this for "handled".
            print(
                f"No live payment link's description/payment_note contained "
                f"{args.sku}. This is NOT proof the link is gone — a link with "
                f"empty metadata cannot match by SKU (the RG-0014 phantom-charge "
                f"gap). {len(links)} live link(s) exist on the account; identify "
                f"the item's link below and re-run with --id / --url / "
                f"--order-id, or run --audit to cross-check every link against "
                f"the item ledger.",
                file=sys.stderr,
            )
            for L in links:
                print(file=sys.stderr)
                print_link(L, prefix="  ")
            return 5
        print(
            f"No payment links exist on the merchant account at all — nothing to "
            f"delete for {args.sku} (off-channel sale, or already cleaned up)."
        )
        return 0

    if len(targets) > 1:
        print(
            f"Multiple payment links matched ({len(targets)} hits). Refusing to "
            f"auto-delete — pass --id <PAYMENT_LINK_ID> to pick exactly one.",
            file=sys.stderr,
        )
        for L in targets:
            print(file=sys.stderr)
            print_link(L, prefix="  ")
        return 4

    target = targets[0]

    print(f"Matched payment link for {args.sku or target.get('id')}:")
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
