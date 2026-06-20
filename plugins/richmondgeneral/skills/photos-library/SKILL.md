---
name: photos-library
description: Query and extract photos from macOS Photos Library, and sort intake photos into per-SKU libraries. Use when user asks to find recent photos, extract product photos, search by date/album/type, convert HEIC to JPEG, pull images from Photos app, sort the intake album into items, file photos into a SKU, clear the intake queue, or route downloaded photos into the right album. Triggers on "recent photos", "photos from last week", "extract from Photos", "product photos", "find pictures of", "pull from camera roll", "sort intake", "sort my intake photos", "file these into their SKU", "out of intake", "photos from downloads into the right album".
metadata:
  version: "1.7"
  author: scottybe
  updated: "2026-06-19"
  changelog: |
    v1.7 - Intake photo sorter (agent loop) + downloads router:
    - file_cluster.py: the ONE canonical filing step — mints (sku_authority) or
      uses a SKU, exports a cluster's originals into items/RG-XXXX/ (hero +
      detail-N, never clobbering an existing hero via sips), adds them to the
      per-SKU Photos album (archive_to_album.scpt, idempotent), and tags them
      rg-sorted + RG-XXXX. --plan dry-runs with zero mutations; offloaded
      originals are reported, not filed.
    - extract_photos.py --uuids: render one specific cluster for the agent to look
      at (vision); original_relpath() in photos_db.py shares the on-disk path math.
    - find_product_clusters.py --hide-sorted / --exclude-keyword
      (exclude_keyword_condition in photos_db.py): the intake QUEUE excludes
      rg-sorted photos, so once a cluster is filed it drops out of the sorter's
      view. This is how "out of Intake" works — RELIABLY, with no album mutation.
    - import_to_photos.scpt: import ~/Downloads files into a Photos album (creates
      it under the "Richmond General" folder if needed).
    - NOTE: a PhotoKit/AppleScript "rebuild the Intake album" approach was tried
      and REJECTED — Photos' async album deletion creates duplicate albums and
      breaks references. Keyword tag + --hide-sorted queue filter replaced it.
      Physical photos stay in Intake until you mass-delete them by hand.

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
count + filenames, never silently skipped. Materialize them the **image-only** way:
in Photos select → File ▸ "Download Originals" (keeps them in-library, no video
sidecars), then re-run. **Do not "Export Unmodified Originals" to a folder** — Live
Photos emit a ~5 MB `.mov` each (≈1 GB/session of bloat); if you already did, strip
them with `intake_cleanup.py prune-sidecars <dir> --apply`.

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

### `scripts/intake_cleanup.py` — intake scratch hygiene

Two safeguards against intake bloat (the 2026-06-19 audit found ~1 GB/session of
Live Photo `.mov` sidecars piling up in scratch, never cleaned up):

```bash
# A) Drop Live Photo .mov sidecars — only ones with a still twin (real videos kept).
#    Safe anytime, on any export/staging folder. Dry-run unless --apply.
python3 scripts/intake_cleanup.py prune-sidecars rg-pending/RG-0028 --apply

# B) Sweep a DONE item's scratch (rg-pending/<sku> + legacy ops/_intake_*).
#    Fires ONLY when label.json state is Sold/Archived; a Listed item with open
#    photo follow-ups is skipped. Dry-run unless --apply.
python3 scripts/intake_cleanup.py sweep --sku RG-0028 --items-dir ../items \
    --extra ../ops/_intake_dishes3 --apply
```

**Definition of done:** run `prune-sidecars` on any export folder before processing,
and `sweep` once the item is terminal, so scratch never accumulates. Both are
importable (`prune_live_photo_sidecars`, `sweep_intake_scratch`) for rg-full-auto wiring.

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

## Intake Photo Sorter (agent loop — library-wide tag sweep, NO album)

**No Intake album to manage.** Shoot product photos normally with the Camera app; the sorter sweeps
the recent library, finds product shots, and tags them on filing so they vanish from the queue.
The loop files each item's photos into its SKU lib — the per-SKU Photos album AND `items/RG-XXXX/` —
as: sweep → look → propose → confirm → file.

1. **Sweep the queue** — last **3 days** of the library (default), product shots only, already-sorted excluded:
   ```bash
   python3 scripts/find_product_clusters.py --hide-sorted --type product --json
   ```
   No `--album` needed. Item-by-item shooting → each time-gap cluster ≈ one item. Add `--days N`
   to widen the window. (The only risk: the ML heuristic occasionally grabs a personal photo that
   looks like a product — you confirm each cluster before filing, so it's caught there.)

2. **Look at each cluster** — extract small JPEGs and Read them (real vision):
   ```bash
   python3 scripts/extract_photos.py --uuids <uuid1,uuid2,…> --resize 1024x1024 -o /tmp/rg-cluster
   ```
   Offloaded originals are reported — offer to download them in Photos first.

3. **Match + propose.** Cross-reference `items/RG-XXXX/` heroes + `label.json`. Per cluster,
   propose *"matches RG-00NN → add as details"* or *"new item → mint next RG-XXXX"*, with a reason.

4. **Confirm with the user** per cluster (accept / different SKU / skip).

5. **File the cluster** — the ONE canonical step (dry-run first if unsure):
   ```bash
   python3 scripts/file_cluster.py --plan --uuids <uuids> [--sku RG-00NN | --mint]
   python3 scripts/file_cluster.py --uuids <uuids> [--sku RG-00NN | --mint] \
       [--role <uuid>=hero] [--role <uuid>=detail-back]
   ```
   Exports to `items/RG-XXXX/` (hero + detail-N, no clobber), adds to the per-SKU album, and tags
   `rg-sorted` + `RG-XXXX`. Minting is atomic (Square-CAS) and hard-fails offline.

   For a cluster that belongs to an **already-photographed** item (just clear it from the queue and
   label it by SKU — no new `items/` photos), tag without exporting:
   ```bash
   python3 scripts/file_cluster.py --tag-only --sku RG-00NN --uuids <uuids>
   ```

**"Out of the queue" = the `rg-sorted` tag + `--hide-sorted` filter.** Filing tags each photo
`rg-sorted` + `RG-XXXX`, and the sweep (step 1) excludes `rg-sorted`, so a filed photo instantly
drops out of the queue — no album to empty, no structural mutation. The photos just stay in your
library, now carrying their SKU in keywords (searchable by `RG-XXXX`). This additive tag-sweep model
replaced the rejected album-rebuild approach (Photos' async album deletion is unreliable — see changelog).

## Downloads → Album (agent decides per photo)

Route `~/Downloads` photos into the right Photos album.

1. List `~/Downloads` images; convert HEIC to a temp JPEG so you can Read/look at each.
2. Route per photo (vision): product shot → "Richmond General Intake" (or, if it clearly matches a
   live SKU, that SKU's album); non-product → leave it alone.
3. Confirm the routing with the user.
4. Import:
   ```bash
   osascript scripts/import_to_photos.scpt "Richmond General Intake" <file1> <file2> …
   ```
   Product imports land in Intake → the Intake Photo Sorter above takes over.

### Safety
- All DB reads use `mode=ro&immutable=1` (never disturbs iCloud sync).
- Irreversible steps (mint, import, file) run only after per-cluster confirmation.
- Re-runs are safe: album membership dedupes; existing `items/` photos are never clobbered.
