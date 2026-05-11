#!/usr/bin/env python3
"""
Square Catalog Image Upload Script

Uploads images to Square Catalog API using multipart form data.
Supports both creating new images and updating existing ones.

Usage:
    # Upload new image and attach to item
    python upload_image.py --image /path/to/image.jpg --item-id ITEM_ID
    
    # Upload new image and attach to item variation
    python upload_image.py --image /path/to/image.jpg --variation-id VAR_ID
    
    # Replace existing image
    python upload_image.py --image /path/to/image.jpg --image-id IMAGE_ID
    
    # With caption and name
    python upload_image.py --image /path/to/image.jpg --item-id ITEM_ID --name "Product Shot" --caption "Front view"

Environment:
    SQUARE_ACCESS_TOKEN - Required. Your Square API access token.
    SQUARE_API_VERSION - Optional. Defaults to 2025-10-16
"""

import argparse
import json
import os
import sys
import uuid
from pathlib import Path

try:
    import requests
except ImportError:
    print("Error: requests library required. Install with: pip install requests")
    sys.exit(1)


SQUARE_API_BASE = "https://connect.squareup.com"
DEFAULT_API_VERSION = "2026-04-21"


def get_mime_type(file_path: str) -> str:
    """Determine MIME type from file extension."""
    ext = Path(file_path).suffix.lower()
    mime_types = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.webp': 'image/webp',
        '.bmp': 'image/bmp',
        '.tiff': 'image/tiff',
        '.tif': 'image/tiff',
    }
    return mime_types.get(ext, 'application/octet-stream')


def create_catalog_image(
    access_token: str,
    image_path: str,
    object_id: str = None,
    name: str = None,
    caption: str = None,
    is_primary: bool = False,
    api_version: str = DEFAULT_API_VERSION
) -> dict:
    """
    Create a new CatalogImage and optionally attach to an item/variation.
    
    Args:
        access_token: Square API access token
        image_path: Path to local image file
        object_id: Optional item or variation ID to attach image to
        name: Optional image name
        caption: Optional image caption (shown in Square Online)
        is_primary: Whether this should be the primary image
        api_version: Square API version
    
    Returns:
        API response dict with 'image' key containing the created CatalogImage
    """
    url = f"{SQUARE_API_BASE}/v2/catalog/images"
    
    headers = {
        'Square-Version': api_version,
        'Authorization': f'Bearer {access_token}',
        'Accept': 'application/json',
    }
    
    # Build the request JSON
    image_data = {}
    if name:
        image_data['name'] = name
    if caption:
        image_data['caption'] = caption
    
    request_body = {
        'idempotency_key': str(uuid.uuid4()),
        'image': {
            'id': '#TEMP_ID',
            'type': 'IMAGE',
            'image_data': image_data
        }
    }
    
    if object_id:
        request_body['object_id'] = object_id
    if is_primary:
        request_body['is_primary'] = True
    
    # Prepare multipart form data
    mime_type = get_mime_type(image_path)
    
    with open(image_path, 'rb') as f:
        files = {
            'file': (Path(image_path).name, f, mime_type),
            'request': (None, json.dumps(request_body), 'application/json')
        }
        
        response = requests.post(url, headers=headers, files=files)
    
    response.raise_for_status()
    return response.json()


def update_catalog_image(
    access_token: str,
    image_id: str,
    image_path: str,
    name: str = None,
    caption: str = None,
    api_version: str = DEFAULT_API_VERSION
) -> dict:
    """
    Replace the image file of an existing CatalogImage.
    
    Args:
        access_token: Square API access token
        image_id: ID of existing CatalogImage to update
        image_path: Path to new local image file
        name: Optional new image name
        caption: Optional new image caption
        api_version: Square API version
    
    Returns:
        API response dict with updated 'image'
    """
    url = f"{SQUARE_API_BASE}/v2/catalog/images/{image_id}"
    
    headers = {
        'Square-Version': api_version,
        'Authorization': f'Bearer {access_token}',
        'Accept': 'application/json',
    }
    
    # Build the request JSON
    image_data = {}
    if name:
        image_data['name'] = name
    if caption:
        image_data['caption'] = caption
    
    request_body = {
        'idempotency_key': str(uuid.uuid4()),
        'image': {
            'type': 'IMAGE',
            'image_data': image_data
        }
    }
    
    # Prepare multipart form data
    mime_type = get_mime_type(image_path)
    
    with open(image_path, 'rb') as f:
        files = {
            'file': (Path(image_path).name, f, mime_type),
            'request': (None, json.dumps(request_body), 'application/json')
        }
        
        response = requests.put(url, headers=headers, files=files)
    
    response.raise_for_status()
    return response.json()


def main():
    parser = argparse.ArgumentParser(
        description='Upload images to Square Catalog API',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        '--image', '-i',
        required=True,
        help='Path to image file to upload'
    )
    
    # Target options (mutually exclusive for clarity)
    target_group = parser.add_mutually_exclusive_group()
    target_group.add_argument(
        '--item-id',
        help='Catalog item ID to attach image to (creates new image)'
    )
    target_group.add_argument(
        '--variation-id',
        help='Catalog item variation ID to attach image to (creates new image)'
    )
    target_group.add_argument(
        '--image-id',
        help='Existing CatalogImage ID to replace (updates existing image)'
    )
    
    parser.add_argument(
        '--name', '-n',
        help='Image name'
    )
    parser.add_argument(
        '--caption', '-c',
        help='Image caption (shown in Square Online)'
    )
    parser.add_argument(
        '--primary', '-p',
        action='store_true',
        help='Set as primary image for the item'
    )
    parser.add_argument(
        '--token', '-t',
        help='Square access token (or set SQUARE_ACCESS_TOKEN env var)'
    )
    parser.add_argument(
        '--api-version',
        default=os.environ.get('SQUARE_API_VERSION', DEFAULT_API_VERSION),
        help=f'Square API version (default: {DEFAULT_API_VERSION})'
    )
    parser.add_argument(
        '--json', '-j',
        action='store_true',
        help='Output full JSON response'
    )
    
    args = parser.parse_args()
    
    # Get access token
    access_token = args.token or os.environ.get('SQUARE_ACCESS_TOKEN')
    if not access_token:
        print("Error: Square access token required.", file=sys.stderr)
        print("Set SQUARE_ACCESS_TOKEN environment variable or use --token", file=sys.stderr)
        sys.exit(1)
    
    # Validate image file
    if not os.path.exists(args.image):
        print(f"Error: Image file not found: {args.image}", file=sys.stderr)
        sys.exit(1)
    
    try:
        if args.image_id:
            # Update existing image
            print(f"Updating image {args.image_id}...")
            result = update_catalog_image(
                access_token=access_token,
                image_id=args.image_id,
                image_path=args.image,
                name=args.name,
                caption=args.caption,
                api_version=args.api_version
            )
        else:
            # Create new image
            object_id = args.item_id or args.variation_id
            print(f"Creating new image" + (f" attached to {object_id}" if object_id else "") + "...")
            result = create_catalog_image(
                access_token=access_token,
                image_path=args.image,
                object_id=object_id,
                name=args.name,
                caption=args.caption,
                is_primary=args.primary,
                api_version=args.api_version
            )
        
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            image = result.get('image', {})
            print(f"\n✅ Success!")
            print(f"   Image ID: {image.get('id')}")
            print(f"   URL: {image.get('image_data', {}).get('url')}")
            if image.get('image_data', {}).get('name'):
                print(f"   Name: {image['image_data']['name']}")
            if image.get('image_data', {}).get('caption'):
                print(f"   Caption: {image['image_data']['caption']}")
                
    except requests.exceptions.HTTPError as e:
        print(f"Error: API request failed: {e}", file=sys.stderr)
        if e.response is not None:
            try:
                error_detail = e.response.json()
                print(json.dumps(error_detail, indent=2), file=sys.stderr)
            except:
                print(e.response.text, file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
