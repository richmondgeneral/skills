# Square Catalog Image API Reference

## Overview

Square's Catalog API supports image management through two key endpoints:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/v2/catalog/images` | POST | Create new CatalogImage |
| `/v2/catalog/images/{image_id}` | PUT | Replace existing image file |

Both endpoints use **multipart form data** (not JSON). Official/newer Square MCP servers may support these endpoints, but connector coverage varies; use this skill's scripts as the stable default path.

## CreateCatalogImage (POST)

Creates a new `CatalogImage` object and optionally attaches it to an item or variation.

### Request Format

```
POST https://connect.squareup.com/v2/catalog/images
Content-Type: multipart/form-data

Parts:
- file: Image file (JPEG, PNG, GIF, etc.)
- request: JSON object with metadata
```

### Request JSON Schema

```json
{
  "idempotency_key": "unique-uuid-string",
  "object_id": "ITEM_OR_VARIATION_ID",  // Optional
  "is_primary": false,                   // Optional
  "image": {
    "id": "#TEMP_ID",
    "type": "IMAGE",
    "image_data": {
      "name": "Image Name",              // Optional
      "caption": "Image caption"         // Optional, shown in Square Online
    }
  }
}
```

### Response

```json
{
  "image": {
    "type": "IMAGE",
    "id": "XVGTTXX6VIFDJVH6YGDJCEK4",
    "updated_at": "2020-08-12T01:49:50.295Z",
    "version": 1597196990295,
    "is_deleted": false,
    "present_at_all_locations": true,
    "image_data": {
      "name": "Image Name",
      "url": "https://items-images-production.s3.us-west-2.amazonaws.com/...",
      "caption": "Image caption"
    }
  }
}
```

## UpdateCatalogImage (PUT)

Replaces the image file of an existing `CatalogImage` object while preserving its ID.

### Request Format

```
PUT https://connect.squareup.com/v2/catalog/images/{image_id}
Content-Type: multipart/form-data

Parts:
- file: New image file
- request: JSON object with metadata
```

### Request JSON Schema

```json
{
  "idempotency_key": "unique-uuid-string",
  "image": {
    "type": "IMAGE",
    "image_data": {
      "name": "Updated Name",    // Optional
      "caption": "Updated caption"  // Optional
    }
  }
}
```

## Supported Image Formats

- JPEG (.jpg, .jpeg)
- PNG (.png)
- GIF (.gif)
- WebP (.webp)
- BMP (.bmp)
- TIFF (.tiff, .tif)

## Image Requirements

- Maximum file size: 15 MB
- Recommended minimum: 500x500 pixels
- Square Online displays images at various sizes; higher resolution recommended

## Attaching Images to Items

After uploading, images can be attached to items via `UpsertCatalogObject`:

```json
{
  "object": {
    "type": "ITEM",
    "id": "EXISTING_ITEM_ID",
    "version": 1234567890,
    "item_data": {
      "image_ids": ["IMAGE_ID_1", "IMAGE_ID_2"]
    }
  }
}
```

The order of `image_ids` determines display order; first ID is the primary image.

## Authentication

All requests require:
- `Authorization: Bearer {ACCESS_TOKEN}`
- `Square-Version: 2026-04-21` (or current version — see project `.env` / SKILL.md changelog)

## Error Handling

Common errors:

| Code | Meaning |
|------|---------|
| 400 | Invalid request (bad image format, missing fields) |
| 401 | Invalid or expired access token |
| 404 | Image ID not found (for updates) |
| 413 | Image file too large |
| 429 | Rate limited |

## Richmond General Location

For reference, Richmond General's location ID: `B87BAEZ0NWV34`
