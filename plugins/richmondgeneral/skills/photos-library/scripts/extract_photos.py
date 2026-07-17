#!/usr/bin/env python3
"""Extract and convert photos from macOS Photos Library."""

import argparse
import sqlite3
import subprocess
import os
from pathlib import Path

import photos_db

def find_photos_library():
    """Find Photos Library path."""
    paths = [
        Path.home() / "Pictures/Photos Library.photoslibrary",
    ]
    for p in paths:
        if p.exists():
            return str(p)
    return None

def extract_photos(library_path, output_dir, days=7, min_width=0, favorites_only=False,
                   limit=20, output_format='jpeg', quality=90, resize=None,
                   album=None, keyword=None, uuids=None):
    """Extract photos from library to output directory."""
    # Constants
    COCOA_EPOCH_OFFSET = 978307200  # Seconds between Unix epoch (1970) and Cocoa epoch (2001)
    SECONDS_PER_DAY = 86400

    db_path = os.path.join(library_path, "database/Photos.sqlite")
    if not os.path.exists(db_path):
        print(f"Error: Database not found at {db_path}")
        return []

    os.makedirs(output_dir, exist_ok=True)

    # Open the live Photos library read-only AND immutable so we never take
    # locks or touch the WAL — anything less can disrupt cloudphotod's sync
    # state tracking and force a full iCloud re-pull.
    with sqlite3.connect(f"file:{db_path}?mode=ro&immutable=1", uri=True) as conn:
        cursor = conn.cursor()

        conditions = ["a.ZTRASHEDSTATE = 0", "a.ZHIDDEN = 0", "a.ZKIND = 0"]
        params = []

        # --uuids selects by ZUUID membership (like --album, by identity not
        # recency), so it bypasses the day window. Parameterize every UUID —
        # never string-interpolate them into the SQL.
        if uuids:
            placeholders = ",".join("?" for _ in uuids)
            conditions.append(f"a.ZUUID IN ({placeholders})")
            params.extend(uuids)
            days = None
        if days:
            conditions.append(f"a.ZDATECREATED > (strftime('%s', 'now') - {COCOA_EPOCH_OFFSET} - ? * {SECONDS_PER_DAY})")
            params.append(days)
        if min_width:
            conditions.append("a.ZWIDTH >= ?")
            params.append(min_width)
        if favorites_only:
            conditions.append("a.ZFAVORITE = 1")
        if album:
            frag, frag_params = photos_db.album_condition(conn, album)
            conditions.append(frag)
            params.extend(frag_params)
        if keyword:
            frag, frag_params = photos_db.keyword_condition(conn, keyword)
            conditions.append(frag)
            params.extend(frag_params)

        where_clause = " AND ".join(conditions)

        query = f"""
        SELECT
            a.ZUUID,
            a.ZUNIFORMTYPEIDENTIFIER as file_type,
            aa.ZORIGINALFILENAME,
            a.ZWIDTH,
            a.ZHEIGHT,
            datetime(a.ZDATECREATED + {COCOA_EPOCH_OFFSET}, 'unixepoch', 'localtime') as created
        FROM ZASSET a
        LEFT JOIN ZADDITIONALASSETATTRIBUTES aa ON a.ZADDITIONALATTRIBUTES = aa.Z_PK
        WHERE {where_clause}
        ORDER BY a.ZDATECREATED DESC
        LIMIT ?
        """

        params.append(limit)
        cursor.execute(query, params)
        rows = cursor.fetchall()

    # With --uuids, flag any requested UUID the DB returned no row for (typo /
    # not in this library / trashed/hidden) so it's reported, never silently
    # dropped. ZUUID is upper-case in Photos; compare case-insensitively.
    not_found = []
    if uuids:
        seen = {r[0].lower() for r in rows}
        not_found = [u for u in uuids if u.lower() not in seen]

    extracted = []
    offloaded = []  # originals not on disk (iCloud-offloaded) — reported, never silently skipped
    for row in rows:
        uuid, file_type, orig_name, width, height, created = row

        # Path of the on-disk original (originals/<FIRST_CHAR>/<uuid>.<ext>) —
        # shared helper keeps this layout DRY with intake_to_item.py.
        src_path = os.path.join(library_path, photos_db.original_relpath(uuid, file_type))

        if not os.path.exists(src_path):
            # Original isn't on local disk — almost always iCloud-offloaded
            # ("Optimize Mac Storage"). Track it so we report the full set at
            # the end instead of silently skipping (which hid intake photos).
            offloaded.append(orig_name or uuid[:8])
            print(f"☁︎ Offloaded (not on disk): {orig_name or uuid[:8]}")
            continue

        # Determine output filename. With --uuids, name by UUID prefix so the
        # caller can map a file back to the asset it requested; otherwise keep
        # the original filename's base (falling back to the UUID prefix).
        if uuids or not orig_name:
            base_name = uuid[:8]
        else:
            base_name = os.path.splitext(orig_name)[0]

        out_name = f"{base_name}.{output_format}"
        dst_path = os.path.join(output_dir, out_name)

        # Convert with macOS-native `sips` — no Homebrew/ImageMagick needed.
        # sips reads HEIC and writes jpeg/png directly.
        cmd = ['sips', '-s', 'format', output_format]
        if output_format == 'jpeg':
            # formatOptions takes a 0–100 JPEG quality (lossless PNG ignores it)
            cmd.extend(['-s', 'formatOptions', str(quality)])
        if resize:
            # `sips -Z` bounds the longest side and preserves aspect ratio.
            # --resize is WxH (validated); use the larger dimension so the
            # result fits within the WxH box.
            w, h = (int(n) for n in resize.lower().split('x'))
            cmd.extend(['-Z', str(max(w, h))])
        cmd.extend([src_path, '--out', dst_path])

        try:
            subprocess.run(cmd, check=True, capture_output=True)
            print(f"✓ {orig_name or uuid[:8]} → {out_name} ({width}x{height})")
            extracted.append({
                'source': src_path,
                'output': dst_path,
                'original_name': orig_name,
                'width': width,
                'height': height,
                'created': created
            })
        except subprocess.CalledProcessError as e:
            print(f"✗ Failed: {orig_name or uuid[:8]} - {e.stderr.decode()[:80] if e.stderr else 'sips error'}")
            continue  # per-file failure (e.g. corrupt original): skip, keep going
        except FileNotFoundError:
            print("✗ 'sips' not found — this script requires macOS (sips is built in).")
            return extracted  # nothing will convert without sips
        except (OSError, PermissionError) as e:
            print(f"✗ {orig_name or uuid[:8]}: {e}")
            continue  # Skip this photo, try next

    # Report offloaded originals clearly — never silently skip (that hid intake
    # photos in the first batch). Tell the user how to materialize them.
    if offloaded:
        print(f"\n☁︎ {len(offloaded)} original(s) offloaded to iCloud (not on disk):")
        for name in offloaded:
            print(f"    - {name}")
        print('  Best (image-only): in Photos select → File ▸ "Download Originals"')
        print("  (keeps them in-library, no video sidecars), then re-run — this stays image-only.")
        print("  Do NOT 'Export Unmodified Originals' to a folder: Live Photos add a ~5MB .mov")
        print("  each (≈1GB/session). If you did, strip them: intake_cleanup.py prune-sidecars <dir> --apply")
        print("  (or osxphotos export --download-missing --skip-live --skip-raw).")

    # Requested UUIDs that matched no asset at all — surface, never silently drop.
    if not_found:
        print(f"\n⚠️  {len(not_found)} requested UUID(s) not found in this library "
              f"(typo / trashed / hidden / different library):")
        for u in not_found:
            print(f"    - {u}")

    return extracted

def main():
    parser = argparse.ArgumentParser(description='Extract photos from macOS Photos Library')
    parser.add_argument('--days', type=int, default=7, help='Photos from last N days (ignored if --favorites/--album/--keyword without --days)')
    parser.add_argument('--min-width', type=int, default=0, help='Minimum width in pixels')
    parser.add_argument('--favorites', action='store_true', help='Only favorited photos')
    parser.add_argument('--album', type=str, help='Only photos in this album (matches album name, e.g. "Intake")')
    parser.add_argument('--keyword', '--tag', dest='keyword', type=str, help='Only photos with this keyword/tag')
    parser.add_argument('--uuids', type=str, help='Comma-separated ZUUIDs to extract (selects by UUID, bypasses --days)')
    parser.add_argument('--limit', type=int, default=20, help='Max photos to extract')
    parser.add_argument('--output', '-o', type=str, required=True, help='Output directory')
    parser.add_argument('--format', type=str, default='jpeg', choices=['jpeg', 'png'], help='Output format')
    parser.add_argument('--quality', type=int, default=90, help='JPEG quality (1-100)')
    parser.add_argument('--resize', type=str, help='Resize to max dimensions (e.g., 800x800)')
    parser.add_argument('--library', type=str, help='Path to Photos Library (auto-detected if not specified)')

    args = parser.parse_args()

    # Input validation
    if args.limit < 1:
        print("Error: --limit must be at least 1")
        return 1
    if args.min_width < 0:
        print("Error: --min-width cannot be negative")
        return 1
    if args.days and args.days < 0:
        print("Error: --days cannot be negative")
        return 1
    if not 1 <= args.quality <= 100:
        print("Error: --quality must be between 1 and 100")
        return 1
    if args.resize:
        import re
        if not re.match(r'^\d+x\d+$', args.resize):
            print("Error: --resize must be in format WxH (e.g., 800x800)")
            return 1

    # Parse --uuids into a clean list (drop blanks/whitespace from the CSV).
    uuid_list = [u.strip() for u in args.uuids.split(',') if u.strip()] if args.uuids else None
    if args.uuids and not uuid_list:
        print("Error: --uuids was empty")
        return 1

    # If --favorites/--album/--keyword/--uuids is used without an explicit --days,
    # drop the day filter — these select by membership/identity, not recency.
    days_filter = args.days
    if (args.favorites or args.album or args.keyword or uuid_list) and '--days' not in ' '.join(os.sys.argv):
        days_filter = None

    library_path = args.library or find_photos_library()
    if not library_path:
        print("Error: Could not find Photos Library")
        return 1

    # Warn early if a named album/keyword doesn't exist (avoids a silent 0).
    if args.album or args.keyword:
        _db = os.path.join(library_path, "database/Photos.sqlite")
        with sqlite3.connect(f"file:{_db}?mode=ro&immutable=1", uri=True) as _c:
            if args.album and not photos_db.album_exists(_c, args.album):
                print(f"⚠️  Album '{args.album}' not found. Known: {', '.join(photos_db.list_albums(_c, 15))}", file=os.sys.stderr)
            if args.keyword and not photos_db.keyword_exists(_c, args.keyword):
                print(f"⚠️  Keyword/tag '{args.keyword}' not found.", file=os.sys.stderr)

    print(f"Extracting from: {library_path}")
    print(f"Output to: {args.output}\n")

    extracted = extract_photos(
        library_path,
        args.output,
        days=days_filter,
        min_width=args.min_width,
        favorites_only=args.favorites,
        limit=args.limit,
        output_format=args.format,
        quality=args.quality,
        resize=args.resize,
        album=args.album,
        keyword=args.keyword,
        uuids=uuid_list
    )

    print(f"\nExtracted {len(extracted)} photos to {args.output}")
    return 0

if __name__ == '__main__':
    exit(main())
