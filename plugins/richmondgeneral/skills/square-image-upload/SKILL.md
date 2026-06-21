---
name: square-image-upload
description: Upload and manage images in Square Catalog via API. Use when the user needs to upload product photos, replace existing catalog images, or attach images to Square items/variations. Triggers on "upload image to Square", "add photo to item", "replace product image", "Square catalog image", or any request to programmatically manage Square product images. This skill is the deterministic default for image uploads, even when some Square MCP connectors expose multipart methods.
metadata:
  version: "1.6"
  author: scottybe
  updated: "2026-05-11"
  runtime_tier: "LOCAL_STANDARD"
  required_capabilities:
    - filesystem_full_access
    - network_access
  changelog: |
    v1.6 - End-to-end refresh + rotation pre-pass + parallel mode:
    - Added `refresh_item_image.py` — resolve item by ID or title → download
      → clean via image-processor → upload back to Square (in-place PUT).
      Supports `--all-images`, `--both` (museum preserved/fixed pair),
      `--prefer preserved|fixed|ask`, `--pro`, `--remove`, `--inspect`,
      `--max-cost` budget guard.
    - Auto-detects hi-res source at `items/RG-XXXX/original.png` if larger
      than Square's stored copy (Square commonly holds a downscaled version).
    - Parallel workers under `--all-images` via thread pool, default
      concurrency 3, capped at 8. Honors Gemini 429/5xx via retry/backoff in
      the image-processor lib.
    - Added `rotate_item_images.py` pre-pass — asks Gemini which CW rotation
      makes each image right-side up, then rotates locally + uploads.
      Run before refresh to fix orientation cheaply (no AI cleanup cost).
    - Square API version bumped to `2026-04-21` (was `2024-12-18`).
    - Auth model: Keychain entry `SQUARE_ACCESS_TOKEN` (auto-exported by
      `~/.zshrc`) is now the primary auth path; project `.env` is fallback.

    v1.5 - runtime contract alignment:
    - Added runtime tier and capability metadata
    - Added runtime policy guidance for privileged/local execution boundaries

    v1.4 - Bulk upload support:
    - Added `upload_batch.py` for directory/manifest-based multi-image uploads
    - Added `*-nobg` preference logic and hero-first primary ordering
    - Added dry-run mode for safe upload planning

    v1.3 - Anthropic skills update:
    - Added author field
    - Updated date to 2025
---

# Square Image Upload

Upload images to Square Catalog using the CreateCatalogImage and UpdateCatalogImage API endpoints.

## Runtime Policy Contract

This skill runs as `LOCAL_STANDARD` for local filesystem access + Square API writes.

Policy references:

- `/Users/scottybe/workspace/square/square-tools/runtime/capability_matrix.json`
- `/Users/scottybe/workspace/square/square-tools/runtime/operation_policy.json`

Related privileged image-export flows (`Photos.app`) are outside this skill and belong to `LOCAL_PRIVILEGED` tooling in `square-tools/bin/`.

## ✅ Status: WORKING

**Verified:** 2024-12-21 - Direct API upload via this skill's Python script works correctly.

**Test Result:**
```
Image ID: JBV4V5HST6EAUXWB5ZPYP52G
URL: https://items-images-production.s3.us-west-2.amazonaws.com/files/.../original.jpeg
```

**Note:** Some Square MCP connectors now expose multipart image methods. Keep this skill as the default upload path for consistent behavior across environments.

## Why This Skill Exists

Square image endpoints require **multipart form data**. Connector behavior varies by client/server version, so this skill provides a stable Python path that works regardless of MCP multipart support.

Note: the `catalog` service in the Square MCP does **not** currently expose image methods — `get_service_info(service: "catalog")` lists only `batchGetobjects`, `batchInsertObjects`, `batchUpdateObjects`, `batchDeleteobjects`, `list`, `searchObjects`, `searchItems`, `updateItemModifierLists`, `updateItemTaxes` (so `get_type_info(service: "catalog", method: "createImage")` errors). The image endpoints require multipart form data and are reached over raw HTTP, which is exactly what this skill's scripts do — use them as the reliable path. If a future MCP/client adds multipart image methods, fall back to this skill's scripts if behavior differs across clients.

## Quick Start

### Prerequisites

1. [`uv`](https://docs.astral.sh/uv/) — manages Python runtime and dependencies (`requests`, `Pillow`) automatically
2. Square access token with `ITEMS_WRITE` permission
3. Square token wired up: Keychain entry `SQUARE_ACCESS_TOKEN` exists (auto-exported by `~/.zshrc`); falls back to project `.env`. See [project root `.env.example`](../../.env.example) for setup.
4. For `refresh_item_image.py`: also `GEMINI_API_KEY` (same Keychain → env → `.env` resolution chain) since it shells out to `clean.py`.

### End-to-End Refresh (recommended entrypoint)

`refresh_item_image.py` is the canonical "fix this item's image and put it back on Square" workflow. It composes download + cleanup + upload in one call.

```bash
# Just look at what's currently attached, no modifications:
uv run --with requests scripts/refresh_item_image.py --item-id TJSHQTHOKYUDORWURROAQCNZ --inspect

# Resolve by title fragment (errors if it matches >1 item):
uv run --with requests scripts/refresh_item_image.py --title "Lionel Pennsylvania GG-1"

# Damage-preservation default (honest condition photo, single image):
uv run --with requests scripts/refresh_item_image.py --item-id <ID>

# Damage-fix mode (restoration look for items where condition is incidental):
uv run --with requests scripts/refresh_item_image.py --item-id <ID> --fix-damage

# Museum companion: produce both variants. Preserved → Square primary;
# fixed → items/RG-XXXX/restored.jpg (for the GitHub Pages before/after view).
uv run --with requests scripts/refresh_item_image.py --item-id <ID> --both

# Process every attached image, with parallelism (default 3 workers, cap 8):
uv run --with requests scripts/refresh_item_image.py --item-id <ID> --all-images --concurrency 4

# Budget guard — abort pre-flight if estimated cost exceeds the cap:
uv run --with requests scripts/refresh_item_image.py --item-id <ID> --all-images --max-cost 5.00

# Use the higher-quality Gemini 3 Pro model (~$2.13/call vs ~$0.57/call):
uv run --with requests scripts/refresh_item_image.py --item-id <ID> --pro

# Freeform extra direction layered on the universal prompt:
uv run --with requests scripts/refresh_item_image.py --item-id <ID> --remove "the dust on the rim"
```

`--both` and `--all-images` are **mutually exclusive** (multiplies cost without
clear benefit — re-run twice if you really want both versions for every image).
`--prefer ask` errors fast if stdin isn't a TTY (no hung launchd/cron jobs).

### Rotation Pre-Pass

Run before `refresh_item_image.py` to cheaply fix orientation (no AI cleanup cost):

```bash
# Auto-detect rotation for an item's primary image:
uv run --with requests,Pillow scripts/rotate_item_images.py --item-id <ID>

# All images on the item:
uv run --with requests,Pillow scripts/rotate_item_images.py --item-id <ID> --all-images

# Dry-run — show what would rotate without modifying Square:
uv run --with requests,Pillow scripts/rotate_item_images.py --item-id <ID> --dry-run
```

### Upload New Image to Item

```bash
uv run --with requests ~/workspace/richmondgeneral/skills/square-image-upload/scripts/upload_image.py \
  --image /path/to/photo.jpg \
  --item-id CATALOG_ITEM_ID \
  --name "Product Photo" \
  --caption "Front view of product"
```

### Replace Existing Image

```bash
uv run --with requests ~/workspace/richmondgeneral/skills/square-image-upload/scripts/upload_image.py \
  --image /path/to/new_photo.jpg \
  --image-id EXISTING_IMAGE_ID
```

### Upload to Item Variation

```bash
uv run --with requests ~/workspace/richmondgeneral/skills/square-image-upload/scripts/upload_image.py \
  --image /path/to/photo.jpg \
  --variation-id VARIATION_ID
```

### Bulk Upload All Item Photos (Hero + Details)

```bash
uv run --with requests ~/workspace/richmondgeneral/skills/square-image-upload/scripts/upload_batch.py \
  --directory /Users/scottybe/workspace/square/items/RG-XXXX \
  --item-id CATALOG_ITEM_ID \
  --include \"*.png\" --include \"*.jpg\" --include \"*.jpeg\" \
  --json
```

### Bulk Upload via Manifest CSV

```bash
uv run --with requests ~/workspace/richmondgeneral/skills/square-image-upload/scripts/upload_batch.py \
  --manifest /path/to/upload-manifest.csv \
  --json
```

Manifest columns:
- `image_path` (required)
- `item_id` or `variation_id` (required unless supplied via CLI)
- `name` (optional)
- `caption` (optional)
- `is_primary` (optional: true/false)

## Script Options

| Flag | Description |
|------|-------------|
| `--image`, `-i` | Path to image file (required) |
| `--item-id` | Catalog item ID to attach image to |
| `--variation-id` | Item variation ID to attach image to |
| `--image-id` | Existing CatalogImage ID to replace |
| `--name`, `-n` | Image name |
| `--caption`, `-c` | Image caption (shown in Square Online) |
| `--primary`, `-p` | Set as primary image |
| `--token`, `-t` | Square access token (or use env var) |
| `--json`, `-j` | Output full JSON response |

### `upload_batch.py` options

| Flag | Description |
|------|-------------|
| `--directory` | Directory mode source |
| `--manifest` | CSV manifest mode source |
| `--item-id` | Target item ID (directory mode, or manifest fallback) |
| `--variation-id` | Target variation ID (directory mode, or manifest fallback) |
| `--recursive` | Recurse through subfolders in directory mode |
| `--include` | Include glob pattern (repeatable) |
| `--exclude` | Exclude glob pattern (repeatable) |
| `--primary-file` | Force a specific file as primary |
| `--no-auto-primary` | Keep existing primary image; do not set primary in directory mode |
| `--no-prefer-nobg` | Disable `*-nobg` variant preference |
| `--dry-run` | Build and print upload plan without API calls |
| `--continue-on-error` | Keep uploading after individual failures |
| `--json` | Output JSON summary |

## Workflow: Add Images to New Item

1. Create item via Square MCP (returns item ID)
2. Process image group with image-processor batch mode if needed:
   - `process_group.py --input-dir /Users/scottybe/workspace/square/items/RG-XXXX`
3. Run batch upload for all processed photos:
   - `upload_batch.py --directory /Users/scottybe/workspace/square/items/RG-XXXX --item-id CATALOG_ITEM_ID`

**Important:** Item must exist before attaching image. Create catalog item first, then upload image.

## Workflow: Update Item Images

1. Get item via Square MCP to find existing image IDs
2. Run upload script with `--image-id` to replace specific image

## Integration with rg-full-auto

In Phase 2, after background removal:

```bash
# Via osascript (runs on Mac with env vars)
do shell script "source ~/.env && uv run --with requests ~/workspace/richmondgeneral/skills/square-image-upload/scripts/upload_image.py \
  --image /Users/scottybe/workspace/square/items/RG-XXXX/hero.png \
  --item-id CATALOG_ITEM_ID \
  --name 'RG-XXXX Hero' \
  --caption 'Primary product image' \
  --primary"
```

## Finding Item/Image IDs

Use Square MCP to search catalog:

```
mcp_square_api:make_api_request
  service: catalog
  method: searchItems
  request: {"text_filter": {"keywords": ["product name"]}}
```

Response includes `image_ids` array for each item.

## API Reference

See [references/api_reference.md](references/api_reference.md) for detailed endpoint documentation.

## Supported Formats

JPEG, PNG, GIF, WebP, BMP, TIFF (max 15MB)

## Troubleshooting

**403 Forbidden**: Usually means item doesn't exist yet, or wrong item ID. Create catalog item first.

**401 Unauthorized**: Check access token is valid and has ITEMS_WRITE permission

**404 Not Found**: Item or image ID doesn't exist

**413 Too Large**: Image exceeds 15MB limit - compress before upload

**requests not found**: If running outside of `uv run --with requests`, install manually with `pip install requests`

## Running the tests

Unit tests live in the parent `skills/` repo under `testing/unit/`. Relevant files for this skill:

- `test_refresh_item_image_parallel.py` — concurrency, mutex flags, exit codes
- `test_rotate_item_images.py` — rotation correctness on synthetic inputs
- `test_square_upload_batch.py` — bulk upload preference/sort logic

Run them:

```bash
cd ~/workspace/richmondgeneral/skills
uv run --with requests,Pillow,pytest -m pytest testing/unit/test_refresh_item_image_parallel.py \
                  testing/unit/test_rotate_item_images.py \
                  testing/unit/test_square_upload_batch.py -v
```

Or run the full skills test suite: `uv run --with requests,Pillow,pytest -m pytest testing/unit/ -v`.
