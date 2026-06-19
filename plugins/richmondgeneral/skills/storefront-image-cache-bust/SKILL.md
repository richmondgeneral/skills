---
name: storefront-image-cache-bust
description: Fix product photos that show wrong/sideways/stale on the Square Online storefront even though the Square Catalog API holds correct, updated versions. Triggers when the user says "the photo on the website is wrong / sideways / out of date", "Square Online is showing the old picture", "I rotated the image in Square but the storefront still has the old one", "storefront image cache is stale", "the CDN is serving the wrong image", "fix the photos for this item" (when the API copy is fine), or any case where `items-images-production.s3.us-west-2.amazonaws.com` shows the right file but `150225383.cdn6.editmysite.com` (or similar Weebly CDN) shows the wrong one. Do NOT use for first-time uploads (use `square-image-upload-cowork`) or for items where the Catalog API itself has the wrong photo.
---

# Storefront Image Cache Bust

## When to use

Square Online's storefront serves product images through a Weebly-side CDN (`<site_id>.cdn6.editmysite.com/uploads/...`) that is **keyed by Square catalog image ID**. The Square Catalog API serves the same images from a different bucket (`items-images-production.s3.us-west-2.amazonaws.com`).

When you update an image in Square via `PUT /v2/catalog/images/{id}` or via a rotation/clean pipeline, the API's S3 bucket gets the new bytes — but the Weebly CDN keeps serving the old bytes under the same image ID. There is no public knob to purge the Weebly cache by URL, and bumping the catalog image object's metadata (caption/name) does not invalidate it either.

The reliable bust: **create new catalog image objects with new IDs**, point the item at them, and let the old ones be soft-deleted. The new IDs translate to new CDN URLs, which Weebly fetches fresh.

### Symptoms

- The storefront product page shows a sideways/old/junky photo
- Downloading the same image ID's URL from `items-images-production.s3.us-west-2.amazonaws.com/files/.../original.jpeg` returns the **correct** rotated/clean version
- Downloading from `https://<site_id>.cdn6.editmysite.com/uploads/.../<image_id>.jpeg` returns the **stale** version
- A rotation or clean pipeline ran recently against the catalog (e.g., `rotate_item_images.py`) and the dashboard preview looks right but the public storefront does not

### Do not use this skill if

- The Catalog API itself has the wrong photo — that's an upload problem; use `square-image-upload-cowork` instead
- You are uploading a net-new image for the first time — same, use `square-image-upload-cowork`
- The issue is image **order** but each image is correct — just patch `item_data.image_ids` directly via `batchUpsertObjects`; no cache-bust needed

## Prerequisites

- `SQUARE_ACCESS_TOKEN` resolvable from env or `<workspace>/.env`
- The item ID and the list of image IDs currently attached to it
- The clean/correct image bytes available — either by downloading from each catalog image object's S3 `url` field, or from a local file the user has

## Pitfall — the `object_id` dedup trap

The script in this skill deliberately uploads images **without** the `object_id` parameter. If you pass `object_id=<item_id>` on `POST /v2/catalog/images`, Square's API may return the existing attached image's ID instead of minting a fresh one (observed behavior when the same item already has a similar attached image). Same ID = same CDN URL = no cache bust. Then if you delete those IDs to clean up, you end up deleting your own live images. Don't do this.

The correct sequence is:

1. Upload each replacement image with **no `object_id`** → get a brand-new image ID per file
2. PATCH the item's `image_ids` array to the new IDs (plus any IDs you're keeping)
3. Optionally delete the now-orphaned old image objects

## Procedure

### Step 1: confirm the diagnosis

Fetch the item with related image objects:

```
service: catalog
method: batchGetobjects
request:
  object_ids: ["<ITEM_ID>"]
  include_related_objects: true
```

For each suspect image, **compare bytes**:

```bash
# Correct version (Catalog API S3)
curl -s -o /tmp/api.jpeg "<image_data.url from batchGetobjects>"

# Stale version (Weebly CDN — note the image ID is the filename)
curl -s -o /tmp/cdn.jpeg "https://<site_id>.cdn6.editmysite.com/uploads/<path>/<IMAGE_ID>.jpeg"

file /tmp/*.jpeg
# Dimensions, aspect ratio, and file size will diverge if the CDN is stale.
```

If the user has Chrome MCP connected, you can also pull the rendered `<img>` srcs from the storefront product page DOM:

```js
Array.from(document.querySelectorAll('img'))
  .filter(i => i.alt && i.alt.includes('<ITEM_NAME>'))
  .map(i => i.src.split('?')[0])
```

Only proceed if (a) the API S3 URL clearly serves the correct file, and (b) the CDN URL clearly serves a wrong file.

### Step 2: download the clean files

For each stale image, download the API S3 version to a local temp directory. The S3 URL is `image_data.url` on each related `IMAGE` object in the `batchGetobjects` response.

### Step 3: run the fix script

The bundled `scripts/cache_bust_item_images.py` does steps 4–6 in one call:

```bash
python3 scripts/cache_bust_item_images.py \
  --item-id <ITEM_ID> \
  --stale <STALE_ID_1>:<local_file_1.jpeg>:<Name>:<Caption> \
  --stale <STALE_ID_2>:<local_file_2.jpeg>:<Name>:<Caption> \
  [--keep <UNCHANGED_IMAGE_ID> ...] \
  [--delete-orphans]
```

What it does:

1. For each `--stale` entry: upload the local file with **no** `object_id` → get a new image ID
2. Read the item, build `image_ids = [new_ids in order...] + [--keep ids in order...]`, write it back via the `POST /v2/catalog/object` upsert endpoint
3. If `--delete-orphans` was passed: delete the old stale image objects

The script reads `SQUARE_ACCESS_TOKEN` from env then falls back to `<workspace>/.env`.

### Step 4: verify on the storefront

After the script finishes, reload the storefront product page and confirm:

```js
Array.from(document.querySelectorAll('img'))
  .filter(i => i.alt && i.alt.includes('<ITEM_NAME>'))
  .map(i => ({src: i.src.split('?')[0].split('/').pop(), w: i.naturalWidth, h: i.naturalHeight}))
```

The image filenames should now be the **new** image IDs, and `naturalWidth/naturalHeight` should match the correct file dimensions (e.g., portrait 896×1195 instead of stale landscape 2000×1500).

Note: the storefront-rendered DOM order may not exactly match `item_data.image_ids` because Square Online's gallery component renders hero + thumbnails in its own order. The hero/primary photo position is what matters for the share image and search result.

## Worked example

On 2026-05-11, item `DLWJY2P7Q24CAY6YGAUY5JKP` (1892 Kings of the Forest, SKU RG-0002) had 3 photos that were sideways on the storefront despite a rotation script having corrected the API copies earlier. Diagnosis:

| Image | API S3 URL bytes | CDN URL bytes |
|---|---|---|
| Cover | 896×1195 portrait (correct) | 2000×1500 landscape (stale, counter visible) |
| Title page | 896×1195 (correct) | 2000×1500 (stale, sideways) |
| Polar bear | 896×1195 (correct) | 2000×1500 (stale, sideways) |
| LOC label | 1216×871 (correct) | 1216×871 (already correct, not stale) |

Fix: ran `cache_bust_item_images.py` with the 3 stale IDs and `--keep` for the LOC label. New image IDs `ESCQC2VZDSC3AIW22R4IEO74` (cover), `Z3XEFF24FZCNBBW7X2AY3HNS` (title), `HFHM74WWELSJBB5CHICY4BMM` (polar) replaced the old ones. Storefront DOM confirmed the new URLs render the correct portrait files.

## Related skills

- `square-image-upload-cowork` — for first-time uploads or content changes (use Cloudinary cleanup if needed)
- `storefront-publish-categories` — analogous Square Online cache problem, but for categories instead of images
- `storefront-sort-default` — another "REST API can't reach this" Square Online dashboard problem
