#!/usr/bin/env python3
"""
Image generation CLI.

Usage:
  python generate.py --prompt "A vintage typewriter" --output result.png
  python generate.py --prompt "Apply this style" --reference style.jpg --output styled.png
  python generate.py --prompt "Professional photo" --quality pro --output hero.png
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
        description='Generate images from text prompts'
    )
    parser.add_argument('--prompt', '-p', required=True, help='Text description')
    parser.add_argument('--output', '-o', required=True, help='Output image path')
    parser.add_argument(
        '--reference', '-r',
        action='append',
        help='Reference image(s) for style guidance'
    )
    parser.add_argument(
        '--quality', '-q',
        default='auto',
        choices=['auto', 'fast', 'pro'],
        help='Quality mode (default: auto)'
    )
    parser.add_argument('--json', action='store_true', help='Output JSON')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')

    args = parser.parse_args()

    # Validate reference images exist
    references = args.reference or []
    for ref in references:
        if not os.path.exists(ref):
            print(f"Error: Reference image not found: {ref}", file=sys.stderr)
            sys.exit(1)

    task_config = TaskConfig.for_generate(
        prompt=args.prompt,
        output_path=args.output,
        quality=args.quality,
        references=references
    )

    router = create_default_router()

    if args.verbose:
        print(f"Prompt: {args.prompt}")
        print(f"Quality: {args.quality}")
        if references:
            print(f"References: {len(references)}")

    result = router.generate(task_config)

    if args.json:
        import json
        output = {
            'success': result.success,
            'model': result.model_used,
            'output_path': result.output_path,
            'prompt': args.prompt,
            'reference_count': len(references),
            'processing_time': result.processing_time,
        }
        if not result.success:
            output['error'] = result.error
        print(json.dumps(output, indent=2))
    else:
        if result.success:
            print(f"Generated: {result.output_path}")
            print(f"Model: {result.model_used}")
            print(f"Time: {result.processing_time:.1f}s")
        else:
            print(f"Error: {result.error}", file=sys.stderr)

    sys.exit(0 if result.success else 1)


if __name__ == '__main__':
    main()
