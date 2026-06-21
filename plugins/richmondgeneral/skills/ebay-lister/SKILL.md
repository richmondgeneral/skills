---
name: ebay-lister
description: >
  eBay is NOT blocked — eBay writes (create AND revise) currently route through the BROWSER via the
  `ebay-chrome` skill, the sanctioned path until further notice. THIS skill is the API path and is ON HOLD
  pending eBay developer API keys (not yet issued); do NOT invoke it for live listing yet (`--dry-run`
  only) — use `ebay-chrome` for real eBay work. When keys arrive: Create and publish Richmond General eBay listings programmatically via eBay's official
  Sell **Inventory API** — no browser, no document_idle hang, batchable. Reads
  items/RG-XXXX/label.json (price, condition, attributes, photos from the live GitHub
  Pages URLs) and runs createOrReplaceInventoryItem -> createOffer -> publishOffer, then
  writes the eBay item_id + URL back into label.json. Use whenever the task is to list an
  item on eBay, publish a prepared eBay listing pack, or fix the recurring eBay
  browser-automation freeze. Triggers on "list on eBay", "publish the eBay listing",
  "push RG-XXXX to eBay", "eBay API". Requires a one-time owner OAuth (see SETUP.md);
  the skill never handles a password.
metadata:
  version: "0.2"
  author: scottybe
  updated: "2026-06-21"
  status: "ON HOLD (2026-06-21) — API path awaiting eBay developer keys (not yet issued); NOT a channel block. eBay writes route through the ebay-chrome browser skill until further notice. --dry-run only until keys arrive."
  changelog: "0.2 (2026-06-21): reframed BLOCKED -> ON HOLD — eBay is not blocked; writes go through ebay-chrome (browser) until further notice; this API path stays --dry-run-only until eBay developer keys are issued."
---

# ebay-lister — list on eBay via the Sell API

> ⏸️ **ON HOLD — API path not active yet (eBay is NOT blocked).** eBay writes — create AND revise —
> currently go through the **browser** via the **`ebay-chrome`** skill (Claude-in-Chrome), the
> sanctioned path until further notice. This API path is waiting on eBay developer keys (App ID /
> Cert ID / OAuth — not yet issued), so only `ebay_lister.py list --sku … --dry-run` is safe here (it
> builds payloads locally, makes no API call). When the keys arrive, follow SETUP.md, then flip
> `metadata.status` to active — the API path is the better route for batch/programmatic CREATE.

Replaces the flaky Chrome listing flow (which freezes at `document_idle`) with eBay's
REST Sell Inventory API. Source of truth for each listing is `items/RG-XXXX/label.json`.

## Prereqs (one time — see SETUP.md)
1. eBay developer app keys: `EBAY_CLIENT_ID`, `EBAY_CLIENT_SECRET`, `EBAY_RU_NAME`.
2. One-time owner OAuth consent for the `richmondgeneral` seller account → `EBAY_REFRESH_TOKEN`.
3. Business policy + location IDs: `EBAY_FULFILLMENT_POLICY_ID`, `EBAY_PAYMENT_POLICY_ID`,
   `EBAY_RETURN_POLICY_ID`, `EBAY_LOCATION_KEY` (capture via `ebay_lister.py policies`).
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

# Go live (create inventory item + offer, publish, write item_id/url back into label.json)
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
- Images are referenced from the public GitHub Pages URLs — push the item page first.
- Aspects are best-effort from `attributes`; pass `--aspect "Author=…"` to add required ones.
  If publish returns missing-required-aspect errors, add them and re-run (PUT/offer are idempotent).
- Dual-copy skill (source + plugin cache) — reinstall the plugin to sync the cache for code-mode.
