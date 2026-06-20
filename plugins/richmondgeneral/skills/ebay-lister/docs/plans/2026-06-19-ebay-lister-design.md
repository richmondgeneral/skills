# ebay-lister — design (2026-06-19)

## Why
The browser (Chrome) eBay listing flow reliably freezes at `document_idle` on the
listing form — RG-0028 dishes, RG-0031, RG-0032 all stalled there. The robust fix is
eBay's official **Sell API** (REST), which has no browser dependency and is batchable.
This skill replaces the manual "listing pack → owner clicks publish" hand-off with a
scripted `createOrReplaceInventoryItem → createOffer → publishOffer` pipeline driven by
`items/RG-XXXX/label.json`.

## Scope (v0.1)
- Create/replace an eBay **inventory item** keyed by our SKU (`RG-XXXX`).
- Create and **publish** a fixed-price **offer** (Buy It Now + optional Best Offer).
- Write the resulting eBay `listingId` + URL back into `label.json → channels.ebay`.
- `--dry-run` builds and prints the exact payloads without calling eBay (testable with no creds).
- Out of scope for v0.1: variations/multi-SKU, auctions, eBay-hosted image upload
  (we pass our public GitHub Pages image URLs), revise/end flows (add in v0.2).

## API surface (production hosts)
- OAuth token: `POST https://api.ebay.com/identity/v1/oauth2/token`
- Authorize (consent): `https://auth.ebay.com/oauth2/authorize`
- Inventory item: `PUT https://api.ebay.com/sell/inventory/v1/inventory_item/{sku}`
- Offer: `POST https://api.ebay.com/sell/inventory/v1/offer`
- Publish: `POST https://api.ebay.com/sell/inventory/v1/offer/{offerId}/publish`
- Policies (setup/lookup): `GET https://api.ebay.com/sell/account/v1/{fulfillment|payment|return}_policy?marketplace_id=EBAY_US`
- Location (setup): `GET/POST https://api.ebay.com/sell/inventory/v1/location`

Scopes: `…/oauth/api_scope/sell.inventory` (list/publish) + `…/sell.account` (read policies/locations).

## Auth model (owner does the one-time consent; the skill never sees a password)
1. Owner registers/uses the eBay developer app → **App ID (client_id)**, **Cert ID (client_secret)**, **Dev ID**, and an **RuName** (redirect).
2. Owner opens the **consent URL** (`ebay_auth.py consent-url`), signs in to the
   `richmondgeneral` seller account, approves the scopes, and is redirected with a `code`.
3. `ebay_auth.py exchange --code <CODE>` swaps the code for a **refresh token** (≈18-month
   life) and stores it in the login Keychain as `EBAY_REFRESH_TOKEN`.
4. Every run, `get_access_token()` mints a short-lived access token from the refresh token.
   Credential resolution order mirrors the other RG skills: **env → macOS Keychain → workspace `.env`**.

Keychain/env names: `EBAY_CLIENT_ID`, `EBAY_CLIENT_SECRET`, `EBAY_REFRESH_TOKEN`,
`EBAY_RU_NAME`, and config `EBAY_FULFILLMENT_POLICY_ID`, `EBAY_PAYMENT_POLICY_ID`,
`EBAY_RETURN_POLICY_ID`, `EBAY_LOCATION_KEY`, `EBAY_MARKETPLACE` (default `EBAY_US`),
`EBAY_ENV` (`production` default | `sandbox`).

Hard-fail (no silent fallback) when creds are missing — same philosophy as `sku_authority`.

## Data mapping (label.json → eBay)
| eBay field | Source |
|---|---|
| inventory `sku` | `label.sku` (RG-XXXX) |
| `product.title` | pack title if present, else `product_name` (≤80 chars) |
| `product.description` | `condition_notes` (+ brand-voice description if available) |
| `product.aspects` | parsed from `attributes` + type-specific defaults (Author/Publisher/Year/…) |
| `product.imageUrls` | `https://richmondgeneral.github.io/items/RG-XXXX/{hero,detail-*}.png` |
| `condition` enum | mapped from `condition` text (Very Good→USED_VERY_GOOD, Good→USED_GOOD, …) |
| `availability` qty | 1 (or from inventory) |
| offer `categoryId` | type → eBay category (Books & Paper → 261186) |
| offer `pricingSummary.price` | `price` |
| offer Best Offer | `listingPolicies.bestOfferTerms.bestOfferEnabled = true` |
| offer policies | the configured fulfillment/payment/return policy IDs |
| offer `merchantLocationKey` | `EBAY_LOCATION_KEY` |

## Write-back
On publish, set `channels.ebay = {status:"listed", item_id:<listingId>,
url:"https://www.ebay.com/itm/<listingId>", listed_price:<price>, offer_id:<offerId>}` in
`label.json`. Caller commits/pushes the `items` repo (matches the rest of the workflow).

## CLI
```
ebay_auth.py consent-url                 # print the URL the owner opens to grant consent
ebay_auth.py exchange --code <CODE>      # one-time: code → refresh token (store in Keychain)
ebay_auth.py check                       # verify token mint + print token expiry
ebay_lister.py policies                  # list account business policies (capture IDs for setup)
ebay_lister.py list --sku RG-XXXX --dry-run   # build + print payloads, no API call
ebay_lister.py list --sku RG-XXXX --publish   # create inv item + offer + publish + write back
```

## Dual-copy note
Like the other RG skills there are two copies (source `skills/plugins/.../ebay-lister/`
and the plugin cache). Cowork-over-bridge runs source; reinstall the plugin to sync the
cache before code-mode uses it.
