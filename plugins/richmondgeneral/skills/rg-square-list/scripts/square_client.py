#!/usr/bin/env python3
"""
Shared Square API client for the rg-square-list and rg-reprice tools (Phase C1).

This is the single import surface both new tools use to talk to Square. It is
deliberately:

  * **stdlib-only at runtime** — urllib/json/os/subprocess/pathlib, NO `requests`
    — so it runs unchanged under a bare non-login shell over the osascript
    Mac bridge (where shell-exported keys and pip-installed deps may be absent).
  * **self-contained** — the token resolver is copied verbatim from
    rg-full-auto/scripts/sku_authority.py rather than imported across skills, so
    a single file path works standalone, from an orchestrator, and over the
    bridge.

The only non-stdlib dependency is `qrcode[pil]`, used by exactly one helper
(`gen_qr_png`); its import lives INSIDE that function so the module imports fine
without it present.

Network goes through one seam — `_http` — which every test monkeypatches, so the
test suite never makes a real call. `square_request` builds Square's auth/version
headers on top of it; the higher-level helpers (`create_payment_link`,
`delete_payment_link`) layer on the payment-link endpoints.

Scope (C1): token + canonical constants + urllib transport + payment-link
create/delete + QR + shared money parsing. The catalog item-create logic and the
CLI are Phase C2 and intentionally NOT here.
"""

from __future__ import annotations

import json
import os
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional


# -----------------------------------------------------------------------------
# Canonical constants — the single source of truth for the new tools.
# -----------------------------------------------------------------------------

LOCATION_ID = "B87BAEZ0NWV34"
API_VERSION = "2026-04-21"
MERCHANT_ID = "7MM9AFJAD0XHW"
TAX_ID = "LPKEJF7H27NOPK7EE6A5CA7V"
CAT_COLLECTIBLES = "YQWBSOJDENMXDGUUQ3TGI3HF"
CAT_NEW_ARRIVALS = "TGWDFETSQPR6BF67YJCTOLW6"
BASE = "https://connect.squareup.com"

# Token env var names: primary, then legacy fallback.
_TOKEN_KEYS = ("SQUARE_ACCESS_TOKEN", "SQUARE_TOKEN")


# -----------------------------------------------------------------------------
# Token resolution — copied verbatim from rg-full-auto/scripts/sku_authority.py
# (_resolve_square_token, ~lines 149-179). NO cross-skill import, so this works
# standalone, from the orchestrator, and over the osascript bridge's bare shell.
# Order: env (SQUARE_ACCESS_TOKEN/SQUARE_TOKEN) -> macOS Keychain -> workspace .env
# -----------------------------------------------------------------------------

def _resolve_square_token() -> Optional[str]:
    """Resolve the Square access token with NO cross-skill import, so this works
    standalone, from the orchestrator, and over the osascript bridge's bare shell.
    Order: env (SQUARE_ACCESS_TOKEN/SQUARE_TOKEN) -> macOS Keychain -> workspace .env."""
    for name in ("SQUARE_ACCESS_TOKEN", "SQUARE_TOKEN"):
        v = os.environ.get(name)
        if v:
            return v
    try:
        r = subprocess.run(
            ["security", "find-generic-password", "-a", os.environ.get("USER", ""),
             "-s", "SQUARE_ACCESS_TOKEN", "-w"],
            capture_output=True, text=True,
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except Exception:  # noqa: BLE001
        pass
    env_path = Path.home() / "workspace" / "richmondgeneral" / ".env"
    try:
        if env_path.exists():
            for raw in env_path.read_text(encoding="utf-8").splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                if key.strip() in ("SQUARE_ACCESS_TOKEN", "SQUARE_TOKEN"):
                    return val.strip().strip('"').strip("'") or None
    except Exception:  # noqa: BLE001
        pass
    return None


def resolve_token() -> str:
    """Return the Square access token, or raise a clear error if none is found.

    Thin public wrapper over the copied `_resolve_square_token()` so callers get
    a guaranteed `str` (never `None`) and an actionable message when auth is
    missing — the same env -> Keychain -> .env order.
    """
    token = _resolve_square_token()
    if not token:
        raise RuntimeError(
            "No Square access token found. Set SQUARE_ACCESS_TOKEN (or the legacy "
            "SQUARE_TOKEN) in the environment, the macOS Keychain "
            "(security add-generic-password -s SQUARE_ACCESS_TOKEN ...), or the "
            "workspace .env (~/workspace/richmondgeneral/.env)."
        )
    return token


# -----------------------------------------------------------------------------
# Network seam — the SOLE place an HTTP call is made. Tests monkeypatch THIS.
# -----------------------------------------------------------------------------

def _http(method: str, url: str, headers: dict, data: Optional[bytes]):
    """Perform one HTTP request and return ``(status:int, body:bytes)``.

    Uses stdlib ``urllib`` (NOT ``requests``) so it runs over the bare-shell
    bridge. An ``HTTPError`` is a real Square response (4xx/5xx) — its status and
    body are RETURNED, not raised, so higher layers can parse the error JSON.
    """
    req = urllib.request.Request(url, data=data, method=method)
    for key, value in headers.items():
        req.add_header(key, value)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def square_request(
    method: str,
    path: str,
    token: str,
    version: str = API_VERSION,
    body: Optional[dict] = None,
) -> tuple[int, dict]:
    """Make a Square API call and return ``(status_code, parsed_json_or_empty)``.

    Builds the auth/version headers, JSON-encodes ``body`` (only when present),
    dispatches through ``_http``, and parses the JSON response (an empty body —
    e.g. a bare DELETE 200 — parses to ``{}``). Mirrors the proven transport in
    rg-item-mark-sold/scripts/delete_payment_link.py. ``Content-Type`` is sent
    ONLY when there is a body, matching Square's expectations for bodyless GET /
    DELETE calls.
    """
    url = f"{BASE}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {
        "Authorization": f"Bearer {token}",
        "Square-Version": version,
    }
    if data is not None:
        headers["Content-Type"] = "application/json"
    status, raw = _http(method, url, headers, data)
    payload = raw.decode("utf-8") if raw else ""
    if not payload:
        return status, {}
    try:
        return status, json.loads(payload)
    except json.JSONDecodeError:
        return status, {"raw": payload}


# -----------------------------------------------------------------------------
# Payment-link helpers.
# -----------------------------------------------------------------------------

def build_payment_link_body(
    name: str,
    variation_id: str,
    price_cents: int,
    sku: str,
    redirect_url: str,
    ask_shipping,
    idempotency_key: str,
) -> dict:
    """Build the request body for creating a catalog-linked payment link.

    The line item references the CATALOG VARIATION by id
    (``catalog_object_id`` + ``item_type:"ITEM"``); Square derives the line name
    and price from that catalog object, so there is intentionally NO inline
    ``price_money`` (and ``name``/``price_cents`` are accepted for forward-compat
    but not embedded — keeping the price authoritative on the catalog avoids a
    drift between the link and the live item). ``reference_id`` and top-level
    ``description`` both carry the SKU so the link is discoverable / deletable
    later by SKU. ``ask_for_shipping_address`` is coerced to a real ``bool`` so it
    serializes as JSON ``true``/``false``.
    """
    return {
        "idempotency_key": idempotency_key,
        "order": {
            "location_id": LOCATION_ID,
            "line_items": [{
                "quantity": "1",
                "catalog_object_id": variation_id,
                "item_type": "ITEM",
            }],
            "reference_id": sku,
        },
        "checkout_options": {
            "redirect_url": redirect_url,
            "ask_for_shipping_address": bool(ask_shipping),
        },
        "description": sku,
    }


def create_payment_link(token: str, body: dict) -> dict:
    """POST a payment-link body and return the created ``payment_link`` object.

    Returns the parsed object (with ``id``, ``url``, ``order_id``). Raises
    ``RuntimeError`` carrying the Square error body on any non-2xx response —
    this creates a real, chargeable checkout URL, so a silent failure must not be
    mistaken for success.
    """
    status, parsed = square_request(
        "POST", "/v2/online-checkout/payment-links", token, body=body
    )
    if not (200 <= status < 300):
        raise RuntimeError(
            f"create_payment_link failed: Square returned {status}: "
            f"{json.dumps(parsed)}"
        )
    return parsed.get("payment_link", {})


def delete_payment_link(token: str, link_id: str) -> int:
    """DELETE a payment link by id; return the HTTP status.

    200 is the expected success. 404 means the link is already gone — the
    desired end state when killing a sold item's Buy Now link — so it is treated
    as OK and returned (not raised). Any other non-2xx raises ``RuntimeError``
    with the Square error body.
    """
    status, parsed = square_request(
        "DELETE", f"/v2/online-checkout/payment-links/{link_id}", token
    )
    if status == 404:
        return status
    if not (200 <= status < 300):
        raise RuntimeError(
            f"delete_payment_link failed: Square returned {status}: "
            f"{json.dumps(parsed)}"
        )
    return status


# -----------------------------------------------------------------------------
# QR — the one non-stdlib helper. Import is INSIDE so the module loads without it.
# -----------------------------------------------------------------------------

def gen_qr_png(url: str, out_path: str) -> None:
    """Render ``url`` as a QR code PNG at ``out_path``.

    Uses ``qrcode[pil]`` (the only non-stdlib dep) — imported lazily so importing
    this module never requires it; only callers that actually generate a QR need
    it on the path (invoke them under uv with ``--with "qrcode[pil]"``).
    """
    import qrcode  # noqa: PLC0415 — lazy by design (optional dep)

    qrcode.make(url).save(out_path)


# -----------------------------------------------------------------------------
# Shared money parsing — both tools take prices as human strings or numbers.
# -----------------------------------------------------------------------------

def dollars_to_cents(price) -> int:
    """Parse a price into integer cents.

    Accepts ``"65.00"``, ``"$65.00"``, ``"$1,234"``, ``65``, ``65.0`` and the
    like — strips ``$``, commas, and surrounding whitespace, then rounds to the
    nearest cent. Numeric inputs are taken as dollars. Rounding uses
    ``round(... )`` so e.g. ``65.5`` → ``6550`` and ``"$1,234.56"`` → ``123456``.
    """
    if isinstance(price, bool):  # guard: bool is an int subclass
        raise TypeError("price must be a number or string, not bool")
    if isinstance(price, (int, float)):
        dollars = float(price)
    else:
        cleaned = str(price).strip().replace("$", "").replace(",", "").strip()
        if not cleaned:
            raise ValueError(f"cannot parse price from {price!r}")
        dollars = float(cleaned)
    return int(round(dollars * 100))
