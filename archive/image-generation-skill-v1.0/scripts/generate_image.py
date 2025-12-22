#!/usr/bin/env python3
"""
Image Generation Script using Gemini Nano Banana

Generate images from text prompts with automatic model selection.
Supports style transfer from reference images.

Usage:
    python generate_image.py --prompt "text description" --output result.png
    python generate_image.py --prompt "apply this style" --reference style.jpg --output result.png
    python generate_image.py --prompt "create logo" --quality pro --output logo.png
"""

import argparse
import sys
import json
from pathlib import Path

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'lib'))

from gemini_api import GeminiAPI, GeminiAPIError, save_image


def main():
    parser = argparse.ArgumentParser(
        description='Generate images using Gemini Nano Banana',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        '--prompt',
        required=True,
        help='Text description of desired image'
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
        help='Reference image for style transfer (can specify multiple)'
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
        # Initialize API client
        if args.verbose:
            print(f"Initializing Gemini API...")
        api = GeminiAPI(api_key=args.api_key)
        
        # Select model
        model = GeminiAPI.select_model(
            args.prompt,
            reference_images=args.references,
            quality_hint=args.quality
        )
        
        if args.verbose:
            print(f"Selected model: {model}")
            if args.references:
                print(f"Reference images: {len(args.references)}")
        
        # Generate image
        if args.verbose:
            print(f"Generating image...")
            
        image_data, metadata = api.generate_image(
            prompt=args.prompt,
            model=model,
            reference_images=args.references
        )
        
        # Save result
        save_image(image_data, args.output)
        
        if args.verbose:
            print(f"✅ Image saved: {args.output}")
        
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
