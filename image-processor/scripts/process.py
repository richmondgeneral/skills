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

# Add lib to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))

from models import TaskConfig, TaskType
from router import create_default_router


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
        prefer_free=True
    )

    router = create_default_router()

    if args.verbose:
        print(f"Processing: {args.image}")
        print(f"Task: {args.task}, Quality: {args.quality}")

    result = router.process_with_fallback(args.image, task_config)

    if args.json:
        import json
        output = {
            'success': result.success,
            'model': result.model_used,
            'output_path': result.output_path,
            'confidence': result.confidence,
            'processing_time': result.processing_time,
            'cost': result.cost,
        }
        if not result.success:
            output['error'] = result.error
        print(json.dumps(output, indent=2))
    else:
        print(result)

    sys.exit(0 if result.success else 1)


if __name__ == '__main__':
    main()
