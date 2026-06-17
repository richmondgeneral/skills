#!/usr/bin/env python3
"""Extract and convert photos from macOS Photos Library."""

import argparse
import sqlite3
import subprocess
import os
from pathlib import Path

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
                   limit=20, output_format='jpeg', quality=90, resize=None):
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
        
        if days:
            conditions.append(f"a.ZDATECREATED > (strftime('%s', 'now') - {COCOA_EPOCH_OFFSET} - ? * {SECONDS_PER_DAY})")
            params.append(days)
        if min_width:
            conditions.append("a.ZWIDTH >= ?")
            params.append(min_width)
        if favorites_only:
            conditions.append("a.ZFAVORITE = 1")

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

    extracted = []
    for row in rows:
        uuid, file_type, orig_name, width, height, created = row

        ext = file_type.split('.')[-1] if file_type else "heic"
        first_char = uuid[0].upper()
        src_path = os.path.join(library_path, f"originals/{first_char}/{uuid}.{ext}")

        if not os.path.exists(src_path):
            print(f"✗ Not found: {orig_name or uuid[:8]}")
            continue

        # Determine output filename
        if orig_name:
            base_name = os.path.splitext(orig_name)[0]
        else:
            base_name = uuid[:8]

        out_name = f"{base_name}.{output_format}"
        dst_path = os.path.join(output_dir, out_name)

        # Build convert command
        cmd = ['convert', src_path]

        if resize:
            cmd.extend(['-resize', resize])

        cmd.extend(['-quality', str(quality), dst_path])

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
            print(f"✗ Failed: {orig_name or uuid[:8]} - {e.stderr.decode()[:50] if e.stderr else 'unknown error'}")
        except FileNotFoundError:
            print("✗ ImageMagick 'convert' not found. Install with: brew install imagemagick")
            return extracted  # Exit early, don't process remaining photos
        except (OSError, PermissionError) as e:
            print(f"✗ {orig_name or uuid[:8]}: {e}")
            continue  # Skip this photo, try next

    return extracted

def main():
    parser = argparse.ArgumentParser(description='Extract photos from macOS Photos Library')
    parser.add_argument('--days', type=int, default=7, help='Photos from last N days (ignored if --favorites without --days)')
    parser.add_argument('--min-width', type=int, default=0, help='Minimum width in pixels')
    parser.add_argument('--favorites', action='store_true', help='Only favorited photos')
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

    # If --favorites is used without explicit --days, remove the day filter
    days_filter = args.days
    if args.favorites and '--days' not in ' '.join(os.sys.argv):
        days_filter = None  # No day restriction for favorites

    library_path = args.library or find_photos_library()
    if not library_path:
        print("Error: Could not find Photos Library")
        return 1

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
        resize=args.resize
    )

    print(f"\nExtracted {len(extracted)} photos to {args.output}")
    return 0

if __name__ == '__main__':
    exit(main())
