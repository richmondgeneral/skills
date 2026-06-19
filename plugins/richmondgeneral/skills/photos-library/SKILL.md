---
name: photos-library
description: Query and extract photos from macOS Photos Library. Use when user asks to find recent photos, extract product photos, search by date/album/type, convert HEIC to JPEG, or pull images from Photos app for processing. Triggers on "recent photos", "photos from last week", "extract from Photos", "product photos", "find pictures of", "pull from camera roll".
metadata:
  version: "1.6"
  author: scottybe
  updated: "2026-06-19"
  changelog: |
    v1.6 - Library-based intake helper (intake_to_item.py):
    - Given --sku + --album/--keyword, pulls matching originals via sips into
      items/RG-XXXX/ (hero.jpeg + detail-N.jpeg) and stubs label.json. Takes the
      first --limit ON-DISK photos so offloaded originals don't crowd out usable
      ones (reports offloaded). Replaces the retired catalog_pipeline/images/.

    v1.5 - Album / keyword (tag) filtering for intake:
    - query_photos.py, extract_photos.py, find_product_clusters.py gained
      --album and --keyword/--tag, so intake can pull by the Intake album or a
      tag instead of only recency. Join tables are discovered at runtime (shared
      photos_db.py) so it survives Photos schema-version bumps.
    - --album/--keyword drop the default day window (select by membership, not
      recency); an unknown album/keyword warns with known-album hints.

    v1.4 - macOS-native extraction + offloaded reporting:
    - extract_photos.py converts with `sips` (built into macOS) instead of
      ImageMagick `convert`, which isn't installed (extraction returned 0).
      JPEG quality via -s formatOptions; --resize maps to `sips -Z` (bounds
      the longest side, preserves aspect).
    - iCloud-offloaded originals (not on disk) are collected and reported with
      a count + filenames + how to download, instead of being silently skipped
      (which hid intake photos in the first batch).

    v1.3 - Safe database access (critical fix):
    - All scripts now open Photos.sqlite with mode=ro&immutable=1
    - Previously query/extract/find_product_clusters used a plain
      read-write connection, which could take locks and checkpoint the
      WAL of the live, cloudphotod-managed database. This disrupted
      iCloud sync-state tracking and forced full re-pulls (symptoms:
      CloudTrackerLastKnownCloudVersion fetch failures, out-of-order
      and delayed photo arrival, rotation re-processing, choppy UI).
    - immutable=1 guarantees no locks and no WAL access; reads can no
      longer disturb Photos/iCloud sync.

    v1.2 - Product photo clustering:
    - Added find_product_clusters.py for auto-grouping photos by shoot
    - Classifies clusters as: product, real_estate, screenshot, single, mixed
    - Fixed --favorites ignoring day filter when used alone

    v1.1 - Security and robustness fixes:
    - Fixed SQL injection vulnerability (parameterized queries)
    - Added database connection context managers (prevents leaks)
    - Added input validation for all CLI parameters
    - Improved error handling (OSError, PermissionError)
    - Extracted magic numbers to named constants

    v1.0 - Initial release: SQLite access to Photos.app library
---

# Photos Library

Query the macOS Photos Library SQLite database and extract photos for processing.

## Requirements

- macOS with Photos app
- Mount user's home directory via `mcp__cowork__request_cowork_directory`
- Python 3 with sqlite3 module
- macOS `sips` (built in) for HEIC→JPEG conversion — no Homebrew/ImageMagick needed

## Database Location

```
~/Pictures/Photos Library.photoslibrary/database/Photos.sqlite
```

## Quick Start

### Query recent photos (last 7 days)

```bash
python3 scripts/query_photos.py --days 7
```

### Extract photos to a folder

```bash
python3 scripts/extract_photos.py --days 7 --output ~/Desktop/Images/from_photos
```

## Core Scripts

### `scripts/query_photos.py`

List photos with metadata. Filters:
- `--days N` - Photos from last N days
- `--min-width N` - Minimum width in pixels
- `--favorites` - Only favorited photos
- `--album "NAME"` - Only photos in this album (e.g. an Intake album)
- `--keyword/--tag "NAME"` - Only photos with this keyword/tag
- `--limit N` - Max results (default 20)

`--album`/`--keyword` select by membership, so they drop the default day window
(pass `--days N` to re-narrow). The join tables are discovered at runtime, so
this keeps working across Photos schema versions.

### `scripts/extract_photos.py`

Extract and convert photos with macOS-native `sips` (no ImageMagick). Options:
- `--days N` - Photos from last N days
- `--album "NAME"` / `--keyword "NAME"` - Pull by album or tag (not just recency)
- `--output PATH` - Destination folder
- `--format jpeg|png` - Output format (default: jpeg)
- `--quality N` - JPEG quality 1-100 (default: 90)
- `--resize WxH` - Bound the longest side to fit a WxH box (aspect preserved)

iCloud-offloaded originals (not on local disk) are reported at the end with a
count + filenames, never silently skipped. Download them in Photos (select →
File ▸ "Download Originals") or `osxphotos export --download-missing`, then re-run.

### `scripts/find_product_clusters.py`

Auto-group photos by shooting session and classify them:
- `--days N` - Search last N days (default: 14)
- `--type TYPE` - Filter: all, product, real_estate, screenshot, single, mixed
- `--album "NAME"` / `--keyword "NAME"` - Cluster only photos in an album/tag
- `--gap N` - Max seconds between photos in cluster (default: 300)
- `--json` - Output as JSON

Classification heuristics:
- **product**: Portrait orientation, 4:3 ratio, multiple shots in cluster
- **real_estate**: Landscape, 5+ photos in cluster
- **screenshot**: Wide aspect ratio (2.16+ = phone screenshots)
- **single**: Isolated photo, not part of cluster
- **mixed**: Unclear classification

### `scripts/intake_to_item.py`

Library-based intake — pull an album/tag straight into an item folder:
```bash
python3 scripts/intake_to_item.py --sku RG-0028 --album "Intake RG-0028"
```
Finds the matching originals, converts them with `sips` into `items/RG-XXXX/`
(`hero.jpeg` + `detail-1.jpeg` …), and stubs `label.json`. Options: `--keyword/--tag`,
`--hero "<filename substring>"` (choose the hero), `--limit`, `--resize WxH`,
`--items-dir`, `--force`. It takes the first `--limit` **on-disk** photos (skipping +
reporting iCloud-offloaded ones) and refuses to clobber a populated folder without
`--force`. Replaces the retired `catalog_pipeline/images/` staging folder.

First intake step only, not the whole thing — the hero is the raw original (run
image-processor for background removal), rename `detail-N` to semantic names
(detail-back / detail-mark / detail-tag), then set final pricing and run the
rg-full-auto Square / label / publish phases.

## Database Schema

### Key Tables

| Table | Purpose |
|-------|---------|
| `ZASSET` | Main photos table (UUID, filename, dimensions, dates) |
| `ZADDITIONALASSETATTRIBUTES` | Original filename, title, camera info |
| `ZGENERICALBUM` | Albums |
| `ZSCENECLASSIFICATION` | ML scene labels |

### Key ZASSET Columns

| Column | Type | Description |
|--------|------|-------------|
| `ZUUID` | VARCHAR | Unique ID, used in file path |
| `ZFILENAME` | VARCHAR | Current filename |
| `ZDATECREATED` | TIMESTAMP | Cocoa timestamp (add 978307200 for Unix) |
| `ZWIDTH`, `ZHEIGHT` | INTEGER | Dimensions |
| `ZKIND` | INTEGER | 0=photo, 1=video |
| `ZFAVORITE` | INTEGER | 1 if favorited |
| `ZTRASHEDSTATE` | INTEGER | 0=not deleted |
| `ZHIDDEN` | INTEGER | 0=visible |
| `ZUNIFORMTYPEIDENTIFIER` | VARCHAR | File type (public.heic, public.jpeg) |

### File Path Pattern

Photos stored at:
```
Photos Library.photoslibrary/originals/[FIRST_CHAR_OF_UUID]/[UUID].[ext]
```

Example:
```
originals/5/556C8CA3-5F88-4EED-AED0-4255CBF09BC0.heic
```

### Cocoa Timestamp Conversion

Apple uses seconds since Jan 1, 2001. To convert:
```python
unix_timestamp = cocoa_timestamp + 978307200
```

In SQLite:
```sql
datetime(ZDATECREATED + 978307200, 'unixepoch', 'localtime')
```

## Common Queries

### Recent non-deleted photos
```sql
SELECT ZUUID, ZFILENAME, ZWIDTH, ZHEIGHT,
       datetime(ZDATECREATED + 978307200, 'unixepoch', 'localtime') as created
FROM ZASSET
WHERE ZTRASHEDSTATE = 0 AND ZHIDDEN = 0
ORDER BY ZDATECREATED DESC
LIMIT 20
```

### With original filename
```sql
SELECT a.ZUUID, aa.ZORIGINALFILENAME, a.ZWIDTH, a.ZHEIGHT
FROM ZASSET a
LEFT JOIN ZADDITIONALASSETATTRIBUTES aa ON a.ZADDITIONALATTRIBUTES = aa.Z_PK
WHERE a.ZTRASHEDSTATE = 0
```

### Photos from specific date range
```sql
WHERE ZDATECREATED > (strftime('%s', 'now') - 978307200 - 7*24*60*60)
```

## Product Photo Workflow

### Option A: Manual filtering
1. Query recent photos with minimum resolution:
   ```bash
   python3 scripts/query_photos.py --days 3 --min-width 1000
   ```

2. Extract to working folder:
   ```bash
   python3 scripts/extract_photos.py --days 3 --min-width 1000 --output ~/Desktop/Images/from_photos
   ```

3. Review extracted JPEGs and identify product shots

### Option B: Auto-clustering (recommended)
1. Find product photo clusters:
   ```bash
   python3 scripts/find_product_clusters.py --days 7 --type product
   ```

2. Extract only the product clusters you need based on date/time

3. The clustering algorithm identifies:
   - Portrait-oriented photos (typical product shots)
   - Grouped by shooting session (within 5 minutes)
   - Filters out screenshots and real estate photos

### Creating size variants
```bash
sips -Z 800 photo.jpeg --out photo_medium.jpeg
sips -Z 400 photo.jpeg --out photo_small.jpeg
```
