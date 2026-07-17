---
name: ebay-lister
description: >
  Build, create, publish, and update Richmond General eBay listings through eBay's Sell Inventory API.
  Use for `--dry-run` payload validation now, and for programmatic eBay create/update work only after
  developer keys are issued and `EBAY_API_LIVE_ENABLED=1` is deliberately configured. Until then, route
  all live eBay create/revise/manage work through `ebay-browser`. Reads
  items/RG-XXXX/label.json (price, condition, attributes, photos from the live GitHub
  Pages URLs), upserts the inventory item and offer, publishes unpublished offers, then
  writes the eBay item_id + URL back into label.json. Use whenever the task is to list an
  item through the eBay API, publish an API listing pack, or revise an API-managed listing.
  Triggers on "eBay API", "publish with eBay API", and "update API-managed eBay listing".
  Requires one-time owner OAuth (see SETUP.md); the skill never handles a password.
metadata:
  version: "0.3"
  author: scottybe
  updated: "2026-07-15"
  status: "ON HOLD — API path awaiting eBay developer keys; live writes are code-gated by EBAY_API_LIVE_ENABLED. Use ebay-browser for live work; use this skill with --dry-run only."
  changelog: "0.3 (2026-07-15): added an explicit live-write gate, required-field validation, safe SKU parsing, correct condition mapping, and idempotent offer updates."
---

# ebay-lister — list on eBay via the Sell API

> ⏸️ **ON HOLD — API path not active yet (eBay is NOT blocked).** eBay writes — create AND revise —
> currently go through the **browser** via the **`ebay-browser`** skill, which prefers the native
> authenticated Chrome surface in Claude, Codex, or Gemini Spark and uses Playwright only as fallback.
> This API path is waiting on eBay developer keys (App ID /
> Cert ID / OAuth — not yet issued), so only `ebay_lister.py list --sku … --dry-run` is safe here (it
> builds payloads locally, makes no API call). Live mutations are also blocked in code unless
> `EBAY_API_LIVE_ENABLED=1`. When the keys arrive, follow SETUP.md and activate that gate only after
> a sandbox smoke test.

Replaces the flaky Chrome listing flow (which freezes at `document_idle`) with eBay's
REST Sell Inventory API. Source of truth for each listing is `items/RG-XXXX/label.json`.

## Prereqs (one time — see SETUP.md)
1. eBay developer app keys: `EBAY_CLIENT_ID`, `EBAY_CLIENT_SECRET`, `EBAY_RU_NAME`.
2. One-time owner OAuth consent for the `richmondgeneral` seller account → `EBAY_REFRESH_TOKEN`.
3. Business policy + location IDs: `EBAY_FULFILLMENT_POLICY_ID`, `EBAY_PAYMENT_POLICY_ID`,
   `EBAY_RETURN_POLICY_ID`, `EBAY_LOCATION_KEY` (capture via `ebay_lister.py policies`).
4. Explicit live-write opt-in: `EBAY_API_LIVE_ENABLED=1`, set only after setup and sandbox validation.
All resolved env → macOS Keychain → workspace `.env` (same as the other RG skills).

## Usage (uv)
```bash
# One-time auth
uv run --project ${CLAUDE_PLUGIN_ROOT} python ${CLAUDE_PLUGIN_ROOT}/skills/ebay-lister/scripts/ebay_auth.py consent-url
uv run --project ${CLAUDE_PLUGIN_ROOT} python ${CLAUDE_PLUGIN_ROOT}/skills/ebay-lister/scripts/ebay_auth.py exchange --code <CODE_FROM_REDIRECT>
uv run --project ${CLAUDE_PLUGIN_ROOT} python ${CLAUDE_PLUGIN_ROOT}/skills/ebay-lister/scripts/ebay_auth.py check

# Capture business-policy + location IDs (store them in Keychain per SETUP.md)
uv run --project ${CLAUDE_PLUGIN_ROOT} python ${CLAUDE_PLUGIN_ROOT}/skills/ebay-lister/scripts/ebay_lister.py policies

# Build payloads WITHOUT calling eBay (works with no creds — safe to test)
uv run --project ${CLAUDE_PLUGIN_ROOT} python ${CLAUDE_PLUGIN_ROOT}/skills/ebay-lister/scripts/ebay_lister.py list --sku RG-0032 --dry-run

# Go live after setup + explicit gate (create/update, publish if needed, write back)
uv run --project ${CLAUDE_PLUGIN_ROOT} python ${CLAUDE_PLUGIN_ROOT}/skills/ebay-lister/scripts/ebay_lister.py list --sku RG-0032 --publish
```

From **Cowork** run these over the mac-bridge:
`rg-skill.sh ebay-lister ebay_lister.py list --sku RG-0032 --dry-run`

## After publishing
`label.json → channels.ebay` is set to `{status:"listed", item_id, url, offer_id}` by the
script. Commit + push the `items` repo (stage explicit paths). Optionally regenerate
`qr-buy.png` to point at the eBay URL if eBay is the primary buy channel.

## Notes / limits (v0.1)
- Fixed-price + Best Offer only; no auctions or variations yet.
- Inventory API listings cannot be revised in Seller Hub. Keep API-created listings on this API path;
  use `ebay-browser` only for browser-created listings.
- Images are referenced from the public GitHub Pages URLs — push the item page first.
- Aspects are best-effort from `attributes`; pass `--aspect "Author=…"` to add required ones.
  If publish returns missing-required-aspect errors, add them and re-run (PUT/offer are idempotent).
- Dual-copy skill (source + plugin cache) — reinstall the plugin to sync the cache for code-mode.
