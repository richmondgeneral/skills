#!/usr/bin/env python3
"""
Photos.app Library Access CLI.

Usage:
  python photos.py --recent 10
  python photos.py --albums
  python photos.py --favorites 5
  python photos.py --search "IMG_*.jpg"
  python photos.py --since 2025-12-01 --limit 20
  python photos.py --copy UUID --output /path/to/dest.png
  python photos.py --stats
"""
import argparse
import sys
import os
from datetime import datetime

# Add lib to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))

from photos import PhotosLibrary, PhotoInfo


def format_photo(photo: PhotoInfo, verbose: bool = False) -> str:
    """Format photo info for display."""
    date_str = photo.date_created.strftime('%Y-%m-%d %H:%M') if photo.date_created else 'Unknown'
    fav = ' *' if photo.is_favorite else ''

    if verbose:
        return (
            f"{photo.uuid}\n"
            f"  File: {photo.filename}\n"
            f"  Date: {date_str}\n"
            f"  Size: {photo.width}x{photo.height}\n"
            f"  Path: {photo.file_path or 'Not accessible'}{fav}"
        )
    else:
        return f"{photo.filename} ({photo.width}x{photo.height}) - {date_str}{fav}"


def main():
    parser = argparse.ArgumentParser(
        description='Access Photos.app library'
    )

    # Actions (mutually exclusive)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--recent', type=int, metavar='N', help='List N recent photos')
    group.add_argument('--albums', action='store_true', help='List albums')
    group.add_argument('--favorites', type=int, nargs='?', const=10, metavar='N', help='List favorite photos')
    group.add_argument('--search', metavar='PATTERN', help='Search by filename (use %% as wildcard)')
    group.add_argument('--copy', metavar='UUID', help='Copy photo by UUID')
    group.add_argument('--info', metavar='UUID', help='Get photo info by UUID')
    group.add_argument('--stats', action='store_true', help='Show library statistics')

    # Filters
    parser.add_argument('--since', metavar='DATE', help='Photos since date (YYYY-MM-DD)')
    parser.add_argument('--until', metavar='DATE', help='Photos until date (YYYY-MM-DD)')
    parser.add_argument('--limit', type=int, default=25, help='Max results (default: 25)')

    # Copy options
    parser.add_argument('--output', '-o', help='Output path for --copy')

    # Output options
    parser.add_argument('--json', action='store_true', help='Output JSON')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--library', help='Path to Photos library (default: ~/Pictures)')

    args = parser.parse_args()

    try:
        library = PhotosLibrary(args.library)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Parse dates
    since_date = None
    until_date = None
    if args.since:
        try:
            since_date = datetime.strptime(args.since, '%Y-%m-%d')
        except ValueError:
            print(f"Error: Invalid date format: {args.since} (use YYYY-MM-DD)", file=sys.stderr)
            sys.exit(1)
    if args.until:
        try:
            until_date = datetime.strptime(args.until, '%Y-%m-%d')
        except ValueError:
            print(f"Error: Invalid date format: {args.until} (use YYYY-MM-DD)", file=sys.stderr)
            sys.exit(1)

    # Execute action
    if args.stats:
        stats = library.get_library_stats()
        if args.json:
            import json
            print(json.dumps(stats, indent=2))
        else:
            print("Photos Library Statistics:")
            print(f"  Photos: {stats['total_photos']:,}")
            print(f"  Videos: {stats['total_videos']:,}")
            print(f"  Favorites: {stats['favorites']:,}")
            print(f"  Albums: {stats['albums']:,}")
            print(f"  Location: {stats['library_path']}")

    elif args.albums:
        albums = library.list_albums(limit=args.limit)
        if args.json:
            import json
            output = [{'uuid': a.uuid, 'title': a.title, 'count': a.photo_count} for a in albums]
            print(json.dumps(output, indent=2))
        else:
            print(f"Albums ({len(albums)}):\n")
            for album in albums:
                print(f"  {album.title} ({album.photo_count} photos)")

    elif args.favorites is not None:
        photos = library.get_favorites(limit=args.favorites)
        output_photos(photos, args.json, args.verbose)

    elif args.search:
        pattern = args.search
        if '*' in pattern:
            pattern = pattern.replace('*', '%')
        if '%' not in pattern:
            pattern = f'%{pattern}%'
        photos = library.search_by_filename(pattern, limit=args.limit)
        output_photos(photos, args.json, args.verbose)

    elif args.copy:
        if not args.output:
            print("Error: --output required with --copy", file=sys.stderr)
            sys.exit(1)
        try:
            result = library.copy_photo(args.copy, args.output)
            if args.json:
                import json
                print(json.dumps({'success': True, 'path': result}))
            else:
                print(f"Copied to: {result}")
        except FileNotFoundError as e:
            if args.json:
                import json
                print(json.dumps({'success': False, 'error': str(e)}))
            else:
                print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.info:
        photo = library.get_photo_by_uuid(args.info)
        if not photo:
            print(f"Error: Photo not found: {args.info}", file=sys.stderr)
            sys.exit(1)
        if args.json:
            import json
            output = {
                'uuid': photo.uuid,
                'filename': photo.filename,
                'original_filename': photo.original_filename,
                'date_created': photo.date_created.isoformat() if photo.date_created else None,
                'width': photo.width,
                'height': photo.height,
                'file_path': photo.file_path,
                'is_favorite': photo.is_favorite,
                'is_hidden': photo.is_hidden
            }
            print(json.dumps(output, indent=2))
        else:
            print(format_photo(photo, verbose=True))

    elif args.recent:
        photos = library.get_recent_photos(limit=args.recent)
        output_photos(photos, args.json, args.verbose)

    elif since_date or until_date:
        photos = library.get_photos_by_date(since=since_date, until=until_date, limit=args.limit)
        output_photos(photos, args.json, args.verbose)

    else:
        # Default: show recent 10
        photos = library.get_recent_photos(limit=10)
        output_photos(photos, args.json, args.verbose)


def output_photos(photos: list, as_json: bool, verbose: bool):
    """Output photo list."""
    if as_json:
        import json
        output = []
        for p in photos:
            output.append({
                'uuid': p.uuid,
                'filename': p.filename,
                'date_created': p.date_created.isoformat() if p.date_created else None,
                'width': p.width,
                'height': p.height,
                'file_path': p.file_path,
                'is_favorite': p.is_favorite
            })
        print(json.dumps(output, indent=2))
    else:
        print(f"Photos ({len(photos)}):\n")
        for photo in photos:
            print(f"  {format_photo(photo, verbose)}")


if __name__ == '__main__':
    main()
