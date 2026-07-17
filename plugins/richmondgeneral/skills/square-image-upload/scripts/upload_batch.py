#!/usr/bin/env python3
"""Bulk Square Catalog image upload helper.

Supports:
- directory mode: upload all discovered image files for one item/variation
- manifest mode: upload rows from CSV for one or many item IDs
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from fnmatch import fnmatch
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

try:
    import requests
except ImportError:
    print('Error: requests library required. Install with: pip install requests')
    sys.exit(1)

from upload_image import create_catalog_image, DEFAULT_API_VERSION


SUPPORTED_EXTENSIONS = {
    '.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tif', '.tiff', '.heic'
}


def matches_any(value: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch(value, pattern) for pattern in patterns)


def parse_bool(value: str) -> bool:
    return str(value).strip().lower() in {'1', 'true', 'yes', 'y', 'on'}


def discover_images(
    directory: Path,
    recursive: bool,
    include_patterns: List[str],
    exclude_patterns: List[str],
) -> List[Path]:
    pattern = '**/*' if recursive else '*'
    images: List[Path] = []

    for path in directory.glob(pattern):
        if not path.is_file():
            continue
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue

        rel = path.relative_to(directory).as_posix()
        name = path.name
        if matches_any(name, exclude_patterns) or matches_any(rel, exclude_patterns):
            continue
        if include_patterns and not (
            matches_any(name, include_patterns) or matches_any(rel, include_patterns)
        ):
            continue

        images.append(path)

    return sorted(images, key=lambda p: p.as_posix().lower())


def choose_preferred_variants(images: List[Path], prefer_nobg: bool) -> List[Path]:
    if not prefer_nobg:
        return images

    grouped: Dict[Tuple[Path, str], List[Path]] = {}
    for img in images:
        stem = img.stem
        key_stem = stem.removesuffix('-nobg').removesuffix('-NOBG')
        key = (img.parent, key_stem.lower())
        grouped.setdefault(key, []).append(img)

    selected: List[Path] = []
    for group in grouped.values():
        group_sorted = sorted(
            group,
            key=lambda p: (
                0 if p.stem.lower().endswith('-nobg') else 1,
                0 if p.suffix.lower() == '.png' else 1,
                p.name.lower(),
            ),
        )
        selected.append(group_sorted[0])

    return sorted(selected, key=lambda p: p.as_posix().lower())


def sort_upload_order(images: List[Path], primary_file: Optional[str] = None) -> List[Path]:
    if not images:
        return []

    primary_path = Path(primary_file).expanduser().resolve() if primary_file and os.path.exists(primary_file) else None
    primary_name = Path(primary_file).name.lower() if primary_file else None

    def rank(path: Path) -> Tuple[int, str]:
        if primary_path and path.resolve() == primary_path:
            return (0, path.name.lower())
        if primary_name and path.name.lower() == primary_name:
            return (0, path.name.lower())
        if 'hero' in path.stem.lower():
            return (1, path.name.lower())
        return (2, path.name.lower())

    return sorted(images, key=rank)


def pretty_name_from_path(path: Path) -> str:
    cleaned = path.stem.replace('-nobg', '')
    cleaned = cleaned.replace('_', ' ').replace('-', ' ').strip()
    return cleaned.title() if cleaned else path.stem


def upload_one(
    access_token: str,
    image_path: Path,
    api_version: str,
    *,
    item_id: Optional[str] = None,
    variation_id: Optional[str] = None,
    name: Optional[str] = None,
    caption: Optional[str] = None,
    is_primary: bool = False,
) -> Dict[str, object]:
    object_id = item_id or variation_id
    result = create_catalog_image(
        access_token=access_token,
        image_path=str(image_path),
        object_id=object_id,
        name=name,
        caption=caption,
        is_primary=is_primary,
        api_version=api_version,
    )

    image = result.get('image', {})
    return {
        'success': True,
        'source': str(image_path),
        'image_id': image.get('id'),
        'url': image.get('image_data', {}).get('url'),
        'name': image.get('image_data', {}).get('name') or name,
        'caption': image.get('image_data', {}).get('caption') or caption,
        'is_primary': bool(is_primary),
        'item_id': item_id,
        'variation_id': variation_id,
    }


def parse_manifest(manifest_csv: Path) -> List[Dict[str, str]]:
    with manifest_csv.open('r', encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        rows = [dict(row) for row in reader]
    return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Bulk upload images to Square catalog')

    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument('--directory', help='Directory of images to upload')
    source_group.add_argument('--manifest', help='CSV manifest (image_path,item_id|variation_id,name,caption,is_primary)')

    target_group = parser.add_mutually_exclusive_group()
    target_group.add_argument('--item-id', help='Catalog item ID target (directory mode)')
    target_group.add_argument('--variation-id', help='Catalog variation ID target (directory mode)')

    parser.add_argument('--recursive', action='store_true', help='Recurse into subdirectories in directory mode')
    parser.add_argument('--include', action='append', default=[], help='Include glob pattern (repeatable)')
    parser.add_argument('--exclude', action='append', default=['qr-code*', '*qr-code*', '*label*', '*.svg'], help='Exclude glob pattern (repeatable)')
    parser.add_argument('--primary-file', help='Force this image as primary (path or basename)')
    parser.add_argument('--no-auto-primary', action='store_true', help='Do not automatically mark first discovered image as primary')
    parser.add_argument('--no-prefer-nobg', action='store_true', help='Do not prefer *-nobg variants when both exist')
    parser.add_argument('--name-prefix', default='', help='Prefix added to generated image names')
    parser.add_argument('--caption-prefix', default='', help='Prefix added to generated captions')
    parser.add_argument('--token', '-t', help='Square access token (or use SQUARE_ACCESS_TOKEN env var)')
    parser.add_argument('--api-version', default=os.environ.get('SQUARE_API_VERSION', DEFAULT_API_VERSION), help=f'Square API version (default: {DEFAULT_API_VERSION})')
    parser.add_argument('--dry-run', action='store_true', help='Do not call API, only print/upload plan')
    parser.add_argument('--continue-on-error', action='store_true', help='Continue if one upload fails')
    parser.add_argument('--json', '-j', action='store_true', help='Output JSON summary')
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    access_token = args.token or os.environ.get('SQUARE_ACCESS_TOKEN')
    if not access_token and not args.dry_run:
        print('Error: Square access token required (SQUARE_ACCESS_TOKEN or --token)', file=sys.stderr)
        return 1

    uploads: List[Dict[str, object]] = []

    if args.directory:
        directory = Path(args.directory).expanduser().resolve()
        if not directory.exists() or not directory.is_dir():
            print(f'Error: Directory not found: {directory}', file=sys.stderr)
            return 1

        if not args.item_id and not args.variation_id:
            print('Error: --item-id or --variation-id is required in directory mode', file=sys.stderr)
            return 1

        discovered = discover_images(
            directory=directory,
            recursive=args.recursive,
            include_patterns=args.include,
            exclude_patterns=args.exclude,
        )
        chosen = choose_preferred_variants(discovered, prefer_nobg=(not args.no_prefer_nobg))
        ordered = sort_upload_order(chosen, args.primary_file)

        for idx, path in enumerate(ordered):
            is_primary = (idx == 0 and not args.no_auto_primary)
            generated_name = f"{args.name_prefix}{pretty_name_from_path(path)}"
            generated_caption = f"{args.caption_prefix}{pretty_name_from_path(path)}"
            uploads.append({
                'image_path': path,
                'item_id': args.item_id,
                'variation_id': args.variation_id,
                'name': generated_name,
                'caption': generated_caption,
                'is_primary': is_primary,
            })
    else:
        manifest_path = Path(args.manifest).expanduser().resolve()
        if not manifest_path.exists():
            print(f'Error: Manifest not found: {manifest_path}', file=sys.stderr)
            return 1

        for row in parse_manifest(manifest_path):
            image_path = Path((row.get('image_path') or '').strip()).expanduser().resolve()
            if not image_path.exists():
                uploads.append({
                    'success': False,
                    'source': str(image_path),
                    'error': 'image_not_found',
                })
                if not args.continue_on_error:
                    break
                continue

            item_id = (row.get('item_id') or args.item_id or '').strip() or None
            variation_id = (row.get('variation_id') or args.variation_id or '').strip() or None
            if not item_id and not variation_id:
                uploads.append({
                    'success': False,
                    'source': str(image_path),
                    'error': 'missing_target_id',
                })
                if not args.continue_on_error:
                    break
                continue

            uploads.append({
                'image_path': image_path,
                'item_id': item_id,
                'variation_id': variation_id,
                'name': (row.get('name') or '').strip() or pretty_name_from_path(image_path),
                'caption': (row.get('caption') or '').strip() or pretty_name_from_path(image_path),
                'is_primary': parse_bool(row.get('is_primary') or ''),
            })

    results: List[Dict[str, object]] = []
    failures = 0

    for task in uploads:
        if task.get('success') is False:
            failures += 1
            results.append(task)
            if not args.continue_on_error:
                break
            continue

        image_path = task['image_path']
        item_id = task.get('item_id')
        variation_id = task.get('variation_id')

        if args.dry_run:
            results.append({
                'success': True,
                'dry_run': True,
                'source': str(image_path),
                'item_id': item_id,
                'variation_id': variation_id,
                'name': task.get('name'),
                'caption': task.get('caption'),
                'is_primary': bool(task.get('is_primary')),
            })
            continue

        try:
            print(f"Uploading {image_path}...", file=sys.stderr)
            uploaded = upload_one(
                access_token=access_token,
                image_path=image_path,
                api_version=args.api_version,
                item_id=item_id,
                variation_id=variation_id,
                name=task.get('name'),
                caption=task.get('caption'),
                is_primary=bool(task.get('is_primary')),
            )
            results.append(uploaded)
        except requests.exceptions.HTTPError as exc:
            failures += 1
            error_entry: Dict[str, object] = {
                'success': False,
                'source': str(image_path),
                'item_id': item_id,
                'variation_id': variation_id,
                'error': str(exc),
            }
            if exc.response is not None:
                try:
                    error_entry['api_error'] = exc.response.json()
                except Exception:
                    error_entry['api_error'] = exc.response.text
            results.append(error_entry)
            if not args.continue_on_error:
                break
        except Exception as exc:
            failures += 1
            results.append({
                'success': False,
                'source': str(image_path),
                'item_id': item_id,
                'variation_id': variation_id,
                'error': str(exc),
            })
            if not args.continue_on_error:
                break

    summary = {
        'success': failures == 0,
        'planned': len(uploads),
        'uploaded': sum(1 for r in results if r.get('success')),
        'failed': failures,
        'results': results,
    }

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(
            f"Batch upload complete: planned={summary['planned']} "
            f"uploaded={summary['uploaded']} failed={summary['failed']}"
        )

    return 0 if failures == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
