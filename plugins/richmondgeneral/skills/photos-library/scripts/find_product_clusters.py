#!/usr/bin/env python3
"""Find and group product photo clusters from macOS Photos Library."""

import argparse
import sqlite3
import json
import os
from datetime import datetime
from pathlib import Path

import photos_db

COCOA_EPOCH_OFFSET = 978307200
SECONDS_PER_DAY = 86400


def find_photos_db():
    """Find Photos Library database."""
    paths = [
        Path.home() / "Pictures/Photos Library.photoslibrary/database/Photos.sqlite",
    ]
    for p in paths:
        if p.exists():
            return str(p)
    return None


def cluster_photos(photos, gap_seconds=300):
    """Group photos by time proximity."""
    if not photos:
        return []

    clusters = []
    current_cluster = [photos[0]]

    for photo in photos[1:]:
        last_ts = current_cluster[-1]['timestamp']
        if abs(photo['timestamp'] - last_ts) <= gap_seconds:
            current_cluster.append(photo)
        else:
            clusters.append(current_cluster)
            current_cluster = [photo]

    if current_cluster:
        clusters.append(current_cluster)

    return clusters


def classify_cluster(cluster):
    """Classify a cluster as product, real_estate, screenshot, or other."""
    if not cluster:
        return 'empty'

    # Count orientations
    portrait = sum(1 for p in cluster if p['height'] > p['width'])
    landscape = len(cluster) - portrait

    # Calculate average aspect ratio
    ratios = [max(p['width'], p['height']) / min(p['width'], p['height']) for p in cluster]
    avg_ratio = sum(ratios) / len(ratios)

    # Classification heuristics
    if avg_ratio > 1.9:
        return 'screenshot'
    elif portrait >= len(cluster) * 0.6 and avg_ratio < 1.5:
        return 'product'
    elif landscape >= len(cluster) * 0.6 and len(cluster) >= 5:
        return 'real_estate'
    elif len(cluster) == 1:
        return 'single'
    else:
        return 'mixed'


def find_product_clusters(db_path, days=3, min_width=2000, cluster_gap=300,
                          album=None, keyword=None, exclude_keyword=None):
    """Find photo clusters that are likely product photos."""
    # Open the live Photos library read-only AND immutable so we never take
    # locks or touch the WAL — anything less can disrupt cloudphotod's sync
    # state tracking and force a full iCloud re-pull.
    with sqlite3.connect(f"file:{db_path}?mode=ro&immutable=1", uri=True) as conn:
        cursor = conn.cursor()

        conditions = [
            "a.ZTRASHEDSTATE = 0",
            "a.ZHIDDEN = 0",
            "a.ZKIND = 0",  # photos only, not videos
        ]
        params = []

        if days:
            conditions.append(f"a.ZDATECREATED > (strftime('%s', 'now') - {COCOA_EPOCH_OFFSET} - ? * {SECONDS_PER_DAY})")
            params.append(days)

        if min_width:
            conditions.append("a.ZWIDTH >= ?")
            params.append(min_width)
        if album:
            frag, frag_params = photos_db.album_condition(conn, album)
            conditions.append(frag)
            params.extend(frag_params)
        if keyword:
            frag, frag_params = photos_db.keyword_condition(conn, keyword)
            conditions.append(frag)
            params.extend(frag_params)
            
        # Add support for excluding keywords
        if exclude_keyword:
            frag, frag_params = photos_db.exclude_keyword_condition(conn, exclude_keyword)
            conditions.append(frag)
            params.extend(frag_params)

        where_clause = " AND ".join(conditions)

        query = f"""
        SELECT
            a.ZUUID,
            aa.ZORIGINALFILENAME,
            a.ZDATECREATED,
            a.ZWIDTH,
            a.ZHEIGHT,
            a.ZUNIFORMTYPEIDENTIFIER,
            datetime(a.ZDATECREATED + {COCOA_EPOCH_OFFSET}, 'unixepoch', 'localtime') as created_str
        FROM ZASSET a
        LEFT JOIN ZADDITIONALASSETATTRIBUTES aa ON a.ZADDITIONALATTRIBUTES = aa.Z_PK
        WHERE {where_clause}
        ORDER BY a.ZDATECREATED DESC
        """

        cursor.execute(query, params)
        rows = cursor.fetchall()

    # Convert to dicts
    photos = []
    for row in rows:
        uuid, filename, timestamp, width, height, ftype, created_str = row
        ext = ftype.split('.')[-1] if ftype else 'heic'
        first_char = uuid[0].upper()

        photos.append({
            'uuid': uuid,
            'filename': filename or uuid,
            'timestamp': timestamp,
            'created': created_str,
            'width': width,
            'height': height,
            'type': ext,
            'path': f"originals/{first_char}/{uuid}.{ext}"
        })

    # Cluster by time
    clusters = cluster_photos(photos, cluster_gap)

    # Classify and annotate each cluster
    result = []
    for i, cluster in enumerate(clusters, 1):
        cluster_type = classify_cluster(cluster)
        first_time = datetime.fromtimestamp(cluster[0]['timestamp'] + COCOA_EPOCH_OFFSET)

        result.append({
            'cluster_id': i,
            'type': cluster_type,
            'count': len(cluster),
            'date': first_time.strftime('%Y-%m-%d'),
            'time': first_time.strftime('%H:%M'),
            'photos': cluster
        })

    return result


def main():
    parser = argparse.ArgumentParser(description='Find product photo clusters in Photos Library')
    parser.add_argument('--days', type=int, default=3, help='Search last N days (0 for all; default 3 — the library-wide intake sweep window)')
    parser.add_argument('--min-width', type=int, default=2000, help='Minimum width in pixels')
    parser.add_argument('--gap', type=int, default=300, help='Max seconds between photos in cluster')
    parser.add_argument('--type', type=str, choices=['all', 'product', 'real_estate', 'screenshot', 'single', 'mixed'],
                        default='all', help='Filter by cluster type')
    parser.add_argument('--album', type=str, help='Only photos in this album (matches album name, e.g. "Intake")')
    parser.add_argument('--keyword', '--tag', dest='keyword', type=str, help='Only photos with this keyword/tag')
    parser.add_argument('--exclude-keyword', type=str, help='Exclude photos with this keyword/tag')
    parser.add_argument('--hide-sorted', action='store_true', help='Convenience flag to exclude photos tagged rg-sorted')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    parser.add_argument('--db', type=str, help='Path to Photos.sqlite')

    args = parser.parse_args()

    # Input validation
    if args.days < 0:
        print("Error: --days cannot be negative")
        return 1
    if args.min_width < 0:
        print("Error: --min-width cannot be negative")
        return 1
    if args.gap < 1:
        print("Error: --gap must be at least 1 second")
        return 1

    db_path = args.db or find_photos_db()
    if not db_path:
        print("Error: Could not find Photos Library database")
        return 1

    days_filter = args.days if args.days > 0 else None
    # When pulling by album/keyword, don't also gate on the high default min-width
    # (intake albums include tag/label/serial close-ups under 2000px) unless the
    # user explicitly passed --min-width.
    min_width = args.min_width
    if (args.album or args.keyword) and '--min-width' not in ' '.join(os.sys.argv):
        min_width = 0

    if args.album or args.keyword or args.exclude_keyword or args.hide_sorted:
        with sqlite3.connect(f"file:{db_path}?mode=ro&immutable=1", uri=True) as _c:
            if args.album and not photos_db.album_exists(_c, args.album):
                print(f"⚠️  Album '{args.album}' not found. Known: {', '.join(photos_db.list_albums(_c, 15))}", file=os.sys.stderr)
            if args.keyword and not photos_db.keyword_exists(_c, args.keyword):
                print(f"⚠️  Keyword/tag '{args.keyword}' not found.", file=os.sys.stderr)
            exclude = args.exclude_keyword
            if args.hide_sorted:
                exclude = 'rg-sorted'
            if exclude and not photos_db.keyword_exists(_c, exclude):
                print(f"⚠️  Exclude keyword/tag '{exclude}' not found in DB.", file=os.sys.stderr)

    exclude_keyword = args.exclude_keyword
    if args.hide_sorted:
        exclude_keyword = 'rg-sorted'

    clusters = find_product_clusters(db_path, days=days_filter, min_width=min_width,
                                     cluster_gap=args.gap, album=args.album, keyword=args.keyword, exclude_keyword=exclude_keyword)

    # Filter by type if specified
    if args.type != 'all':
        clusters = [c for c in clusters if c['type'] == args.type]

    if args.json:
        print(json.dumps(clusters, indent=2))
    else:
        days_str = f"last {args.days} days" if args.days else "all time"
        scope = f", album='{args.album}'" if args.album else (f", tag='{args.keyword}'" if args.keyword else "")
        print(f"Found {len(clusters)} clusters ({days_str}, min_width={min_width}{scope})\n")

        print(f"{'#':>3} {'Type':<12} {'Count':>5} {'Date':<12} {'Time':<6} {'First Photo'}")
        print("-" * 70)

        for c in clusters:
            first_photo = c['photos'][0]['filename'][:25] if c['photos'] else '?'
            type_marker = "★" if c['type'] == 'product' else " "
            print(f"{c['cluster_id']:>3} {c['type']:<12} {c['count']:>5} {c['date']:<12} {c['time']:<6} {first_photo} {type_marker}")

        # Summary
        product_clusters = [c for c in clusters if c['type'] == 'product']
        if product_clusters:
            total_product_photos = sum(c['count'] for c in product_clusters)
            print(f"\n★ {len(product_clusters)} product clusters with {total_product_photos} photos")

    return 0


if __name__ == '__main__':
    exit(main())
