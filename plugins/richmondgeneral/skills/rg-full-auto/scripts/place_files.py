#!/usr/bin/env python3
"""
Place QR codes and images in Richmond General GitHub repo.

Handles file placement for Phase 7 of the workflow. Creates item directories
and saves QR codes from base64 encoding and images to correct locations.

Usage:
    python place_files.py --sku RG-0001 --qr-base64 <base64_data> --image ~/path/to/hero.png
    python place_files.py --sku RG-0001 --qr-base64 <base64_data> --repo-path ~/my-repo/items

Environment:
    HOME - Used to construct default repo path if not specified

"""

import argparse
import base64
import os
import sys
from pathlib import Path


def place_files(
    sku: str,
    qr_base64: str = None,
    image_path: str = None,
    repo_path: str = None
) -> bool:
    """
    Place QR code and/or image in item directory.
    
    Args:
        sku: Item SKU (e.g., RG-0001)
        qr_base64: Base64-encoded QR code PNG data
        image_path: Path to hero image file to copy
        repo_path: Path to GitHub repo items directory (default: ~/workspace/richmondgeneral/items)
    
    Returns:
        True if successful, False otherwise
    """
    
    # Resolve repo path
    if not repo_path:
        repo_path = Path.home() / "workspace" / "square" / "items"
    else:
        repo_path = Path(repo_path)
    
    # Create item directory
    item_dir = repo_path / sku
    try:
        item_dir.mkdir(parents=True, exist_ok=True)
        print(f"📁 Item directory: {item_dir}")
    except Exception as e:
        print(f"❌ Error creating directory {item_dir}: {e}", file=sys.stderr)
        return False
    
    # Save QR code if provided
    if qr_base64:
        qr_path = item_dir / f"{sku}-qr.png"
        try:
            qr_data = base64.b64decode(qr_base64)
            with open(qr_path, 'wb') as f:
                f.write(qr_data)
            print(f"✅ QR code saved: {qr_path}")
        except Exception as e:
            print(f"❌ Error saving QR code: {e}", file=sys.stderr)
            return False
    
    # Copy image if provided
    if image_path:
        src = Path(image_path)
        if not src.exists():
            print(f"❌ Image file not found: {src}", file=sys.stderr)
            return False
        
        # Determine destination filename
        # If it's already named correctly (RG-XXXX-hero.png), keep it
        # Otherwise, rename to RG-XXXX-hero.png
        if src.name.startswith(sku):
            dest_name = src.name
        else:
            dest_name = f"{sku}-hero.png"
        
        dest = item_dir / dest_name
        
        try:
            with open(src, 'rb') as src_file:
                with open(dest, 'wb') as dst_file:
                    dst_file.write(src_file.read())
            print(f"✅ Image copied: {dest}")
        except Exception as e:
            print(f"❌ Error copying image: {e}", file=sys.stderr)
            return False
    
    print(f"\n✅ Files placed for {sku} in {item_dir}")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Place QR codes and images in Richmond General GitHub repo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        '--sku',
        required=True,
        help='Item SKU (e.g., RG-0001)'
    )
    parser.add_argument(
        '--qr-base64',
        help='Base64-encoded QR code PNG data'
    )
    parser.add_argument(
        '--image',
        help='Path to hero image file to copy'
    )
    parser.add_argument(
        '--repo-path',
        help='Path to GitHub repo items directory (default: ~/workspace/richmondgeneral/items)'
    )
    
    args = parser.parse_args()
    
    # Require at least one file to place
    if not args.qr_base64 and not args.image:
        print("Error: Provide at least --qr-base64 or --image", file=sys.stderr)
        parser.print_help()
        sys.exit(1)
    
    success = place_files(
        sku=args.sku,
        qr_base64=args.qr_base64,
        image_path=args.image,
        repo_path=args.repo_path
    )
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
