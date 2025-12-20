---
name: square-image-upload
description: Upload and manage images in Square Catalog via API. Use when the user needs to upload product photos, replace existing catalog images, or attach images to Square items/variations. Triggers on "upload image to Square", "add photo to item", "replace product image", "Square catalog image", or any request to programmatically manage Square product images. Required because Square's image endpoints use multipart form data which the standard MCP connector cannot handle.
metadata:
  version: "1.0"
---

# Square Image Upload

Upload images to Square Catalog using the CreateCatalogImage and UpdateCatalogImage API endpoints.

## Why This Skill Exists

The Square MCP connector only supports JSON-based API calls. Image upload endpoints require **multipart form data**, so this skill provides a Python script to handle the upload directly.

## Quick Start

### Prerequisites

1. Python 3.7+ with `requests` library
2. Square access token with `ITEMS_WRITE` permission
3. Set environment variable: `export SQUARE_ACCESS_TOKEN=your_token`

### Upload New Image to Item

```bash
python3 scripts/upload_image.py \
  --image /path/to/photo.jpg \
  --item-id PA4Z5DLBA76TOLWUCC33764V \
  --name "Product Photo" \
  --caption "Front view of product"
```

### Replace Existing Image

```bash
python3 scripts/upload_image.py \
  --image /path/to/new_photo.jpg \
  --image-id EXISTING_IMAGE_ID
```

### Upload to Item Variation

```bash
python3 scripts/upload_image.py \
  --image /path/to/photo.jpg \
  --variation-id CKBTJ55TYKLGPUZJWB52YVJP
```

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

## Workflow: Add Images to New Item

1. Create item via Square MCP (returns item ID)
2. Run upload script with `--item-id` and `--primary` for main image
3. Run upload script again for additional images

## Workflow: Update Item Images

1. Get item via Square MCP to find existing image IDs
2. Run upload script with `--image-id` to replace specific image

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

**401 Unauthorized**: Check access token is valid and has ITEMS_WRITE permission

**404 Not Found**: Image ID doesn't exist (for updates)

**413 Too Large**: Image exceeds 15MB limit - compress before upload

**requests not found**: Install with `pip install requests`
