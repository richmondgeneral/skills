#!/usr/bin/env python3
"""ebay_lister.py — create + publish eBay listings from items/RG-XXXX/label.json
via eBay's Sell **Inventory API** (no browser, batchable).

Pipeline:  createOrReplaceInventoryItem -> createOffer -> publishOffer -> write back.

Commands:
    policies                       List account business policies (capture IDs for setup).
    list --sku RG-XXXX --dry-run   Build + print the exact payloads, no API call (no creds needed).
    list --sku RG-XXXX --publish   Create inventory item + offer, publish, write item_id/url back.

Config resolved via ebay_auth.resolve() (env -> Keychain -> .env):
    EBAY_FULFILLMENT_POLICY_ID, EBAY_PAYMENT_POLICY_ID, EBAY_RETURN_POLICY_ID,
    EBAY_LOCATION_KEY, EBAY_MARKETPLACE (default EBAY_US)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

import requests

import ebay_auth as auth

ITEMS_DIR = Path.home() / "workspace" / "richmondgeneral" / "items"
PAGES_BASE = "https://richmondgeneral.github.io/items"

# type/category -> eBay US leaf category id
CATEGORY_BY_TYPE = {
    "books & paper": "261186",   # Books > Books
    "books": "261186",
}

CONDITION_MAP = {
    "new": "NEW",
    "like new": "LIKE_NEW",
    "very good": "USED_VERY_GOOD",
    "good": "USED_GOOD",
    "acceptable": "USED_ACCEPTABLE",
    "fair": "USED_ACCEPTABLE",
}


def _marketplace() -> str:
    return auth.resolve("EBAY_MARKETPLACE") or "EBAY_US"


def _api_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Content-Language": "en-US",
        "Accept": "application/json",
        "X-EBAY-C-MARKETPLACE-ID": _marketplace(),
    }


def _map_condition(text: str) -> str:
    t = (text or "").lower()
    for key, enum in CONDITION_MAP.items():
        if key in t:
            return enum
    return "USED_GOOD"


def _map_category(label: dict, override: Optional[str]) -> Optional[str]:
    if override:
        return override
    cats = []
    sq = label.get("channels", {}).get("square", {})
    cats += [str(c).lower() for c in sq.get("categories", [])]
    cats.append((label.get("product_name") or "").lower())
    blob = " ".join(cats)
    for key, cid in CATEGORY_BY_TYPE.items():
        if key in blob:
            return cid
    return None


def _image_urls(sku: str) -> list:
    d = ITEMS_DIR / sku
    urls = []
    if (d / "hero.png").exists():
        urls.append(f"{PAGES_BASE}/{sku}/hero.png")
    if d.exists():
        for p in sorted(d.glob("detail-*.png")):
            urls.append(f"{PAGES_BASE}/{sku}/{p.name}")
    return urls


def _aspects(label: dict, extra: list) -> dict:
    """Best-effort aspects: split `attributes` on bullets into Features, plus overrides."""
    aspects: dict = {}
    attrs = label.get("attributes") or ""
    feats = [s.strip() for s in attrs.replace("|", "•").split("•") if s.strip()]
    if feats:
        aspects["Features"] = feats
    aspects.setdefault("Language", ["English"])
    for kv in extra or []:
        if "=" in kv:
            k, _, v = kv.partition("=")
            aspects[k.strip()] = [s.strip() for s in v.split(",") if s.strip()]
    return aspects


def build_payloads(sku: str, label: dict, category: Optional[str],
                   extra_aspects: list, title_override: Optional[str]) -> dict:
    title = (title_override or label.get("product_name") or sku)[:80]
    desc = label.get("condition_notes") or label.get("product_name") or ""
    price = str(label.get("price") or "").strip()
    cat = _map_category(label, category)
    images = _image_urls(sku)

    inventory_item = {
        "availability": {"shipToLocationAvailability": {"quantity": 1}},
        "condition": _map_condition(label.get("condition", "")),
        "product": {
            "title": title,
            "description": desc,
            "aspects": _aspects(label, extra_aspects),
            "imageUrls": images,
        },
    }
    offer = {
        "sku": sku,
        "marketplaceId": _marketplace(),
        "format": "FIXED_PRICE",
        "availableQuantity": 1,
        "categoryId": cat,
        "listingDescription": desc,
        "listingPolicies": {
            "fulfillmentPolicyId": auth.resolve("EBAY_FULFILLMENT_POLICY_ID"),
            "paymentPolicyId": auth.resolve("EBAY_PAYMENT_POLICY_ID"),
            "returnPolicyId": auth.resolve("EBAY_RETURN_POLICY_ID"),
            "bestOfferTerms": {"bestOfferEnabled": True},
        },
        "pricingSummary": {"price": {"value": price, "currency": "USD"}},
        "merchantLocationKey": auth.resolve("EBAY_LOCATION_KEY"),
    }
    return {"inventory_item": inventory_item, "offer": offer}


def _missing_config(offer: dict) -> list:
    miss = []
    lp = offer.get("listingPolicies", {})
    for k in ("fulfillmentPolicyId", "paymentPolicyId", "returnPolicyId"):
        if not lp.get(k):
            miss.append(k)
    if not offer.get("merchantLocationKey"):
        miss.append("merchantLocationKey")
    if not offer.get("categoryId"):
        miss.append("categoryId")
    if not (offer.get("pricingSummary", {}).get("price", {}).get("value")):
        miss.append("price")
    return miss


def cmd_policies() -> int:
    token = auth.get_access_token()
    out = {}
    base = f"{auth.hosts()['api']}/sell/account/v1"
    mk = _marketplace()
    for kind in ("fulfillment_policy", "payment_policy", "return_policy"):
        r = requests.get(f"{base}/{kind}?marketplace_id={mk}",
                         headers=_api_headers(token), timeout=30)
        out[kind] = r.json() if r.status_code == 200 else {"error": r.status_code, "body": r.text}
    loc = requests.get(f"{auth.hosts()['api']}/sell/inventory/v1/location",
                       headers=_api_headers(token), timeout=30)
    out["locations"] = loc.json() if loc.status_code == 200 else {"error": loc.status_code}
    print(json.dumps(out, indent=2))
    return 0


def _load_label(sku: str) -> tuple[dict, Path]:
    path = ITEMS_DIR / sku / "label.json"
    if not path.exists():
        raise SystemExit(f"ERROR: {path} not found.")
    return json.loads(path.read_text(encoding="utf-8")), path


def cmd_list(sku: str, dry_run: bool, publish: bool, category: Optional[str],
             extra_aspects: list, title: Optional[str]) -> int:
    label, label_path = _load_label(sku)
    payloads = build_payloads(sku, label, category, extra_aspects, title)
    missing = _missing_config(payloads["offer"])

    if dry_run:
        print(json.dumps({"sku": sku, "dry_run": True,
                          "missing_config": missing, **payloads}, indent=2))
        if missing:
            print(f"\nNote: {len(missing)} config value(s) unresolved: {missing}. "
                  "Run `ebay_lister.py policies` and SETUP.md to fill them.", file=sys.stderr)
        return 0

    if missing:
        raise SystemExit(f"ERROR: cannot list — missing config: {missing}. See SETUP.md.")

    token = auth.get_access_token()
    api = auth.hosts()["api"]

    # 1) createOrReplaceInventoryItem (PUT, idempotent)
    r = requests.put(f"{api}/sell/inventory/v1/inventory_item/{sku}",
                     headers=_api_headers(token),
                     data=json.dumps(payloads["inventory_item"]), timeout=45)
    if r.status_code not in (200, 201, 204):
        raise SystemExit(f"ERROR inventory_item ({r.status_code}): {r.text}")

    # 2) createOffer
    r = requests.post(f"{api}/sell/inventory/v1/offer",
                      headers=_api_headers(token),
                      data=json.dumps(payloads["offer"]), timeout=45)
    if r.status_code == 200 or r.status_code == 201:
        offer_id = r.json().get("offerId")
    elif r.status_code == 400 and "25002" in r.text:  # offer already exists for SKU
        # look up existing offer id
        g = requests.get(f"{api}/sell/inventory/v1/offer?sku={sku}&marketplace_id={_marketplace()}",
                         headers=_api_headers(token), timeout=30)
        offer_id = (g.json().get("offers", [{}])[0] or {}).get("offerId")
        if not offer_id:
            raise SystemExit(f"ERROR offer exists but could not resolve offerId: {r.text}")
    else:
        raise SystemExit(f"ERROR createOffer ({r.status_code}): {r.text}")

    if not publish:
        print(json.dumps({"sku": sku, "offer_id": offer_id, "published": False,
                          "note": "Offer created. Re-run with --publish to go live."}, indent=2))
        return 0

    # 3) publishOffer
    r = requests.post(f"{api}/sell/inventory/v1/offer/{offer_id}/publish",
                      headers=_api_headers(token), timeout=45)
    if r.status_code not in (200, 201):
        raise SystemExit(f"ERROR publishOffer ({r.status_code}): {r.text}")
    listing_id = r.json().get("listingId")
    url = f"{auth.hosts()['itm']}{listing_id}"

    # write back into label.json
    label.setdefault("channels", {})["ebay"] = {
        "status": "listed",
        "item_id": listing_id,
        "url": url,
        "offer_id": offer_id,
        "listed_price": str(label.get("price")),
        "format": "Buy It Now + Best Offer",
        "note": f"Listed via Sell Inventory API ({auth._env_mode()}).",
    }
    label_path.write_text(json.dumps(label, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({"sku": sku, "offer_id": offer_id, "listing_id": listing_id,
                      "url": url, "label_updated": True}, indent=2))
    return 0


def _main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Create/publish eBay listings from label.json.")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("policies", help="List account business policies + locations.")
    lst = sub.add_parser("list", help="Build/create/publish a listing for one SKU.")
    lst.add_argument("--sku", required=True, help="RG-XXXX")
    lst.add_argument("--dry-run", action="store_true", help="Print payloads, no API call.")
    lst.add_argument("--publish", action="store_true", help="Publish the offer (go live).")
    lst.add_argument("--category", help="Override eBay category id.")
    lst.add_argument("--aspect", action="append", default=[],
                     help="Extra aspect K=V1,V2 (repeatable).")
    lst.add_argument("--title", help="Override the listing title (<=80 chars).")
    args = p.parse_args(argv)

    try:
        if args.cmd == "policies":
            return cmd_policies()
        if args.cmd == "list":
            return cmd_list(args.sku, args.dry_run, args.publish,
                            args.category, args.aspect, args.title)
    except auth.EbayAuthError as e:
        print(f"ERROR (auth): {e}", file=sys.stderr)
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(_main())
