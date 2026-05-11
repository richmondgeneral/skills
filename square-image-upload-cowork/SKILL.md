---
name: square-image-upload-cowork
description: Cowork-native workflow to upload product images to Square Catalog, optionally cleaning the background and/or removing visible price tags via Cloudinary before upload. Use this skill whenever the user wants to push a product photo to Square from a Cowork session — including from a workspace file, an image URL (e.g., GitHub Pages or a vendor site), or to replace an existing Square catalog image. Trigger on phrasings like "upload this photo to Square", "swap out the product image", "fix the image on item X", "replace the price tag in this picture", "remove the background and put it on this Square item", "the photo has a sticker on it", "clean up this listing photo". Do NOT use for inventory adjustments (use square-inventory-loss) or for description text fixes.
---

# Square Image Upload — Cowork Native

Push a product image to Square Catalog from a Cowork session, with optional Cloudinary-based pre-processing for background removal and/or price-tag removal. No Mac filesystem or Photos.app dependencies — runs entirely inside Cowork's sandbox.

**Why this exists separately from the Mac `square-image-upload` skill:** the Mac version assumes `osascript`, the user's `~/.claude/skills` symlink tree, and a Mac-side Python venv. None of those work from Cowork. This skill runs against the Square MCP + Cloudinary MCP + the workspace mount only.

## Quick reference

- **Square location:** `B87BAEZ0NWV34` (Richmond General)
- **Workspace .env:** `/Users/scottybe/workspace/richmondgeneral/.env` — script reads `SQUARE_ACCESS_TOKEN` (or legacy `SQUARE_TOKEN`) from here when the env var isn't already set
- **Square-Version header:** `2026-04-21` (current pinned version)
- **Upload script:** `scripts/upload_to_square.py` (stdlib-only Python — no `requests` dependency)
- **Cloudinary:** accessed via the `mcp__09c02195-…__*` MCP tools, not direct API

## Input sources

The skill accepts the image in any of three forms — it resolves them all to bytes before the Square upload:

| Source | How the skill receives it | Resolved by |
|---|---|---|
| Workspace file | A path under `/Users/scottybe/workspace/richmondgeneral/...` | Direct file read from the Cowork mount |
| Public URL | An HTTP/HTTPS URL (GitHub Pages, vendor product page, etc.) | `urllib.request` GET inside the script |
| Existing Square image | A Square `image_id` (24-char) | `catalog.batchGetobjects` → look up `image_data.url` → fetch as URL |

For the Mac Photos library: ask the user to export the photo into the workspace folder first (their existing `photos-library` Mac skill can do this in one step). Don't try to reach Photos.app from Cowork — the sandbox can't.

## Workflow

### Step 1 — Confirm what's being uploaded and where it goes

Before any processing, get these from the user (or infer from context):

- **Source** — file path / URL / Square image_id (see table above)
- **Destination** — one of:
  - Attach to a Square `item_id` (becomes part of that item's image_ids array)
  - Attach to a Square `variation_id` (variation-specific image)
  - Replace an existing `image_id` (replaces in place)
- **Processing flags** — bg-removal? price-tag removal? both? neither?
- **Primary?** — should this be the item's primary/hero image?

If the user said "upload this photo to item X" without specifying processing, ask once about bg removal and price tags. Don't process by default — preserve the original unless asked.

### Step 2 — Process via Cloudinary (only if bg-removal or price-tag flagged)

Cloudinary is the cleanest path because both transformations compose in a single URL.

**2a. Upload the source to Cloudinary** (skip this if the source is already a Cloudinary URL):

```
mcp__09c02195-e0c5-43c5-b334-41a21dc2c1c8__upload-asset
  upload_request:
    file: "<source-url>"           # or file://<absolute-local-path>
    folder: "rg-pending"            # keeps temp uploads organized
    use_filename: true
    tags: ["rg-pending", "skill:square-image-upload-cowork"]
```

For a local workspace file, prefix the absolute path with `file://`. For a Square `image_id` source, first resolve to URL via `catalog.batchGetobjects`, then pass that URL.

Capture the response's `public_id` — you need it for the next step. Also note the `secure_url` (the original asset URL, before any transformations).

**2b. Build the transformation URL.**

Cloudinary delivery URL structure:
```
https://res.cloudinary.com/<cloud_name>/image/upload/<transformations>/<public_id>.<ext>
```

Transformations to apply (in order, each separated by `/`):

| If user asked for... | Component to add |
|---|---|
| Background removal | `e_background_removal` |
| Price-tag removal | `e_gen_remove:prompt_(price%20tag)` |
| Both | `e_background_removal/e_gen_remove:prompt_(price%20tag)` |
| Always (at end, for optimization) | `f_auto/q_auto` |

**Example URL** (bg-removal + price tag, on cloud `richmondgeneral`, asset `rg-pending/abc123`):
```
https://res.cloudinary.com/richmondgeneral/image/upload/e_background_removal/e_gen_remove:prompt_(price%20tag)/f_auto/q_auto/rg-pending/abc123.png
```

Hit the URL once via `urllib.request` from inside the upload script — that triggers Cloudinary to generate the derived asset, then returns the bytes.

**2c. Show the processed image to the user for sign-off** before uploading to Square. Use the Cowork image-preview path (the `mcp__cowork__present_files` tool, or paste the Cloudinary URL inline — Cowork renders public image URLs). If the user says it looks wrong, offer to:

- Re-run with different processing flags (e.g., turn off bg-removal if it ate part of the product)
- Skip processing and upload the original instead
- Bail and let the user fix the source

Do NOT push to Square without sign-off when processing was applied — the whole point of the sign-off step is to catch Cloudinary mistakes before they hit your live catalog.

### Step 3 — Upload to Square

Run the bundled Python script. It handles the multipart POST to `/v2/catalog/images`, which the Square MCP doesn't expose.

```bash
python3 scripts/upload_to_square.py \
  --source <file-path-or-url> \
  --item-id <ITEM_ID>           # OR --variation-id, OR --image-id (for replace)
  --name "Product Hero" \
  --caption "Front view" \
  --primary                      # optional: set as item's primary image
  --json                         # machine-readable output
```

**Key script behavior:**

- Resolves `SQUARE_ACCESS_TOKEN` via this priority: (1) `os.environ`, (2) `/Users/scottybe/workspace/richmondgeneral/.env` parsed manually (no `python-dotenv` dependency), (3) legacy `SQUARE_TOKEN` fallback at each level. Bails with a clear error message if none found.
- Sends `Square-Version: 2026-04-21` and `Authorization: Bearer <token>` headers.
- Builds multipart/form-data with two parts: a JSON `request` part and a binary `image_file` part. Required by Square's CreateCatalogImage endpoint.
- Uses Python stdlib only (`urllib`, `mimetypes`, `email.mime.multipart`) — no `requests`, no `python-dotenv`. Works in any vanilla Python 3 install.
- Returns either the new `image_id` (on create) or the updated record (on replace), plus the public `image_data.url` for verification.

### Step 4 — Verify

After upload, fetch the item one more time and confirm:
- The new `image_id` appears in the item's `image_ids` array (for new attaches)
- If `--primary` was set, the new image_id is at position 0
- The Square Online listing reflects the new image (give it ~30 seconds for CDN propagation)

Show the user the live Square catalog URL or the storefront product page if it exists.

## API gotchas (do NOT skip)

- **`Square-Version` header is required** on every Square API call. Use `2026-04-21`.
- **`/v2/catalog/images` is the ONLY multipart endpoint** in Square's API. Every other catalog endpoint takes JSON. Don't try to use `batchUpsertCatalogObjects` for image creation — that doesn't accept binary data.
- **The multipart body has exactly two parts**, in this order:
  1. A part named `request` with `Content-Type: application/json`, containing the JSON envelope (idempotency_key, object_id, image, is_primary).
  2. A part named `image_file` with the image's actual content-type (`image/png`, `image/jpeg`, etc.) and a `filename` in the `Content-Disposition`.
- **`object_id`** in the JSON envelope is what links the image to an item or variation. Set it to the `ITEM` id or `ITEM_VARIATION` id. For replace-in-place, omit `object_id` and use the `image_id` path parameter (`PUT /v2/catalog/images/{image_id}`) instead.
- **Cloudinary's `e_gen_remove`** charges generative-AI credits. Each invocation counts. Don't accidentally pipe an entire batch through it during testing — the dry-run path doesn't bypass this.
- **Cloudinary URL transformations are async-generated on first hit.** The first request to a brand-new transformation URL may take 5-15s as Cloudinary builds the derived asset. Subsequent requests are CDN-cached. The script should wait, not timeout aggressively.

## When something goes wrong

- **HTTP 401 from Square** → token isn't being read. Check that `.env` exists at `/Users/scottybe/workspace/richmondgeneral/.env` and has `SQUARE_ACCESS_TOKEN=...` (no quotes, no trailing whitespace). The script logs which resolution step succeeded.
- **HTTP 400 with `INVALID_REQUEST_ERROR` on object_id** → the id doesn't exist or is the wrong type (ITEM vs ITEM_VARIATION). Re-run `searchItems` to confirm.
- **Cloudinary processing returns the original unchanged** → check the URL — `e_` parameters need `e_` prefix (not `effect_`). URL-encode the prompt (`price%20tag`, not `price tag`).
- **Square returns the image but the storefront doesn't show it** → CDN propagation. Wait 30-60s. If still missing after a minute, the issue is `ecom_visibility` on the item itself, not the image upload.
- **Multipart upload returns `BAD_REQUEST` with no detail** → the parts are likely in the wrong order or the content-types are missing. The script enforces both — if you're hitting this from a manual `curl`, that's your culprit.

## Worked example (typical happy path)

User: *"There's a price sticker on the photo for item RG-0023. Replace the image with one without the sticker and remove the background while you're at it."*

1. Look up RG-0023 → get item_id + current image_ids[0]. Capture both.
2. `catalog.batchGetobjects` on image_ids[0] → get the original S3 URL.
3. Cloudinary `upload-asset` with that URL, folder `rg-pending`. Capture `public_id`.
4. Build URL: `…/image/upload/e_background_removal/e_gen_remove:prompt_(price%20tag)/f_auto/q_auto/<public_id>.png`
5. Show the cleaned image to user, ask "does this look right?"
6. On approval: `python3 scripts/upload_to_square.py --source <cloudinary-url> --image-id <existing image_ids[0]> --name "RG-0023 hero (cleaned)" --json`
7. Verify the item's image_ids[0] now points to the cleaned version. Note the new `image_data.url` in the response.

## Future work (not in v1)

- **Batch mode** — accept a directory or CSV manifest, process+upload many at once. Add in v2 once v1 is proven.
- **Manual region for `gen_remove`** — accept `--region x,y,w,h` for cases where the prompt-based detection misses the price tag. Cloudinary supports `e_gen_remove:region_(...)` syntax; we can layer it on without changing the script.
- **Side-by-side preview** — show before/after in a Cowork artifact so the user can compare without flipping between URLs.
- **Auto-cleanup of `rg-pending` Cloudinary folder** — delete temp uploads after Square has the final image, to keep Cloudinary storage tidy.
