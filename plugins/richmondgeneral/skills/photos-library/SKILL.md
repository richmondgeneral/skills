---
name: photos-library
description: Query and extract photos from macOS Photos Library, sort intake photos into per-SKU libraries, and sort receipt photos into ops/receipts + the receipts ledger. Use when user asks to find recent photos, extract product photos, search by date/album/type, convert HEIC to JPEG, pull images from Photos app, sort the intake album into items, file photos into a SKU, clear the intake queue, route downloaded photos into the right album, or sort/file receipts out of the photo library. Triggers on "recent photos", "photos from last week", "extract from Photos", "product photos", "find pictures of", "pull from camera roll", "sort intake", "sort my intake photos", "file these into their SKU", "out of intake", "photos from downloads into the right album", "sort receipts", "file receipts", "receipt photos", "receipts out of the library".
metadata:
  version: "1.11"
  author: scottybe
  updated: "2026-07-15"
  changelog: |
    v1.11 - Cowork operating pattern baked in: mac-bridge-first entry point (deferred-tool
    connection check), subagent fan-out for per-item research with writes kept serial in the
    main agent (2026-06-21 experiment, now default), computer-use fallback for iCloud-offloaded
    originals (open in Photos to force download, then re-run = manifest resume).

    v1.10 - Duplicate-mint guard + live-model verification (RG-0060 void postmortem):
    - file_cluster scans items/*/.filed.json before minting — a --mint retry ADOPTS the
      already-filed SKU instead of minting a duplicate; conflicts exit 4; Void records
      are never adopted. Void-SKU recovery flow documented.
    - find_product_clusters --verify-live: filters the queue against Photos' LIVE model
      (sqlite flushes lazily; prevents the re-file trap after a fresh filing run)
    - SOP: commit new item dirs right after filing

    v1.9 - Intake filing hardened (2026-07-15 Cowork-struggle postmortem):
    - file_cluster.py tags BEFORE the album step; album add is best-effort/non-fatal
      (the flaky AppleScript used to abort pre-tag, stranding exported items in the queue)
    - per-photo tag verification + one retry (bare `try` used to swallow failures silently);
      exit 3 + tag_failed listing when photos still fail
    - .filed.json resume manifest: re-running after a bridge timeout skips exported photos
      instead of duplicating them under fresh detail-N names; [export i/n] progress on stderr
    - subprocess failures now emit stage + captured stderr as JSON (no more "errored
      without detail" over the bridge); --no-album flag

    v1.8 - Receipt sorter (agent loop):
    - find_receipts.py: queue of receipt photos via Apple's OWN ML labels in
      the Photos search index (database/search/psi.sqlite "Receipt" scene
      group; new psi_db.py reconstructs ZUUIDs from little-endian uuid_0/uuid_1
      halves; psi strings are NUL-terminated — matched via 'receipt'||char(0)).
      --hide-sorted excludes filed ones; prints ML-label coverage date.
    - file_receipt.py: the ONE canonical receipt filing step — sips-exports to
      ops/receipts/YYYY-MM-DD-<vendor>.jpeg (never clobbers), appends the row
      to ops/receipts/receipts-log.md (the lot-tracker's cost feed), adds to
      the "Receipts" album, tags rg-sorted + rg-receipt. --plan dry-runs;
      --dismiss tag-only-drops a personal receipt from the queue.
    - file_cluster.py: tag_keywords() extracted (tag_sorted now wraps it).
    - Photos labels lazily (overnight/on-power) — a freshly shot receipt may
      take a day to appear in the queue.
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
   Exports to `items/RG-XXXX/` (hero + detail-N, no clobber), tags `rg-sorted` + `RG-XXXX`
   (verified per-photo, one automatic retry), then adds to the per-SKU album **best-effort**
   (the album AppleScript is known-flaky; a failure is a warning, never an abort — tagging
   happens FIRST so the queue always clears). Minting is atomic (Square-CAS) and hard-fails
   offline.

   **Timeout / interruption? Just re-run the SAME command.** A `.filed.json` manifest in the
   item dir records uuid→file; a re-run skips already-exported photos (no duplicate detail-N),
   re-tags idempotently, and finishes what's left. Per-photo `[export i/n]` progress goes to
   stderr — over the bridge, always capture it (`2>&1`) and for big clusters (>8 photos) expect
   to re-run once or twice rather than raising the bridge timeout.

   Exit codes: `0` = filed (album warning possible — check `album.warning` in the JSON);
   `3` = some photos failed tagging even after retry (`tag_failed` lists them — re-run, or
   `--tag-only` those uuids). `--no-album` skips the album step entirely.

   For a cluster that belongs to an **already-photographed** item (just clear it from the queue and
   label it by SKU — no new `items/` photos), tag without exporting:
   ```bash
   python3 scripts/file_cluster.py --tag-only --sku RG-00NN --uuids <uuids>
   ```

**Cowork entry point: load `mac-bridge` FIRST.** Every command in this skill runs on the Mac.
From Cowork, load the `mac-bridge` skill before anything else — it has the connection-check
protocol (the osascript tool is usually DEFERRED, not disconnected; ToolSearch it before telling
the user to toggle the extension).

**Intake at scale = subagent fan-out (reads) + serial writes (proven 2026-06-21).** After the
sweep, the MAIN agent segments each cluster into items and assigns explicit UUIDs. Then:
- **Fan out one READ-ONLY subagent per item** for the slow cognitive work: identify → hero pick →
  condition → estimates block → web comps (subagents must load WebSearch via ToolSearch) →
  photo-gap flags → blockers. Subagents mint/write/tag/commit NOTHING.
- **All writes stay serial in the main agent**: SKU mint (CAS authority), `file_cluster` runs,
  tagging, git commits, Square. Two writers on the bridge/Photos/git is how duplicate-SKU and
  half-tagged states happen — the bridge is a single-lane road.
- Main agent reviews each subagent draft against the definition-of-done, then executes.

**iCloud-offloaded originals — computer-use fallback.** `file_cluster` reports offloaded uuids
(original not on disk) and skips them. Scripting cannot force the download; the fix is UI:
with **computer-use** (Photos is a native app = full tier), open Photos, search the UUID or
locate the photo (the intake album/date view), open it full-screen so Photos fetches the
original, wait for the download badge to clear, then re-run the SAME `file_cluster` command —
the manifest resume picks up just the newly available photos. If computer-use isn't granted,
hand the user the photo list and ask them to open each once.

**Duplicate-mint guard + Void-SKU recovery.** `file_cluster` scans every item's `.filed.json`
before minting: if any of the cluster's uuids were already filed, it **adopts that SKU** (no new
mint) — so a `--mint` retry after a crash can no longer create an RG-0060-style duplicate. If the
uuids span two SKUs, or `--sku` disagrees with where the photos already live, it exits 4 with the
conflict instead of filing a duplicate. In the RARE case a duplicate record still exists
(discovered later): the **earlier-filed SKU stays live**; the extra record gets
`label.json → state: "Void"` plus a `void: {reason, superseded_by, date}` note (RG-0033/RG-0060
precedent). Voided SKU numbers are never reused (sequence gaps are fine), voided dirs never get a
gallery card or listing, and the guard skips Void records when adopting.

**Fresh tags lag the sqlite — use `--verify-live` after filing.** Photos flushes keyword writes
to Photos.sqlite lazily (can be minutes), so a sweep run right after filing may re-report
just-tagged photos as unsorted. Do NOT re-file them — re-run the sweep with
`find_product_clusters.py --hide-sorted --verify-live`, which also checks Photos' live model and
hides photos already rg-sorted there.

**After filing: commit the new item dirs** (`git -C items add items/RG-XXXX && commit` — explicit
paths, worktree-safe per CLAUDE.md multi-writer rules). Exported photos + label stubs sitting
uncommitted are one reset away from re-doing the whole sweep.

**"Out of the queue" = the `rg-sorted` tag + `--hide-sorted` filter.** Filing tags each photo
`rg-sorted` + `RG-XXXX`, and the sweep (step 1) excludes `rg-sorted`, so a filed photo instantly
drops out of the queue — no album to empty, no structural mutation. The photos just stay in your
library, now carrying their SKU in keywords (searchable by `RG-XXXX`). This additive tag-sweep model
replaced the rejected album-rebuild approach (Photos' async album deletion is unreliable — see changelog).

## Receipt Sorter (agent loop — ML-labeled queue)

Receipts from buying trips get photographed alongside products. Photos' own ML
labels them (no aspect-ratio guessing — a photographed receipt is a normal 4:3
photo; only ML/vision can see the receipt inside the frame); this loop files
them into `ops/receipts/` + the ledger so the lot-tracker sees every cost.
Same shape as the item sorter: sweep → look → confirm → file.

1. **Sweep the queue** — receipt-labeled photos, already-filed excluded:
   ```bash
   python3 scripts/find_receipts.py --hide-sorted --days 30 --json
   ```
   ⚠️ Photos labels lazily (overnight / on power): the output's
   `newest_labeled` date shows coverage — a receipt shot today may not be in
   the queue until tomorrow.

2. **Look at each candidate** (real vision) — confirm it IS a purchase receipt
   and READ vendor / date / total off it (use the FULL uuids from the JSON):
   ```bash
   python3 scripts/extract_photos.py --uuids <uuid,…> --resize 1024x1024 -o /tmp/rg-receipts
   ```

3. **Confirm with the user** — vendor, date, total, lot code (if this receipt
   belongs to a tracked lot, e.g. GIBA-C2). Multi-page receipt = one filing
   with several uuids. Personal (non-business) receipts: dismiss so the queue
   stays clean —
   ```bash
   python3 scripts/file_receipt.py --dismiss --uuids <uuids>
   ```
   (tags `rg-sorted` + `rg-receipt` only; no export, no ledger, no album).

4. **File it** — the ONE canonical step (dry-run first if unsure):
   ```bash
   python3 scripts/file_receipt.py --plan --uuids <uuids> --vendor "Goodwill" --total 12.99
   python3 scripts/file_receipt.py --uuids <uuids> --vendor "Goodwill" \
       --total 12.99 [--date YYYY-MM-DD] [--lot GIBA-C2]
   ```
   Exports to `ops/receipts/YYYY-MM-DD-<vendor>.jpeg`, appends the row to
   `ops/receipts/receipts-log.md`, adds to the "Receipts" album under
   "Richmond General Archive", and tags `rg-sorted` + `rg-receipt` — the photo
   drops out of this queue AND the item intake sweep. After filing, offer to
   record the cost against the lot (rg-lot-tracker).

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
