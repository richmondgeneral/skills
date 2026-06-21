# ebay-lister — one-time setup (owner)

> **STATUS (2026-06-19): BLOCKED — awaiting eBay dev-account approval.** The developer
> account application is submitted but **not yet approved**, so steps 1–4 below cannot be
> completed and the skill must not be used for live listing yet. When the approval email
> arrives, work through this file top to bottom, then clear the BLOCKED banner in SKILL.md.

This is the only part Claude can't do — it needs the eBay developer keys and a browser
sign-in to the `richmondgeneral` seller account. Claude never sees a password; it only
uses the post-consent `code` and the resulting tokens.

## 1. eBay developer app keys
1. Sign in at <https://developer.ebay.com> with the account tied to `richmondgeneral`.
2. **Application Keys** → use the **Production** keyset. Copy **App ID (Client ID)**,
   **Cert ID (Client Secret)**, **Dev ID**.
3. **User Tokens → Get a Token from eBay via Your Application** → create an **RuName**
   (the OAuth redirect). Copy the RuName string.

Store them in the login Keychain (resolved automatically by the skill):
```bash
security add-generic-password -U -a "$USER" -s EBAY_CLIENT_ID     -w '<App ID>'
security add-generic-password -U -a "$USER" -s EBAY_CLIENT_SECRET -w '<Cert ID>'
security add-generic-password -U -a "$USER" -s EBAY_RU_NAME       -w '<RuName>'
# optional: -s EBAY_ENV -w sandbox   (defaults to production)
```

## 2. One-time OAuth consent → refresh token
```bash
# Print the consent URL, open it in a browser, sign in as richmondgeneral, approve.
uv run --project <plugin> python skills/ebay-lister/scripts/ebay_auth.py consent-url
# After approving you're redirected to your RuName with ?code=<LONG_CODE> in the URL.
uv run --project <plugin> python skills/ebay-lister/scripts/ebay_auth.py exchange --code '<LONG_CODE>'
# -> stores EBAY_REFRESH_TOKEN in Keychain (good ~18 months). Verify:
uv run --project <plugin> python skills/ebay-lister/scripts/ebay_auth.py check
```

## 3. Business policies + inventory location
eBay offers must reference your fulfillment (shipping), payment, and return policies, plus
an inventory location. List what the account already has and copy the IDs:
```bash
uv run --project <plugin> python skills/ebay-lister/scripts/ebay_lister.py policies
```
Then store:
```bash
security add-generic-password -U -a "$USER" -s EBAY_FULFILLMENT_POLICY_ID -w '<id — the USPS Media Mail / standard policy>'
security add-generic-password -U -a "$USER" -s EBAY_PAYMENT_POLICY_ID     -w '<id>'
security add-generic-password -U -a "$USER" -s EBAY_RETURN_POLICY_ID      -w '<id>'
security add-generic-password -U -a "$USER" -s EBAY_LOCATION_KEY          -w '<merchantLocationKey, e.g. richmond-il>'
```
If `locations` is empty, create one once via the Inventory API `createInventoryLocation`
(`merchantLocationKey = richmond-il`, address = the Richmond, IL pickup address).

## 4. Smoke test, then go live
```bash
# Safe: builds the payloads, lists any still-missing config, no API call.
... ebay_lister.py list --sku RG-0032 --dry-run
# Live: creates the inventory item + offer, publishes, writes item_id/url into label.json.
... ebay_lister.py list --sku RG-0032 --publish
```

Once this is in place, listing any item is one command — RG-0031 and RG-0032 included.
