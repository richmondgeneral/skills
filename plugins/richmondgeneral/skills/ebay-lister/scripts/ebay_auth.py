#!/usr/bin/env python3
"""ebay_auth.py — eBay OAuth + credential resolution for the RG ebay-lister skill.

Self-contained (no cross-skill imports) so it runs standalone, from the orchestrator,
and over the osascript bridge's bare shell.

Credential resolution order (mirrors sku_authority / square-image-upload):
    env var  ->  macOS Keychain (`security find-generic-password`)  ->  workspace .env

Names resolved:
    EBAY_CLIENT_ID, EBAY_CLIENT_SECRET, EBAY_REFRESH_TOKEN, EBAY_RU_NAME,
    EBAY_ENV (production|sandbox, default production)

Commands:
    consent-url            Print the authorize URL the owner opens to grant consent.
    exchange --code CODE   One-time: swap an authorization code for a refresh token.
    check                  Mint an access token from the refresh token and report expiry.

The owner performs the browser sign-in/consent. This script never handles a password —
only the post-consent `code` and the resulting tokens.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path
from typing import Optional

import requests

# --- Scopes the skill needs (list/publish + read policies/locations) ---
SCOPES = [
    "https://api.ebay.com/oauth/api_scope/sell.inventory",
    "https://api.ebay.com/oauth/api_scope/sell.account",
]

# --- Host selection (production by default; sandbox for testing) ---
def _env_mode() -> str:
    return (resolve("EBAY_ENV") or "production").strip().lower()


def hosts() -> dict:
    if _env_mode() == "sandbox":
        return {
            "api": "https://api.sandbox.ebay.com",
            "auth": "https://auth.sandbox.ebay.com",
            "itm": "https://www.sandbox.ebay.com/itm/",
        }
    return {
        "api": "https://api.ebay.com",
        "auth": "https://auth.ebay.com",
        "itm": "https://www.ebay.com/itm/",
    }


# --- Credential resolution: env -> Keychain -> workspace .env ---
_ENV_FILE = Path.home() / "workspace" / "richmondgeneral" / ".env"


def resolve(name: str) -> Optional[str]:
    v = os.environ.get(name)
    if v:
        return v
    try:
        r = subprocess.run(
            ["security", "find-generic-password", "-a", os.environ.get("USER", ""),
             "-s", name, "-w"],
            capture_output=True, text=True,
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except Exception:  # noqa: BLE001
        pass
    try:
        if _ENV_FILE.exists():
            for raw in _ENV_FILE.read_text(encoding="utf-8").splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                if key.strip() == name:
                    return val.strip().strip('"').strip("'") or None
    except Exception:  # noqa: BLE001
        pass
    return None


def keychain_store(name: str, value: str) -> bool:
    """Store/replace a generic password in the login Keychain."""
    try:
        subprocess.run(
            ["security", "add-generic-password", "-U", "-a", os.environ.get("USER", ""),
             "-s", name, "-w", value],
            capture_output=True, text=True, check=True,
        )
        return True
    except Exception:  # noqa: BLE001
        return False


class EbayAuthError(RuntimeError):
    pass


def _basic_auth_header() -> str:
    cid = resolve("EBAY_CLIENT_ID")
    secret = resolve("EBAY_CLIENT_SECRET")
    if not cid or not secret:
        raise EbayAuthError(
            "Missing EBAY_CLIENT_ID / EBAY_CLIENT_SECRET (env, Keychain, or .env). "
            "See SETUP.md to register the eBay developer app and store the keys.")
    raw = f"{cid}:{secret}".encode("utf-8")
    return "Basic " + base64.b64encode(raw).decode("ascii")


def consent_url() -> str:
    ru = resolve("EBAY_RU_NAME")
    cid = resolve("EBAY_CLIENT_ID")
    if not cid or not ru:
        raise EbayAuthError("Missing EBAY_CLIENT_ID / EBAY_RU_NAME — see SETUP.md.")
    params = {
        "client_id": cid,
        "redirect_uri": ru,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "prompt": "login",
    }
    return f"{hosts()['auth']}/oauth2/authorize?" + urllib.parse.urlencode(params)


def exchange_code(code: str) -> dict:
    """Authorization-code grant -> {access_token, refresh_token, ...}."""
    ru = resolve("EBAY_RU_NAME")
    if not ru:
        raise EbayAuthError("Missing EBAY_RU_NAME — see SETUP.md.")
    r = requests.post(
        f"{hosts()['api']}/identity/v1/oauth2/token",
        headers={"Authorization": _basic_auth_header(),
                 "Content-Type": "application/x-www-form-urlencoded"},
        data={"grant_type": "authorization_code",
              "code": urllib.parse.unquote(code),
              "redirect_uri": ru},
        timeout=30,
    )
    if r.status_code != 200:
        raise EbayAuthError(f"code exchange failed ({r.status_code}): {r.text}")
    return r.json()


def get_access_token() -> str:
    """Mint a short-lived access token from the stored refresh token."""
    refresh = resolve("EBAY_REFRESH_TOKEN")
    if not refresh:
        raise EbayAuthError(
            "No EBAY_REFRESH_TOKEN found. Run the one-time consent: "
            "`ebay_auth.py consent-url`, approve in the browser, then "
            "`ebay_auth.py exchange --code <CODE>`. See SETUP.md.")
    r = requests.post(
        f"{hosts()['api']}/identity/v1/oauth2/token",
        headers={"Authorization": _basic_auth_header(),
                 "Content-Type": "application/x-www-form-urlencoded"},
        data={"grant_type": "refresh_token",
              "refresh_token": refresh,
              "scope": " ".join(SCOPES)},
        timeout=30,
    )
    if r.status_code != 200:
        raise EbayAuthError(f"token refresh failed ({r.status_code}): {r.text}")
    return r.json()["access_token"]


def _main(argv=None) -> int:
    p = argparse.ArgumentParser(description="eBay OAuth helper for ebay-lister.")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("consent-url", help="Print the authorize URL to grant consent.")
    ex = sub.add_parser("exchange", help="Swap an authorization code for a refresh token.")
    ex.add_argument("--code", required=True, help="The ?code=... value from the redirect.")
    ex.add_argument("--no-store", action="store_true",
                    help="Print the refresh token instead of storing it in Keychain.")
    sub.add_parser("check", help="Mint an access token and report success.")
    args = p.parse_args(argv)

    try:
        if args.cmd == "consent-url":
            print(consent_url())
            return 0
        if args.cmd == "exchange":
            tok = exchange_code(args.code)
            refresh = tok.get("refresh_token")
            if not refresh:
                print(json.dumps(tok, indent=2)); return 1
            if args.no_store:
                print(refresh)
            else:
                ok = keychain_store("EBAY_REFRESH_TOKEN", refresh)
                print(json.dumps({
                    "stored_in_keychain": ok,
                    "refresh_token_expires_in": tok.get("refresh_token_expires_in"),
                    "note": "EBAY_REFRESH_TOKEN saved." if ok else
                            "Could not store in Keychain — set EBAY_REFRESH_TOKEN manually.",
                }, indent=2))
            return 0
        if args.cmd == "check":
            t = get_access_token()
            print(json.dumps({"ok": True, "access_token_prefix": t[:12] + "…",
                              "env": _env_mode()}, indent=2))
            return 0
    except EbayAuthError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(_main())
