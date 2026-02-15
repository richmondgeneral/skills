---
name: square-image-upload
description: Upload and manage images in Square Catalog via API. Use when the user needs to upload product photos, replace existing catalog images, or attach images to Square items/variations. Triggers on "upload image to Square", "add photo to item", "replace product image", "Square catalog image", or any request to programmatically manage Square product images. Required because Square's image endpoints use multipart form data which the standard MCP connector cannot handle.
metadata:
  version: "1.4"
  author: scottybe
  updated: "2026-02-15"
  changelog: |
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

## ✅ Status: WORKING

**Verified:** 2024-12-21 - Direct API upload via this skill's Python script works correctly.

**Test Result:**
```
Image ID: JBV4V5HST6EAUXWB5ZPYP52G
URL: https://items-images-production.s3.us-west-2.amazonaws.com/files/.../original.jpeg
```

**Note:** Square MCP connector cannot upload images (JSON-only). This skill handles multipart/form-data uploads directly.

## Why This Skill Exists

The Square MCP connector only supports JSON-based API calls. Image upload endpoints require **multipart form data**, so this skill provides a Python script to handle the upload directly.

## Quick Start

### Prerequisites

1. Python 3.7+ with `requests` library
2. Square access token with `ITEMS_WRITE` permission
3. Set environment variable: `export SQUARE_ACCESS_TOKEN=your_token`

### Upload New Image to Item

```bash
python3 ~/.claude/skills/square-image-upload/scripts/upload_image.py \
  --image /path/to/photo.jpg \
  --item-id CATALOG_ITEM_ID \
  --name "Product Photo" \
  --caption "Front view of product"
```

### Replace Existing Image

```bash
python3 ~/.claude/skills/square-image-upload/scripts/upload_image.py \
  --image /path/to/new_photo.jpg \
  --image-id EXISTING_IMAGE_ID
```

### Upload to Item Variation

```bash
python3 ~/.claude/skills/square-image-upload/scripts/upload_image.py \
  --image /path/to/photo.jpg \
  --variation-id VARIATION_ID
```

### Bulk Upload All Item Photos (Hero + Details)

```bash
python3 ~/.claude/skills/square-image-upload/scripts/upload_batch.py \
  --directory /Users/scottybe/workspace/square/items/RG-0015 \
  --item-id CATALOG_ITEM_ID \
  --include \"*.png\" --include \"*.jpg\" --include \"*.jpeg\" \
  --json
```

### Bulk Upload via Manifest CSV

```bash
python3 ~/.claude/skills/square-image-upload/scripts/upload_batch.py \
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
do shell script "source ~/.env && python3 ~/.claude/skills/square-image-upload/scripts/upload_image.py \
  --image /Users/scottybe/workspace/square/items/RG-XXXX/hero.png \
  --item-id CATALOG_ITEM_ID \
  --name 'RG-XXXX Hero' \
  --caption 'Primary product image' \
  --primary"
```

## Finding Item/Image IDs

Use Square MCP to search catalog:

```
Square:make_api_request
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

**requests not found**: Install with `pip install requests`
