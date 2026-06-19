#!/usr/bin/env python3
"""Query macOS Photos Library metadata."""

import argparse
import sqlite3
import os
import json
from pathlib import Path

import photos_db

def find_photos_db():
    """Find Photos Library database."""
    paths = [
        Path.home() / "Pictures/Photos Library.photoslibrary/database/Photos.sqlite",
    ]
    for p in paths:
        if p.exists():
            return str(p)
    return None

def query_photos(db_path, days=7, min_width=0, favorites_only=False, limit=20,
                 album=None, keyword=None, output_format='table'):
    """Query photos from the database."""
    # Constants
    COCOA_EPOCH_OFFSET = 978307200  # Seconds between Unix epoch (1970) and Cocoa epoch (2001)
    SECONDS_PER_DAY = 86400
    
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
            a.ZFILENAME,
            datetime(a.ZDATECREATED + {COCOA_EPOCH_OFFSET}, 'unixepoch', 'localtime') as created,
            a.ZWIDTH,
            a.ZHEIGHT,
            a.ZUNIFORMTYPEIDENTIFIER as file_type,
            a.ZFAVORITE,
            aa.ZORIGINALFILENAME
        FROM ZASSET a
        LEFT JOIN ZADDITIONALASSETATTRIBUTES aa ON a.ZADDITIONALATTRIBUTES = aa.Z_PK
        WHERE {where_clause}
        ORDER BY a.ZDATECREATED DESC
        LIMIT ?
        """

        params.append(limit)
        cursor.execute(query, params)
        rows = cursor.fetchall()

    photos = []
    for row in rows:
        uuid, filename, created, width, height, file_type, favorite, orig_name = row
        ext = file_type.split('.')[-1] if file_type else "heic"
        first_char = uuid[0].upper()

        photos.append({
            'uuid': uuid,
            'filename': orig_name or filename or uuid,
            'created': created,
            'width': width,
            'height': height,
            'type': ext,
            'favorite': bool(favorite),
            'path': f"originals/{first_char}/{uuid}.{ext}"
        })

    return photos

def main():
    parser = argparse.ArgumentParser(description='Query macOS Photos Library')
    parser.add_argument('--days', type=int, default=7, help='Photos from last N days (ignored if --favorites/--album/--keyword without --days)')
    parser.add_argument('--min-width', type=int, default=0, help='Minimum width in pixels')
    parser.add_argument('--favorites', action='store_true', help='Only favorited photos')
    parser.add_argument('--album', type=str, help='Only photos in this album (matches album name, e.g. "Intake")')
    parser.add_argument('--keyword', '--tag', dest='keyword', type=str, help='Only photos with this keyword/tag')
    parser.add_argument('--limit', type=int, default=20, help='Max results')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    parser.add_argument('--db', type=str, help='Path to Photos.sqlite (auto-detected if not specified)')

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

    # If --favorites/--album/--keyword is used without an explicit --days, drop
    # the day filter — these select by membership/tag, not recency.
    days_filter = args.days
    if (args.favorites or args.album or args.keyword) and '--days' not in ' '.join(os.sys.argv):
        days_filter = None

    db_path = args.db or find_photos_db()
    if not db_path:
        print("Error: Could not find Photos Library database")
        return 1

    # Warn early if a named album/keyword doesn't exist (avoids a silent 0 result).
    if args.album or args.keyword:
        with sqlite3.connect(f"file:{db_path}?mode=ro&immutable=1", uri=True) as _c:
            if args.album and not photos_db.album_exists(_c, args.album):
                hint = ", ".join(photos_db.list_albums(_c, 15))
                print(f"⚠️  Album '{args.album}' not found. Known albums: {hint}", file=os.sys.stderr)
            if args.keyword and not photos_db.keyword_exists(_c, args.keyword):
                print(f"⚠️  Keyword/tag '{args.keyword}' not found.", file=os.sys.stderr)

    photos = query_photos(
        db_path,
        days=days_filter,
        min_width=args.min_width,
        favorites_only=args.favorites,
        limit=args.limit,
        album=args.album,
        keyword=args.keyword
    )

    if args.json:
        print(json.dumps(photos, indent=2))
    else:
        days_str = f"last {days_filter} days" if days_filter else "all time"
        fav_str = ", favorites only" if args.favorites else ""
        alb_str = f", album='{args.album}'" if args.album else ""
        kw_str = f", tag='{args.keyword}'" if args.keyword else ""
        print(f"Found {len(photos)} photos ({days_str}, min_width={args.min_width}{fav_str}{alb_str}{kw_str})\n")
        print(f"{'Filename':<35} {'Created':<20} {'Size':<12} {'Type'}")
        print("-" * 80)
        for p in photos:
            size = f"{p['width']}x{p['height']}"
            fav = "★" if p['favorite'] else ""
            fname = p['filename'][:32] + "..." if len(p['filename']) > 35 else p['filename']
            print(f"{fname:<35} {p['created']:<20} {size:<12} {p['type']} {fav}")

    return 0

if __name__ == '__main__':
    exit(main())
