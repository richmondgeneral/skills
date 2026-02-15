#!/usr/bin/env python3
"""
Background removal and image processing CLI.

Usage:
  python process.py image.jpg
  python process.py image.jpg --output result.png
  python process.py image.jpg --task remove-bg --quality high
  python process.py image.jpg --model nano-banana
"""
import argparse
import sys
import os
from typing import Dict, Any, Optional

from PIL import Image

# Add lib to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))

from models import TaskConfig, TaskType, RemoveBgModel
from router import create_default_router


def analyze_mask_quality(output_path: str) -> Optional[Dict[str, Any]]:
    """
    Analyze alpha channel quality for background removal output.

    Returns None if output cannot be analyzed as an image.
    """
    try:
        with Image.open(output_path) as img:
            alpha = img.convert('RGBA').getchannel('A')
            bbox = alpha.getbbox()
            hist = alpha.histogram()  # 256-length histogram

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

        # Rectangle-mask heuristic:
        # - alpha-filled pixels almost completely fill bbox
        # - almost no antialiasing pixels
        # - very few alpha levels
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
            'suspicious_rect_mask': suspicious_rect_mask
        }
    except Exception:
        return None


def try_removebg_recovery(image_path: str, output_path: str, quality_mode: str,
                          verbose: bool = False):
    """
    Attempt recovery pass with remove.bg when initial mask quality is poor.
    Returns ProcessingResult or None if remove.bg is unavailable.
    """
    model = RemoveBgModel()
    if not model.health_check():
        return None

    if verbose:
        print(
            "Mask quality check flagged rectangular output; retrying with remove.bg...",
            file=sys.stderr
        )

    retry_config = TaskConfig(
        task_type=TaskType.REMOVE_BG,
        quality_mode=quality_mode,
        output_path=output_path,
        prefer_free=False,
        model_preference='removebg'
    )
    retry_result = model.process_image(image_path, retry_config)
    if retry_result.success:
        retry_result.metadata['auto_recovery'] = 'retry_removebg_after_rectangular_mask'
    return retry_result


def main():
    parser = argparse.ArgumentParser(
        description='Process images (background removal, analysis)'
    )
    parser.add_argument('image', help='Input image path')
    parser.add_argument('--output', '-o', help='Output image path')
    parser.add_argument(
        '--task', '-t',
        default='remove-bg',
        choices=['remove-bg', 'analyze'],
        help='Processing task (default: remove-bg)'
    )
    parser.add_argument(
        '--quality', '-q',
        default='high',
        choices=['low', 'medium', 'high', 'premium'],
        help='Quality mode (default: high)'
    )
    parser.add_argument(
        '--model', '-m',
        choices=['nano-banana', 'gemini25', 'removebg', 'auto'],
        default='auto',
        help='Model to use (default: auto)'
    )
    parser.add_argument(
        '--allow-rect-mask',
        action='store_true',
        help='Allow rectangular mask outputs without failing the command'
    )
    parser.add_argument('--json', action='store_true', help='Output JSON')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')

    args = parser.parse_args()

    if not os.path.exists(args.image):
        print(f"Error: Image not found: {args.image}", file=sys.stderr)
        sys.exit(1)

    # Map task string to TaskType
    task_map = {
        'remove-bg': TaskType.REMOVE_BG,
        'analyze': TaskType.ANALYZE,
    }

    task_config = TaskConfig(
        task_type=task_map[args.task],
        quality_mode=args.quality,
        output_path=args.output,
        prefer_free=(args.model == 'auto'),
        model_preference=args.model
    )

    router = create_default_router()

    if args.verbose:
        print(f"Processing: {args.image}", file=sys.stderr)
        print(f"Task: {args.task}, Quality: {args.quality}, Model: {args.model}", file=sys.stderr)

    result = router.process_with_fallback(args.image, task_config)
    strict_mask_qa = (args.task == 'remove-bg' and not args.allow_rect_mask)

    # Post-process quality check for background removal outputs.
    if args.task == 'remove-bg' and result.success and result.output_path:
        mask_quality = analyze_mask_quality(result.output_path)
        if mask_quality:
            result.metadata['mask_quality'] = mask_quality
            if args.verbose:
                print(
                    "Mask quality:",
                    f"transparent={mask_quality['transparent_ratio']:.1%},",
                    f"occupancy={mask_quality['occupancy_ratio']:.1%},",
                    f"semi={mask_quality['semi_alpha_ratio']:.1%},",
                    f"alpha_levels={mask_quality['unique_alpha_values']}",
                    file=sys.stderr
                )

            if mask_quality['suspicious_rect_mask'] and result.model_used != 'remove.bg':
                retry_result = try_removebg_recovery(
                    args.image, result.output_path, args.quality, args.verbose
                )
                if retry_result and retry_result.success:
                    retry_quality = analyze_mask_quality(retry_result.output_path)
                    if retry_quality:
                        retry_result.metadata['mask_quality'] = retry_quality
                    result = retry_result
                elif args.verbose:
                    print(
                        "remove.bg recovery unavailable or failed; keeping initial output.",
                        file=sys.stderr
                    )

        final_quality = result.metadata.get('mask_quality') if result.metadata else None
        if (
            strict_mask_qa
            and final_quality
            and final_quality.get('suspicious_rect_mask')
        ):
            result.success = False
            result.error = (
                "Rectangular mask detected and no acceptable recovery output was produced. "
                "Re-run with --model removebg or pass --allow-rect-mask to bypass."
            )
            result.metadata = result.metadata or {}
            result.metadata['qa_guard'] = 'failed_rectangular_mask'

    if args.json:
        import json
        output = {
            'success': result.success,
            'model': result.model_used,
            'output_path': result.output_path,
            'confidence': result.confidence,
            'processing_time': result.processing_time,
            'cost': result.cost,
            'metadata': result.metadata
        }
        if not result.success:
            output['error'] = result.error
        print(json.dumps(output, indent=2))
    else:
        print(result)

    sys.exit(0 if result.success else 1)


if __name__ == '__main__':
    main()
