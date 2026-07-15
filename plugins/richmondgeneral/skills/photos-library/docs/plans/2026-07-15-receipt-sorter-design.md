# Receipt Sorter — photos-library v1.8 (design)

Date: 2026-07-15. Approved by owner (destination: `ops/receipts/` by date; vision
data-extract into a receipts ledger: yes).

## Problem

Receipt photos (thrift/estate/auction purchases) pile up in the Photos library mixed
with product shots. Items already have a sweep→look→confirm→file loop
(`find_product_clusters.py` → `file_cluster.py`); receipts have nothing — they linger
in the intake sweep as noise and their financial data never reaches the lot-tracker.

## Detection: Apple's ML labels, not aspect-ratio heuristics

The item classifier guesses from photo dimensions. Receipts don't need guessing —
Photos' on-device ML already labels them. The search index
`~/Pictures/Photos Library.photoslibrary/database/search/psi.sqlite` (open with
`mode=ro&immutable=1`, same safety rule as Photos.sqlite) contains:

- `groups`: `content_string='Receipt'` category **1500** (scene label; 282 assets in
  the owner's library on 2026-07-15) and `'Receipts'` category **2800** (278 assets).
  ⚠️ `content_string` values carry a **trailing NUL byte** — match on
  `normalized_string` (`'receipt'`/`'receipts'`) instead.
- `ga(groupid, assetid)`: group→asset join.
- `assets(uuid_0, uuid_1)`: the asset UUID as two **little-endian signed 64-bit
  halves**. Reconstruct: `uuid.UUID(bytes=struct.pack('<q', uuid_0) + struct.pack('<q', uuid_1))`,
  uppercased = `ZASSET.ZUUID`. Verified against a live 2026-06-16 receipt photo.

Caveat (document in SKILL.md): Photos runs its labeler lazily (overnight / on power),
so a receipt shot minutes ago may not be labeled yet. The sweep prints the newest
labeled-asset date so the operator knows the coverage window; a `--days` vision sweep
of unlabeled photos remains the manual fallback.

## Components

### `scripts/find_receipts.py` — the queue

Union of the two receipt groups from psi.sqlite → UUIDs → cross into Photos.sqlite
for filename, created date, dims, on-disk path (reuse `photos_db.py` helpers).
Filters: `--days N` (default 30), `--hide-sorted` (exclude keyword `rg-sorted`,
same mechanics as the item sweep), `--json`. Output newest-first. Exit 0 with an
empty list is normal.

### `scripts/file_receipt.py` — the ONE canonical filing step

Mirrors `file_cluster.py`'s role but with none of the SKU machinery (no mint, no
`label.json`, no items dir). Args: `--uuids` (comma-separated ZUUIDs),
`--vendor` (required), `--date YYYY-MM-DD` (default: photo creation date),
`--total` (e.g. `12.99`, optional-but-urged), `--lot` (optional lot code, e.g.
`GIBA-C2`), `--ops-dir` (default `~/workspace/richmondgeneral/ops`), `--plan` dry-run.

Filing does four things:
1. **Export** on-disk originals via `sips` → `ops/receipts/YYYY-MM-DD-<vendor-slug>.jpeg`
   (multi-photo: `-2`, `-3`… suffixes; never clobbers an existing file — bump suffix).
2. **Ledger**: append a row to `ops/receipts/receipts-log.md`
   (`| date | vendor | total | lot | file | uuids |`; create file with header if
   absent). This is the lot-tracker's feed for cost entry.
3. **Album**: add the photos to a **"Receipts"** album under "Richmond General
   Archive" (reuse `archive_to_album.scpt` — its first arg is any album name).
4. **Tag** `rg-sorted` + `rg-receipt` (generalize `file_cluster.tag_sorted` into a
   shared keyword-union helper) — the photo drops out of BOTH the receipt queue and
   the item intake sweep.

Offloaded (iCloud) originals: reported, not filed — same as the item flow.

### SKILL.md — "Receipt Sorter" agent loop (new section), v1.7 → v1.8

sweep (`find_receipts.py --hide-sorted --json`) → look
(`extract_photos.py --uuids … --resize 1024x1024`, real vision: confirm it IS a
receipt, read vendor/date/total off it) → confirm with the user → `file_receipt.py`.
Multi-page receipts = one filing with several uuids.

## Testing

Pure logic unit-tested (pattern of `test_file_cluster.py`): psi UUID reconstruction,
receipt filename planning (slug, suffixes, no-clobber), ledger row append/create.
Photos/sips side effects stay in the integration path, skipped by `--plan`.

## Rollout

Plugin marketplace loop per CLAUDE.md: bump plugin.json version, `claude plugin
validate .`, commit/push skills, `claude plugin marketplace update richmondgeneral
&& claude plugin update richmondgeneral@richmondgeneral`.

## Rejected alternatives

- **Extend find_product_clusters/file_cluster with a receipt mode** — those are
  SKU-shaped (mint, label.json, items dir); receipts share almost nothing.
- **SKILL.md-only workflow (no scripts)** — fragile inline SQL, untestable.
- **Aspect-ratio heuristic** — a photographed receipt is a normal 4:3 photo; the
  receipt shape is inside the frame. Only ML/vision can see it.
