#!/usr/bin/env python3
"""Query macOS Photos Library metadata."""

import argparse
import sqlite3
import os
import json
from pathlib import Path

def find_photos_db():
    """Find Photos Library database."""
    paths = [
        Path.home() / "Pictures/Photos Library.photoslibrary/database/Photos.sqlite",
    ]
    for p in paths:
        if p.exists():
            return str(p)
    return None

def query_photos(db_path, days=7, min_width=0, favorites_only=False, limit=20, output_format='table'):
    """Query photos from the database."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    conditions = ["a.ZTRASHEDSTATE = 0", "a.ZHIDDEN = 0", "a.ZKIND = 0"]

    if days:
        conditions.append(f"a.ZDATECREATED > (strftime('%s', 'now') - 978307200 - {days}*24*60*60)")
    if min_width:
        conditions.append(f"a.ZWIDTH >= {min_width}")
    if favorites_only:
        conditions.append("a.ZFAVORITE = 1")

    where_clause = " AND ".join(conditions)

    query = f"""
    SELECT
        a.ZUUID,
        a.ZFILENAME,
        datetime(a.ZDATECREATED + 978307200, 'unixepoch', 'localtime') as created,
        a.ZWIDTH,
        a.ZHEIGHT,
        a.ZUNIFORMTYPEIDENTIFIER as file_type,
        a.ZFAVORITE,
        aa.ZORIGINALFILENAME
    FROM ZASSET a
    LEFT JOIN ZADDITIONALASSETATTRIBUTES aa ON a.ZADDITIONALATTRIBUTES = aa.Z_PK
    WHERE {where_clause}
    ORDER BY a.ZDATECREATED DESC
    LIMIT {limit}
    """

    cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()

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
    parser.add_argument('--days', type=int, default=7, help='Photos from last N days')
    parser.add_argument('--min-width', type=int, default=0, help='Minimum width in pixels')
    parser.add_argument('--favorites', action='store_true', help='Only favorited photos')
    parser.add_argument('--limit', type=int, default=20, help='Max results')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    parser.add_argument('--db', type=str, help='Path to Photos.sqlite (auto-detected if not specified)')

    args = parser.parse_args()

    db_path = args.db or find_photos_db()
    if not db_path:
        print("Error: Could not find Photos Library database")
        return 1

    photos = query_photos(
        db_path,
        days=args.days,
        min_width=args.min_width,
        favorites_only=args.favorites,
        limit=args.limit
    )

    if args.json:
        print(json.dumps(photos, indent=2))
    else:
        print(f"Found {len(photos)} photos (last {args.days} days, min_width={args.min_width})\n")
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
