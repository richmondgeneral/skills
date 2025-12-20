#!/usr/bin/env python3
"""
Background Removal for Richmond General Items

Uses remove.bg API to process product photos for Square catalog.
Fast, listing-ready quality for batch processing.

Usage:
    python remove_background.py input.jpeg output.png
    
Environment:
    REMOVEBG_API_KEY - Required. Your remove.bg API key.
"""

import argparse
import os
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    print("Error: requests library required. Install with: pip install requests")
    sys.exit(1)


REMOVEBG_API_URL = "https://api.remove.bg/v1.0/removebg"


def remove_background(input_path: str, output_path: str, api_key: str) -> None:
    """
    Remove background from image using remove.bg API.
    
    Args:
        input_path: Path to input image
        output_path: Path to save processed image
        api_key: remove.bg API key
    """
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")
    
    print(f"Removing background from {Path(input_path).name}...")
    
    with open(input_path, 'rb') as f:
        response = requests.post(
            REMOVEBG_API_URL,
            files={'image_file': f},
            data={'size': 'auto'},  # Full resolution
            headers={'X-Api-Key': api_key},
        )
    
    response.raise_for_status()
    
    # Save the result
    with open(output_path, 'wb') as out:
        out.write(response.content)
    
    print(f"✅ Background removed: {output_path}")
    print(f"   API credits remaining: {response.headers.get('X-Credits-Charged', 'Unknown')}")


def main():
    parser = argparse.ArgumentParser(
        description='Remove background from product images using remove.bg',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        'input',
        help='Input image file'
    )
    parser.add_argument(
        'output',
        help='Output image file (PNG recommended)'
    )
    parser.add_argument(
        '--api-key',
        help='remove.bg API key (or set REMOVEBG_API_KEY env var)'
    )
    
    args = parser.parse_args()
    
    # Get API key
    api_key = args.api_key or os.environ.get('REMOVEBG_API_KEY')
    if not api_key:
        print("Error: remove.bg API key required.", file=sys.stderr)
        print("Set REMOVEBG_API_KEY environment variable or use --api-key", file=sys.stderr)
        print("\nGet your API key at: https://remove.bg/api", file=sys.stderr)
        sys.exit(1)
    
    try:
        remove_background(args.input, args.output, api_key)
    except requests.exceptions.HTTPError as e:
        print(f"Error: API request failed: {e}", file=sys.stderr)
        if e.response is not None:
            print(f"Status: {e.response.status_code}", file=sys.stderr)
            print(f"Response: {e.response.text}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
