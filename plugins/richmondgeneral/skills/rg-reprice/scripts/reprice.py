#!/usr/bin/env python3
"""rg-reprice — one-command price-change cascade across every surface (Phase D).

Given a SKU and a new price, this re-prices a *single, already-listed* Richmond
General item everywhere it lives, in one ordered pass:

  (a) Square catalog VARIATION price — the safe fetch-patch-upsert (GET the
      variation, patch only ``price_money``, re-upsert with its fetched version,
      preserving sku/pricing_type).
  (b) Square PAYMENT LINK — delete the old catalog-linked link, mint a fresh one
      at the new price (a payment link's amount is fixed at creation, so a price
      change requires a recreate, never an edit).
  (c) the BUY QR — re-render ``qr-buy.png`` for the new checkout URL.
  (d) ``label.json`` — price / price_status / channels.square.* / a dated
      ``estimates.refinement_log`` "Repriced" entry.
  (e) the GitHub Pages ITEM PAGE — rebuild so the printed/visible price + buy
      link refresh.
  (f) the GALLERY CARD — rebuild the landing-grid card's price.
  (g) a reminder to update the private pricing report.

Remote (Square) FIRST, then local — so the page/gallery builders in steps (e)/(f)
read the just-written new price and new buy link out of label.json.

Runtime deps: Python 3 **stdlib only**, plus the cross-skill ``square_client``
(the shared rg-square-list transport). We do NOT reimplement token resolution,
the urllib transport, the payment-link create/delete, or the QR — all reused.

Network + QR + subprocess go through seams the test suite monkeypatches
(``sc.square_request`` / ``sc.create_payment_link`` / ``sc.delete_payment_link``
/ ``sc.gen_qr_png`` and ``reprice.subprocess.run``), so nothing ever hits Square,
writes a PNG, or spawns a builder in tests.

This is NOT for new listings (use rg-square-list / rg-full-auto) nor for sold
items (use rg-item-mark-sold). It assumes the item is already live on Square
(``channels.square.object_id`` + ``variation_id`` present).
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

# --- Cross-skill import of the shared Square client -------------------------
# square_client lives in the sibling rg-square-list skill. Add its scripts/ dir
# to sys.path relative to THIS file (so it works run directly, from an
# orchestrator, or over the osascript bridge), then import the module. We hold a
# MODULE reference (``sc``) and call through it — ``sc.square_request(...)`` — so
# the test suite's ``monkeypatch.setattr(sc, "square_request", ...)`` is seen
# here. dollars_to_cents / build_payment_link_body are pure and imported as
# names (the tests never patch them).
_SQUARE_LIST_SCRIPTS = (
    Path(__file__).resolve().parent.parent.parent
    / "rg-square-list" / "scripts"
)
if str(_SQUARE_LIST_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SQUARE_LIST_SCRIPTS))

import square_client as sc  # noqa: E402
from square_client import (  # noqa: E402
    build_payment_link_body,
    dollars_to_cents,
)

# The page/gallery builders (steps e/f) run with cwd = the workspace root. We do
# NOT derive that from this file's path: code-mode runs a dual-copy of this skill
# out of ~/.claude/plugins/cache/.../rg-reprice/scripts/reprice.py, where a fixed
# ``parents[6]`` resolves to ~/.claude/plugins/cache — which has NO items/ — so
# the page/gallery subprocesses would fail (exit 2) and, being check=False, fail
# SILENTLY, leaving the public page + gallery on the OLD price after a successful
# Square reprice. Instead, locate the workspace by its items/ build scripts,
# searching cwd (always the workspace when reprice is run) then this file's
# ancestors as a fallback. Resolved lazily (only where the subprocess cwd is
# needed) so importing the module never raises.


def _find_repo_root():
    """Locate the workspace root by the items/ build scripts, searching cwd then this file's ancestors."""
    marker = Path("items") / "scripts" / "build_item_page.py"
    for base in (Path.cwd(), Path(__file__).resolve()):
        for d in (base, *base.parents):
            if (d / marker).exists():
                return d
    raise RuntimeError(
        "rg-reprice: cannot locate the workspace root (items/scripts/build_item_page.py "
        "not found above the current directory or this script). Run rg-reprice from the "
        "richmondgeneral workspace."
    )

# Public item-page base — the payment-link redirect (and the page URL) target.
ITEM_PAGE_BASE = "https://richmondgeneral.github.io/items"


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------

def _local_pickup_only(label: dict) -> bool:
    """True when the item is pickup-only (so the new link skips shipping).

    Mirrors rg-square-list's ``_local_pickup_only``: top-level
    ``fulfillment == "local_pickup_only"`` OR ``shipping.local_pickup_only``.
    """
    if label.get("fulfillment") == "local_pickup_only":
        return True
    shipping = label.get("shipping") or {}
    return bool(shipping.get("local_pickup_only"))


def _write_label(label_path: Path, label: dict) -> None:
    """Write ``label`` as pretty JSON with a trailing newline.

    Same formatting contract as rg-square-list's writer (2-space indent,
    ``ensure_ascii=False``, trailing ``\\n``) so reprice's write-back is
    byte-compatible with the rest of the toolchain.
    """
    label_path.write_text(
        json.dumps(label, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _get_variation(token: str, variation_id: str) -> dict:
    """GET a catalog VARIATION object and return its parsed ``object`` dict.

    Raises on any non-2xx — a price change must not proceed on a failed fetch
    (we'd otherwise upsert with a stale/blank version and clobber the variation).
    """
    status, parsed = sc.square_request(
        "GET", f"/v2/catalog/object/{variation_id}", token
    )
    if not (200 <= status < 300):
        raise RuntimeError(
            f"GET catalog variation {variation_id} failed: {status}: "
            f"{json.dumps(parsed)}"
        )
    obj = parsed.get("object") or {}
    if not obj.get("version") and obj.get("version") != 0:
        raise RuntimeError(
            f"No version on fetched variation {variation_id}: version missing"
        )
    return obj


def _update_variation_price(token: str, variation_id: str, new_cents: int) -> None:
    """Safe fetch-patch-upsert of the variation price.

    GET the variation, set ONLY ``item_variation_data.price_money`` to the new
    amount (preserving sku, pricing_type, item_id, etc.), then POST it back to
    ``catalog/batch-upsert`` carrying the FETCHED version. Raises on a non-2xx
    upsert (a money-path step must never fail silently).
    """
    obj = _get_variation(token, variation_id)
    vdata = obj.setdefault("item_variation_data", {})
    vdata["price_money"] = {"amount": new_cents, "currency": "USD"}

    body = {
        "idempotency_key": str(uuid.uuid4()),
        "batches": [{"objects": [obj]}],
    }
    status, parsed = sc.square_request(
        "POST", "/v2/catalog/batch-upsert", token, body=body
    )
    if not (200 <= status < 300):
        raise RuntimeError(
            f"batch-upsert price update of {variation_id} failed: {status}: "
            f"{json.dumps(parsed)}"
        )


def _recreate_payment_link(token: str, sku: str, product_name: str,
                           variation_id: str, new_cents: int,
                           old_link_id, ask_shipping: bool) -> dict:
    """Delete the old payment link (if any) then create a fresh one at the new
    price. Returns the new ``payment_link`` object (``id`` / ``url`` /
    ``order_id``).

    Delete BEFORE create so there is never a window with two chargeable links
    for the same item, and we never blind-create a second live link beside a
    stale one. The amount is taken from the catalog variation (no inline
    ``price_money`` — keeps the link authoritative on the catalog), which we just
    set to ``new_cents``.
    """
    if old_link_id:
        sc.delete_payment_link(token, old_link_id)

    body = build_payment_link_body(
        name=product_name,
        variation_id=variation_id,
        price_cents=new_cents,
        sku=sku,
        redirect_url=f"{ITEM_PAGE_BASE}/{sku}/",
        ask_shipping=ask_shipping,
        idempotency_key=str(uuid.uuid4()),
    )
    return sc.create_payment_link(token, body)


def _build_plan(sku, item_dir, old_price, new_price_str, old_link_id,
                object_id, variation_id, local_pickup_only):
    """Assemble the dry-run / summary plan dict."""
    return {
        "sku": sku,
        "item_dir": str(item_dir),
        "old_price": old_price,
        "new_price": new_price_str,
        "object_id": object_id,
        "variation_id": variation_id,
        "old_payment_link_id": old_link_id,
        "local_pickup_only": local_pickup_only,
        "redirect_url": f"{ITEM_PAGE_BASE}/{sku}/",
        "steps": [
            "(a) Square variation price → fetch-patch-upsert",
            "(b) payment link → delete old + create new at new price",
            "(c) qr-buy.png → regenerate for new buy link",
            "(d) label.json → price/price_status/channels.square/refinement_log",
            "(e) item page → rebuild",
            "(f) gallery card → rebuild",
            "(g) reminder → update the pricing report",
        ],
    }


# ---------------------------------------------------------------------------
# Orchestrator.
# ---------------------------------------------------------------------------

def reprice(sku: str, new_price, dry_run: bool = False, date=None,
            items_root=None) -> dict:
    """Cascade a price change for ``sku`` to ``new_price`` across every surface.

    Order: Square (variation price, then payment-link recreate, then QR) →
    label.json → item page → gallery card → pricing-report reminder. Remote
    first so the local builders pick up the new price + buy link.

    ``date`` defaults to today (ISO). ``items_root`` overrides the items/ parent
    (default ``<workspace-root>/items``, resolved via ``_find_repo_root``) — used
    by tests to point at a tmp dir.

    With ``dry_run=True`` it builds + prints the plan and returns it WITHOUT
    resolving a token, calling Square, writing files, generating a QR, or
    spawning a subprocess.
    """
    if date is None:
        date = datetime.date.today().isoformat()

    # Resolve the workspace root lazily, anchored to where reprice is RUN (cwd),
    # not to this file — so the cache dual-copy still finds the real items/.
    # Only needed when items_root isn't supplied (tests pass it) or for the
    # page/gallery subprocess cwd; both real-run uses are below.
    repo_root = None
    if items_root:
        root = Path(items_root)
    else:
        repo_root = _find_repo_root()
        root = repo_root / "items"
    item_dir = root / sku
    label_path = item_dir / "label.json"
    label = json.loads(label_path.read_text(encoding="utf-8"))

    new_cents = dollars_to_cents(new_price)
    new_price_str = f"{new_cents / 100:.2f}"

    product_name = label.get("product_name") or sku
    channels = label.get("channels") or {}
    square = channels.get("square") or {}
    object_id = square.get("object_id")
    variation_id = square.get("variation_id")
    old_link_id = square.get("payment_link_id")
    old_price = square.get("price") or label.get("price")
    local_pickup_only = _local_pickup_only(label)

    plan = _build_plan(sku, item_dir, old_price, new_price_str, old_link_id,
                       object_id, variation_id, local_pickup_only)

    # --- dry run: plan only, ZERO side effects -------------------------------
    if dry_run:
        plan["dry_run"] = True
        print(f"[dry-run] {sku}: would reprice ${old_price} -> ${new_price_str}")
        for step in plan["steps"]:
            print(f"  {step}")
        print(f"  redirect: {plan['redirect_url']}  "
              f"(pickup-only: {local_pickup_only})")
        return plan

    if not variation_id:
        raise RuntimeError(
            f"{sku}: channels.square.variation_id is missing — cannot reprice an "
            "item that is not listed on Square (use rg-square-list first)."
        )

    token = sc.resolve_token()

    # --- (a) Square variation price ------------------------------------------
    _update_variation_price(token, variation_id, new_cents)

    # --- (b) Payment link: delete old → create new at the new price ----------
    link = _recreate_payment_link(
        token, sku, product_name, variation_id, new_cents, old_link_id,
        ask_shipping=(not local_pickup_only),
    )
    new_buy_link = link.get("url")
    new_link_id = link.get("id")
    new_order_id = link.get("order_id")

    # --- (c) QR: re-render qr-buy.png for the new buy link -------------------
    if new_buy_link:
        try:
            sc.gen_qr_png(new_buy_link, os.path.join(str(item_dir), "qr-buy.png"))
        except ImportError:
            print(
                "  [warn] qr-buy.png NOT regenerated: the `qrcode` package is not "
                "installed (re-run under uv with --with \"qrcode[pil]\")."
            )

    # --- (d) label.json: price / status / channels.square / refinement_log ---
    label["price"] = new_price_str
    label["price_status"] = (
        f"final — ${new_price_str} (repriced from ${old_price} on {date})"
    )
    square.update({
        "price": new_price_str,
        "buy_link": new_buy_link,
        "payment_link_id": new_link_id,
        "order_id": new_order_id,
    })
    channels["square"] = square
    label["channels"] = channels

    estimates = label.get("estimates")
    if not isinstance(estimates, dict):
        estimates = {}
        label["estimates"] = estimates
    log = estimates.get("refinement_log")
    if not isinstance(log, list):
        log = []
        estimates["refinement_log"] = log
    log.append({
        "date": date,
        "note": f"Repriced ${old_price} -> ${new_price_str}.",
    })

    _write_label(label_path, label)
    print(f"{sku}: repriced ${old_price} -> ${new_price_str}")
    print(f"  buy link:     {new_buy_link}")
    print(f"  payment link: {new_link_id}")

    # The page/gallery builders run with cwd = the workspace root, resolved from
    # the run location (cache-safe). Reuse the value from above if we computed it.
    if repo_root is None:
        repo_root = _find_repo_root()

    # --- (e) Item page rebuild -----------------------------------------------
    # check=False + don't hard-fail: build_item_page.py SKIPS protected/living/
    # sold pages (returns a non-write result), which is expected, not an error.
    page_res = subprocess.run(
        ["uv", "run", "python", "items/scripts/build_item_page.py", sku],
        cwd=str(repo_root), check=False,
    )
    print(f"  item page:    build_item_page.py exit {page_res.returncode}")
    if page_res.returncode != 0:
        print(
            f"⚠ rg-reprice: build_item_page.py exited {page_res.returncode} for "
            f"{sku} — if this item is a protected/living-test/sold page this is "
            f"expected; OTHERWISE the public page may now show a STALE price. "
            f"Verify items/{sku}/index.html.",
            file=sys.stderr,
        )

    # --- (f) Gallery card rebuild --------------------------------------------
    gallery_res = subprocess.run(
        ["uv", "run", "python", "items/scripts/build_gallery.py",
         "--update-card", sku],
        cwd=str(repo_root), check=False,
    )
    print(f"  gallery card: build_gallery.py exit {gallery_res.returncode}")
    if gallery_res.returncode != 0:
        print(
            f"⚠ rg-reprice: build_gallery.py exited {gallery_res.returncode} for "
            f"{sku} — if this item is a protected/living-test/sold page this is "
            f"expected; OTHERWISE the gallery card may now show a STALE price. "
            f"Verify the landing-grid card for {sku}.",
            file=sys.stderr,
        )

    # --- (g) Pricing-report reminder -----------------------------------------
    print(f"⚠ Update ops/pricing/{sku}-pricing.md with the new comp basis "
          f"+ date.")

    plan.update({
        "dry_run": False,
        "buy_link": new_buy_link,
        "payment_link_id": new_link_id,
        "order_id": new_order_id,
        "page_exit": page_res.returncode,
        "gallery_exit": gallery_res.returncode,
    })
    return plan


# ---------------------------------------------------------------------------
# CLI.
# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Reprice a listed Richmond General item across every surface: Square "
            "variation price, payment-link recreate, qr-buy, label.json, item "
            "page, and gallery card. Preview with --dry-run first."
        )
    )
    parser.add_argument("sku", help="the item SKU, e.g. RG-0055")
    parser.add_argument("price", help="the new price, e.g. 65 or 65.00 or $65")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="plan only — zero network calls, no writes, no subprocesses.",
    )
    parser.add_argument(
        "--date", default=datetime.date.today().isoformat(),
        help="date stamp for price_status / refinement_log (default: today).",
    )
    args = parser.parse_args(argv)

    plan = reprice(args.sku, args.price, dry_run=args.dry_run, date=args.date)

    # Surface a non-zero builder exit prominently (the cascade itself already
    # warned to stderr per-step). A protected/living-test/sold page is a
    # deliberate skip, so we don't crash — but a failed builder means the public
    # page/gallery may be on a STALE price, so we exit non-zero to flag it.
    if not args.dry_run:
        page_rc = plan.get("page_exit") or 0
        gallery_rc = plan.get("gallery_exit") or 0
        if page_rc != 0 or gallery_rc != 0:
            print(
                f"⚠ rg-reprice: a page/gallery builder failed for {args.sku} "
                f"(item-page exit {page_rc}, gallery exit {gallery_rc}). If "
                f"{args.sku} is a protected/living-test/sold page this is "
                f"expected; otherwise its public price may be STALE — verify and "
                f"re-run rg-reprice (it's idempotent).",
                file=sys.stderr,
            )
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
