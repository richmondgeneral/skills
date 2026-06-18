---
name: square-image-upload-cowork
description: Cowork-native workflow to upload product images to Square Catalog, optionally cleaning the background and/or removing visible price tags first. Cleanup runs on the Mac image-processor (Gemini) via the osascript bridge — no Cloudinary. Use this skill whenever the user wants to push a product photo to Square from a Cowork session — including from a workspace file, an image URL (e.g., GitHub Pages or a vendor site), or to replace an existing Square catalog image. Trigger on phrasings like "upload this photo to Square", "swap out the product image", "fix the image on item X", "replace the price tag in this picture", "remove the background and put it on this Square item", "the photo has a sticker on it", "clean up this listing photo". Do NOT use for inventory adjustments (use square-inventory-loss) or for description text fixes.
metadata:
  version: "2.0"
  author: scottybe
  updated: "2026-06-18"
  changelog: |
    v2.0 - Cloudinary removed. Image cleanup now runs on the Mac image-processor
      (Gemini) over the osascript bridge (verified callable from Cowork
      2026-06-18: `do shell script` runs bash on the Mac). One cleanup engine
      (Gemini) across the Mac and Cowork paths; --fix-damage / --both now
      available (Cloudinary couldn't do them). Square upload path unchanged.
---

# Square Image Upload — Cowork

Push a product image to Square Catalog from a Cowork session, with optional background removal and/or price-tag removal first. Cleanup runs on the **Mac `image-processor` (Gemini)**, invoked over the **osascript bridge** — no Cloudinary, no extra image connector.

**The bridge:** Cowork can run AppleScript through the "Control your Mac" osascript extension, and `do shell script "…"` runs bash on the Mac (verified from Cowork, 2026-06-18). That lets this skill hand image cleanup to the same Gemini engine the Mac path uses. Files pass through the shared **workspace mount** (`~/workspace/richmondgeneral/...`), which both Cowork and the Mac can read/write.

> Repo note: this file is the source of truth. The copy Cowork actually loads is the account-synced skill (the `anthropic-skills` manifest). Re-sync it via the Skills UI for this change to take effect inside Cowork.

## Quick reference

- **Square location:** `B87BAEZ0NWV34` (Richmond General)
- **Square-Version header:** `2026-04-21`
- **Upload script:** `scripts/upload_to_square.py` (stdlib-only Python — no `requests`)
- **Workspace .env:** auto-discovered relative to the script; reads `SQUARE_ACCESS_TOKEN` (legacy `SQUARE_TOKEN` fallback)
- **Cleanup bridge (Mac Gemini):**
  ```
  osascript → do shell script "source $HOME/.local/bin/env && \
    uv run --project $HOME/workspace/richmondgeneral/skills/plugins/richmondgeneral \
    python $HOME/workspace/richmondgeneral/skills/plugins/richmondgeneral/skills/image-processor/scripts/clean.py \
    --input '<INPUT>' --output '<OUTPUT>' [--remove 'price tag'] [--fix-damage]"
  ```
  `uv` is at `$HOME/.local/bin/uv`; `source $HOME/.local/bin/env` is required (the bare osascript shell has neither `uv` on PATH nor a new-enough Python — system is 3.9.6; `uv` provisions ≥3.11).

## Input sources

The skill resolves any of these to a file the Mac can read **before** cleanup/upload:

| Source | How received | Staged for cleanup |
|---|---|---|
| Workspace file | path under `~/workspace/richmondgeneral/...` | already on the shared mount — use directly |
| Public URL | HTTP/HTTPS (GitHub Pages, vendor page) | download into `~/workspace/richmondgeneral/rg-pending/` first |
| Existing Square image | 24-char `image_id` | `catalog.batchGetObjects` → `image_data.url` → download into the workspace |

For the Mac Photos library: the bridge can now reach it too — but the cleanest path is still to have the Mac `photos-library` skill export into the workspace, then proceed here.

## Workflow

### Step 1 — Confirm source / destination / processing / primary
Get (or infer): **source** (file/URL/image_id), **destination** (`item_id`, `variation_id`, or replace an `image_id`), **processing flags** (bg-removal? price-tag? both? neither?), and whether it's the **primary** image. Don't process by default — ask once if unspecified.

### Step 2 — Clean on the Mac (only if bg-removal or price-tag flagged)
1. **Stage** the source as a file under the shared workspace (download URLs / Square images into `~/workspace/richmondgeneral/rg-pending/` first).
2. **Run `image-processor`'s `clean.py` on the Mac via the bridge** (see Quick reference for the exact command). Write `--output` to a workspace path so Cowork can read it back.
   - `--remove "price tag"` (or `"sticker"`, freeform) for targeted inpainting.
   - `--fix-damage` / `--both` for damage handling (now available — Cloudinary couldn't).
3. **Sign-off:** show the cleaned file to the user (`mcp__cowork__present_files`, or inline) **before** uploading. If it's wrong: re-run with different flags, upload the original instead, or bail. Do NOT push to Square without sign-off when cleanup was applied.

### Step 3 — Upload to Square
```bash
python3 scripts/upload_to_square.py \
  --source <workspace-file-or-url> \
  --item-id <ITEM_ID>          # OR --variation-id, OR --image-id (replace in place)
  --name "Product Hero" --caption "Front view" \
  --primary --json
```
The script does the multipart POST to `/v2/catalog/images` (the only multipart Square endpoint), resolves `SQUARE_ACCESS_TOKEN` from env/`.env`, sends `Square-Version: 2026-04-21`, and returns the new/updated `image_id` + public `image_data.url`.

### Step 4 — Verify
Re-fetch the item: confirm the new `image_id` is in `image_ids` (position 0 if `--primary`), and the storefront reflects it (~30s CDN propagation).

## Gotchas
- **Bridge env:** `do shell script` is a bare non-login shell — `source $HOME/.local/bin/env` first or `uv` won't be found; don't fall back to the system Python 3.9.6.
- **Paths must be Mac-visible:** the bridge runs on the Mac, so inputs/outputs go under `~/workspace/richmondgeneral/...` (the shared mount), not a Cowork-only sandbox path.
- **`Square-Version` header required** on every Square call (`2026-04-21`).
- **`/v2/catalog/images` is the only multipart endpoint** — two parts in order: JSON `request`, then binary `image_file`. The script enforces this.
- **`object_id`** in the JSON envelope links the image to the `ITEM`/`ITEM_VARIATION`; for replace-in-place use `PUT /v2/catalog/images/{image_id}` (omit `object_id`).

## When something goes wrong
- **HTTP 401 from Square** → token not read; check `.env` has `SQUARE_ACCESS_TOKEN=` (no quotes/whitespace).
- **`uv: command not found` over the bridge** → you skipped `source $HOME/.local/bin/env`.
- **clean.py output not visible to Cowork** → it was written outside the shared workspace mount; rerun with `--output` under `~/workspace/richmondgeneral/...`.
- **Square shows the image but storefront doesn't** → CDN propagation (wait 30–60s); if persistent, it's `ecom_visibility` on the item, not the upload.

## Worked example
User: *"There's a price sticker on the photo for RG-0023. Replace the image without the sticker and remove the background."*
1. Look up RG-0023 → `item_id` + current `image_ids[0]`.
2. `catalog.batchGetObjects` on `image_ids[0]` → S3 URL → download to `~/workspace/richmondgeneral/rg-pending/RG-0023-src.png`.
3. Bridge-clean: `… clean.py --input '~/workspace/richmondgeneral/rg-pending/RG-0023-src.png' --output '~/workspace/richmondgeneral/rg-pending/RG-0023-clean.png' --remove 'price tag'` (bg removal is clean.py's default storefront treatment).
4. Show the cleaned file; get sign-off.
5. `python3 scripts/upload_to_square.py --source ~/workspace/richmondgeneral/rg-pending/RG-0023-clean.png --image-id <existing image_ids[0]> --name "RG-0023 hero (cleaned)" --json`
6. Verify `image_ids[0]` now points to the cleaned version.

## Relationship to the Mac `square-image-upload`
Cleanup now uses the **same Gemini engine** as the Mac path (via the bridge), so the old Cloudinary capability gap is closed. The Mac `square-image-upload` still has extras for bulk work — parallel `--all-images`, `--max-cost` guardrail, rotation pre-pass, pre/post downscale. For a full catalog refresh on the Mac, use that; for a one-off from Cowork, use this.
