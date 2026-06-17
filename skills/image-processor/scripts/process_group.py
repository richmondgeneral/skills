#!/usr/bin/env python3
"""Batch background-removal workflow for item image groups.

Processes all eligible images in a folder (or recursively) and writes
transparent PNG outputs using the existing image-processor routing/fallback logic.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from PIL import Image

# Add lib to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))

from models import TaskConfig, TaskType, RemoveBgModel
from router import create_default_router


SUPPORTED_EXTENSIONS = {
    '.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.tif', '.tiff', '.heic'
}


def matches_any(value: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch(value, pattern) for pattern in patterns)


def default_exclude_patterns(suffix: str) -> List[str]:
    return [
        'qr-code*',
        '*qr-code*',
        '*label*',
        '*.svg',
        f'*{suffix}.png',
    ]


def has_transparency(image_path: Path) -> bool:
    """Return True when an image already has transparent pixels."""
    try:
        with Image.open(image_path) as img:
            rgba = img.convert('RGBA')
            alpha = rgba.getchannel('A')
            min_alpha, _ = alpha.getextrema()
            return min_alpha < 255
    except Exception:
        return False


def analyze_mask_quality(output_path: Path) -> Optional[Dict[str, Any]]:
    """Analyze alpha channel quality for background removal output."""
    try:
        with Image.open(output_path) as img:
            alpha = img.convert('RGBA').getchannel('A')
            bbox = alpha.getbbox()
            hist = alpha.histogram()

        total_pixels = sum(hist)
        if total_pixels == 0:
            return None

        transparent = hist[0]
        opaque = hist[255]
        semi = total_pixels - transparent - opaque
        non_zero = total_pixels - transparent
        unique_alpha = sum(1 for count in hist if count > 0)

        if bbox:
            bbox_w = max(1, bbox[2] - bbox[0])
            bbox_h = max(1, bbox[3] - bbox[1])
            bbox_area = bbox_w * bbox_h
        else:
            bbox_area = 0

        occupancy = (non_zero / bbox_area) if bbox_area > 0 else 0.0
        transparency_ratio = transparent / total_pixels
        semi_ratio = semi / total_pixels

        suspicious_rect_mask = (
            bbox_area > 0 and
            occupancy > 0.97 and
            semi_ratio < 0.002 and
            unique_alpha <= 3
        )

        return {
            'transparent_ratio': round(transparency_ratio, 4),
            'occupancy_ratio': round(occupancy, 4),
            'semi_alpha_ratio': round(semi_ratio, 4),
            'unique_alpha_values': unique_alpha,
            'suspicious_rect_mask': suspicious_rect_mask,
        }
    except Exception:
        return None


def try_removebg_recovery(image_path: Path, output_path: Path, quality_mode: str,
                          verbose: bool = False):
    """Attempt recovery pass with remove.bg when initial mask quality is poor."""
    model = RemoveBgModel()
    if not model.health_check():
        return None

    if verbose:
        print(
            f"[{image_path.name}] Rectangular mask detected; retrying with remove.bg...",
            file=sys.stderr,
        )

    retry_config = TaskConfig(
        task_type=TaskType.REMOVE_BG,
        quality_mode=quality_mode,
        output_path=str(output_path),
        prefer_free=False,
        model_preference='removebg',
    )
    retry_result = model.process_image(str(image_path), retry_config)
    if retry_result.success:
        retry_result.metadata['auto_recovery'] = 'retry_removebg_after_rectangular_mask'
    return retry_result


def discover_images(
    input_dir: Path,
    recursive: bool,
    include_patterns: List[str],
    exclude_patterns: List[str],
    suffix: str,
    max_files: Optional[int] = None,
) -> List[Path]:
    """Discover candidate images for batch processing."""
    glob_pattern = '**/*' if recursive else '*'
    discovered: List[Path] = []

    for path in input_dir.glob(glob_pattern):
        if not path.is_file():
            continue

        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue

        if path.stem.lower().endswith(suffix.lower()):
            continue

        rel = path.relative_to(input_dir).as_posix()
        name = path.name

        if matches_any(name, exclude_patterns) or matches_any(rel, exclude_patterns):
            continue

        if include_patterns and not (
            matches_any(name, include_patterns) or matches_any(rel, include_patterns)
        ):
            continue

        discovered.append(path)

    discovered.sort(
        key=lambda p: (
            0 if 'hero' in p.stem.lower() else 1,
            p.name.lower(),
        )
    )

    if max_files is not None and max_files >= 0:
        discovered = discovered[:max_files]

    return discovered


def build_output_path(source: Path, input_dir: Path, output_dir: Optional[Path], suffix: str) -> Path:
    """Build output file path for a source image."""
    if output_dir is None:
        target_dir = source.parent
    else:
        rel_parent = source.parent.relative_to(input_dir)
        target_dir = output_dir / rel_parent

    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir / f"{source.stem}{suffix}.png"


def process_one(
    router,
    source: Path,
    output: Path,
    quality: str,
    model: str,
    allow_rect_mask: bool,
    verbose: bool,
) -> Dict[str, Any]:
    """Process a single image and return a structured result."""
    task_config = TaskConfig(
        task_type=TaskType.REMOVE_BG,
        quality_mode=quality,
        output_path=str(output),
        prefer_free=(model == 'auto'),
        model_preference=model,
    )

    result = router.process_with_fallback(str(source), task_config)
    metadata = result.metadata or {}

    if result.success and result.output_path:
        mask_quality = analyze_mask_quality(Path(result.output_path))
        if mask_quality:
            metadata['mask_quality'] = mask_quality

            if mask_quality.get('suspicious_rect_mask') and result.model_used != 'remove.bg':
                retry_result = try_removebg_recovery(source, output, quality, verbose)
                if retry_result and retry_result.success:
                    result = retry_result
                    metadata = result.metadata or {}
                    retry_quality = analyze_mask_quality(Path(result.output_path))
                    if retry_quality:
                        metadata['mask_quality'] = retry_quality

        final_quality = metadata.get('mask_quality')
        if (
            result.success and
            final_quality and
            final_quality.get('suspicious_rect_mask') and
            not allow_rect_mask
        ):
            result.success = False
            result.error = (
                'Rectangular mask detected and no acceptable recovery output was produced. '
                'Use --allow-rect-mask to bypass.'
            )
            metadata['qa_guard'] = 'failed_rectangular_mask'

    return {
        'source': str(source),
        'output': str(output),
        'success': bool(result.success),
        'model': result.model_used,
        'processing_time': round(float(result.processing_time), 3),
        'cost': float(result.cost),
        'error': result.error,
        'metadata': metadata,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Batch background removal for an image folder')
    parser.add_argument('--input-dir', required=True, help='Input directory containing images')
    parser.add_argument('--output-dir', help='Output directory (default: alongside each source)')
    parser.add_argument('--recursive', action='store_true', help='Recurse into subdirectories')
    parser.add_argument('--include', action='append', default=[], help='Include glob pattern (repeatable)')
    parser.add_argument('--exclude', action='append', default=[], help='Exclude glob pattern (repeatable)')
    parser.add_argument('--suffix', default='-nobg', help='Output suffix before .png (default: -nobg)')
    parser.add_argument('--quality', default='premium', choices=['low', 'medium', 'high', 'premium'])
    parser.add_argument('--model', default='auto', choices=['nano-banana', 'gemini25', 'removebg', 'auto'])
    parser.add_argument('--overwrite', action='store_true', help='Overwrite existing outputs')
    parser.add_argument('--process-transparent', action='store_true', help='Re-process PNGs that already have transparency')
    parser.add_argument('--allow-rect-mask', action='store_true', help='Allow rectangular mask output without failing')
    parser.add_argument('--max-files', type=int, help='Process at most N discovered files')
    parser.add_argument('--fail-fast', action='store_true', help='Stop on first processing failure')
    parser.add_argument('--json', action='store_true', help='Emit JSON summary')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose progress to stderr')
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    input_dir = Path(args.input_dir).expanduser().resolve()
    if not input_dir.exists() or not input_dir.is_dir():
        print(f'Error: Input directory not found: {input_dir}', file=sys.stderr)
        return 1

    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else None
    exclude_patterns = args.exclude or default_exclude_patterns(args.suffix)

    files = discover_images(
        input_dir=input_dir,
        recursive=args.recursive,
        include_patterns=args.include,
        exclude_patterns=exclude_patterns,
        suffix=args.suffix,
        max_files=args.max_files,
    )

    if not files:
        summary = {
            'success': True,
            'input_dir': str(input_dir),
            'processed': 0,
            'failed': 0,
            'skipped': 0,
            'results': [],
            'note': 'No candidate images found',
        }
        if args.json:
            print(json.dumps(summary, indent=2))
        else:
            print('No candidate images found.')
        return 0

    router = create_default_router()

    results: List[Dict[str, Any]] = []
    failures = 0
    skipped = 0

    for source in files:
        output = build_output_path(source, input_dir, output_dir, args.suffix)

        if output.exists() and not args.overwrite:
            skipped += 1
            results.append({
                'source': str(source),
                'output': str(output),
                'success': True,
                'skipped': True,
                'reason': 'output_exists',
            })
            continue

        if has_transparency(source) and not args.process_transparent:
            skipped += 1
            results.append({
                'source': str(source),
                'output': str(output),
                'success': True,
                'skipped': True,
                'reason': 'already_transparent',
            })
            continue

        if args.verbose:
            print(f'Processing {source} -> {output}', file=sys.stderr)

        item_result = process_one(
            router=router,
            source=source,
            output=output,
            quality=args.quality,
            model=args.model,
            allow_rect_mask=args.allow_rect_mask,
            verbose=args.verbose,
        )
        results.append(item_result)

        if not item_result['success']:
            failures += 1
            if args.fail_fast:
                break

    processed = sum(1 for r in results if not r.get('skipped'))
    summary = {
        'success': failures == 0,
        'input_dir': str(input_dir),
        'output_dir': str(output_dir) if output_dir else str(input_dir),
        'processed': processed,
        'failed': failures,
        'skipped': skipped,
        'results': results,
    }

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(
            f"Batch complete: processed={summary['processed']} "
            f"failed={summary['failed']} skipped={summary['skipped']}"
        )

    return 0 if failures == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
