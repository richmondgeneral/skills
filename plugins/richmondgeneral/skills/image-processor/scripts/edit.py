#!/usr/bin/env python3
"""
Image editing CLI.

Usage:
  python edit.py --input photo.jpg --instruction "remove the background" --output result.png
  python edit.py --input photo.jpg --instruction "change to sunset lighting" --output sunset.png
  python edit.py --input subject.jpg --instruction "place in scene" --reference bg.jpg --output composite.png
  python edit.py --input subject.jpg --odd-placement "a moon rover lab" --output silly.png
"""
import argparse
import sys
import os

# Add lib to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))

from models import TaskConfig, TaskType
from router import create_default_router


def build_odd_placement_instruction(scene: str, extra_instruction: str = "") -> str:
    """Build a robust instruction for surreal-but-recognizable odd placements."""
    base = (
        f"Create a playful composite by placing the main item naturally in {scene}. "
        "Keep the item itself recognizable and true to shape, text, and colors. "
        "Match perspective and lighting to the new scene, add realistic contact shadows, "
        "and avoid stretching or deforming the item."
    )
    if extra_instruction:
        return f"{base} Additional direction: {extra_instruction}"
    return base


def main():
    parser = argparse.ArgumentParser(
        description='Edit images with natural language instructions'
    )
    parser.add_argument('--input', '-i', required=True, help='Input image to edit')
    parser.add_argument('--instruction', '-I', help='Edit instruction')
    parser.add_argument(
        '--odd-placement',
        help='Scene for playful placement (example: "a lunar command center")'
    )
    parser.add_argument('--output', '-o', required=True, help='Output image path')
    parser.add_argument(
        '--reference', '-r',
        action='append',
        help='Reference image(s) for style/context'
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

    if not os.path.exists(args.input):
        print(f"Error: Input image not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    # Validate reference images exist
    references = args.reference or []
    for ref in references:
        if not os.path.exists(ref):
            print(f"Error: Reference image not found: {ref}", file=sys.stderr)
            sys.exit(1)

    if not args.instruction and not args.odd_placement:
        print("Error: Provide --instruction or --odd-placement", file=sys.stderr)
        sys.exit(1)

    final_instruction = args.instruction or ""
    if args.odd_placement:
        final_instruction = build_odd_placement_instruction(args.odd_placement, final_instruction)

    task_config = TaskConfig.for_edit(
        instruction=final_instruction,
        output_path=args.output,
        quality=args.quality,
        references=references
    )

    router = create_default_router()

    if args.verbose:
        print(f"Input: {args.input}", file=sys.stderr)
        print(f"Instruction: {final_instruction}", file=sys.stderr)
        print(f"Quality: {args.quality}", file=sys.stderr)
        if references:
            print(f"References: {len(references)}", file=sys.stderr)

    result = router.process(args.input, task_config)

    if args.json:
        import json
        output = {
            'success': result.success,
            'model': result.model_used,
            'input_image': args.input,
            'instruction': final_instruction,
            'output_path': result.output_path,
            'reference_count': len(references),
            'processing_time': result.processing_time,
            'mode': 'odd-placement' if args.odd_placement else 'edit',
        }
        if not result.success:
            output['error'] = result.error
        print(json.dumps(output, indent=2))
    else:
        if result.success:
            print(f"Edited: {result.output_path}")
            print(f"Model: {result.model_used}")
            print(f"Time: {result.processing_time:.1f}s")
        else:
            print(f"Error: {result.error}", file=sys.stderr)

    sys.exit(0 if result.success else 1)


if __name__ == '__main__':
    main()
