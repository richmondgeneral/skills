#!/usr/bin/env python3
"""
Image Editing Script using Gemini Nano Banana

Edit existing images with natural language instructions.
Supports object manipulation, style changes, and multi-image composition.

Usage:
    python edit_image.py --input photo.jpg --instruction "remove background" --output result.png
    python edit_image.py --input portrait.jpg --instruction "change to sunset lighting" --output edited.png
    python edit_image.py --input base.jpg --instruction "combine these" --reference style.jpg --output result.png
"""

import argparse
import sys
import json
from pathlib import Path

# Add lib to path (symlinked from image-generation-skill)
sys.path.insert(0, str(Path(__file__).parent.parent / 'lib'))

from gemini_api import GeminiAPI, GeminiAPIError, save_image


def main():
    parser = argparse.ArgumentParser(
        description='Edit images using Gemini Nano Banana',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        '--input',
        required=True,
        help='Input image to edit'
    )
    
    parser.add_argument(
        '--instruction',
        required=True,
        help='Natural language editing instruction'
    )
    
    parser.add_argument(
        '--output',
        required=True,
        help='Output image path (PNG recommended)'
    )
    
    parser.add_argument(
        '--reference',
        action='append',
        dest='references',
        help='Additional reference images for composition/style (can specify multiple, max 14 total)'
    )
    
    parser.add_argument(
        '--quality',
        choices=['auto', 'fast', 'pro'],
        default='auto',
        help='Quality/speed preference (auto=smart selection, fast=Nano Banana, pro=Nano Banana Pro)'
    )
    
    parser.add_argument(
        '--api-key',
        help='Gemini API key (or set GEMINI_API_KEY env var)'
    )
    
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output metadata as JSON to stdout'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Verbose output'
    )
    
    args = parser.parse_args()
    
    try:
        # Verify input exists
        if not Path(args.input).exists():
            print(f"Error: Input image not found: {args.input}", file=sys.stderr)
            return 1
        
        # Initialize API client
        if args.verbose:
            print(f"Initializing Gemini API...")
        api = GeminiAPI(api_key=args.api_key)
        
        # Select model
        model = GeminiAPI.select_model(
            args.instruction,
            reference_images=args.references,
            quality_hint=args.quality
        )
        
        if args.verbose:
            print(f"Input: {Path(args.input).name}")
            print(f"Selected model: {model}")
            if args.references:
                print(f"Reference images: {len(args.references)}")
        
        # Edit image
        if args.verbose:
            print(f"Editing image...")
            
        image_data, metadata = api.edit_image(
            input_image=args.input,
            instruction=args.instruction,
            model=model,
            reference_images=args.references
        )
        
        # Save result
        save_image(image_data, args.output)
        
        if args.verbose:
            print(f"✅ Edited image saved: {args.output}")
        
        # Output metadata
        if args.json:
            metadata['output_path'] = str(Path(args.output).resolve())
            print(json.dumps(metadata, indent=2))
        elif not args.verbose:
            # Minimal output for scripting
            print(args.output)
        
        return 0
        
    except GeminiAPIError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nCancelled", file=sys.stderr)
        return 130
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
