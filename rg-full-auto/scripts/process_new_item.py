#!/usr/bin/env python3
"""
Richmond General - New Item Processing Workflow

Claude-supervised, agent-run workflow for processing items from photo to live listing.

This script orchestrates the 7-phase workflow:
1. Appraisal & Research (visual analysis)
2. Photography (background removal)
3. Square Catalog Creation
4. Image Upload to Square
5. Fulfillment Setup (manual step)
6. Payment Link Generation
7. Label CSV & GitHub Pages

Usage:
    # Interactive mode (Claude supervises each step)
    python process_new_item.py --image photo.jpeg --interactive
    
    # Batch mode (future - unsupervised)
    python process_new_item.py --image photo.jpeg --auto

Environment Variables Required:
    SQUARE_ACCESS_TOKEN - Square API access token
    REMOVEBG_API_KEY - remove.bg API key
"""

import argparse
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Dict, Optional

try:
    import requests
except ImportError:
    print("Error: requests library required. Install with: pip install requests")
    sys.exit(1)


class RGItemProcessor:
    """Processes new items through the complete Richmond General workflow."""
    
    def __init__(self, interactive: bool = True):
        self.interactive = interactive
        self.square_token = os.environ.get('SQUARE_ACCESS_TOKEN')
        self.removebg_token = os.environ.get('REMOVEBG_API_KEY')
        self.location_id = "B87BAEZ0NWV34"  # Richmond General
        self.categories = {
            'timeless_treasures': '3N3II4W6Q7AA43RWQGEEWELY',
            'new_finds': 'P34KX3L7XRZJJ5RP6W35K4YO'
        }
        
        if not self.square_token:
            raise ValueError("SQUARE_ACCESS_TOKEN environment variable required")
        if not self.removebg_token:
            raise ValueError("REMOVEBG_API_KEY environment variable required")
    
    def get_next_sku(self) -> str:
        """Generate next available SKU number."""
        max_num = 0
        for item in Path('.').glob('RG-*'):
            if item.is_dir():
                try:
                    num = int(item.name.replace('RG-', ''))
                    max_num = max(max_num, num)
                except ValueError:
                    continue
        return f"RG-{max_num + 1:04d}"
    
    def prompt(self, message: str, default: str = "") -> str:
        """Interactive prompt for user supervision."""
        if not self.interactive:
            return default
        response = input(f"{message}: ").strip()
        return response if response else default
    
    def confirm(self, message: str) -> bool:
        """Ask for user confirmation."""
        if not self.interactive:
            return True
        response = input(f"{message} (y/n): ").strip().lower()
        return response == 'y'
    
    def phase1_research(self, image_path: str) -> Dict:
        """Phase 1: Appraisal & Research (requires Claude visual analysis)."""
        print("\n=== PHASE 1: APPRAISAL & RESEARCH ===")
        print("📸 Image loaded. Claude should analyze this image for:")
        print("  - Item identification")
        print("  - Era/dating")
        print("  - Condition assessment")
        print("  - Comparable sales research")
        print("  - Price recommendation")
        print("\n⚠️  This phase requires Claude's visual analysis capabilities.")
        print("    Continue workflow after Claude provides appraisal.\n")
        
        # In interactive mode, collect appraisal data
        item_data = {
            'sku': self.prompt("SKU", self.get_next_sku()),
            'title': self.prompt("Item title"),
            'era': self.prompt("Era (e.g., 1930s)"),
            'price': float(self.prompt("Price (dollars)", "19.99")),
            'condition': self.prompt("Condition (e.g., Very Good)"),
            'maker': self.prompt("Maker/Publisher"),
            'origin': self.prompt("Origin (e.g., USA)"),
            'description': self.prompt("Description (HTML with <br> tags)"),
            'seo_title': self.prompt("SEO Title"),
            'seo_description': self.prompt("SEO Description (150-160 chars)"),
            'permalink': self.prompt("Permalink slug"),
        }
        
        return item_data
    
    def phase2_photography(self, input_path: str, sku: str) -> Dict:
        """Phase 2: Photography & Background Removal."""
        print(f"\n=== PHASE 2: PHOTOGRAPHY ===")
        
        # Save original
        working_dir = Path('assets/working-images')
        working_dir.mkdir(parents=True, exist_ok=True)
        original_path = working_dir / f"{sku}-hero.jpeg"
        
        print(f"💾 Saving original: {original_path}")
        # Copy input to working-images (would be done by Claude in actual workflow)
        
        # Remove background
        converted_path = Path(f"{sku}-hero-converted.png")
        print(f"🎨 Removing background...")
        
        # Call remove.bg
        with open(input_path, 'rb') as f:
            response = requests.post(
                "https://api.remove.bg/v1.0/removebg",
                files={'image_file': f},
                data={'size': 'auto'},
                headers={'X-Api-Key': self.removebg_token},
            )
        response.raise_for_status()
        
        with open(converted_path, 'wb') as out:
            out.write(response.content)
        
        print(f"✅ Background removed: {converted_path}")
        
        return {
            'original_path': str(original_path),
            'converted_path': str(converted_path)
        }
    
    def phase3_catalog(self, item_data: Dict) -> Dict:
        """Phase 3: Square Catalog Creation."""
        print(f"\n=== PHASE 3: SQUARE CATALOG CREATION ===")
        
        price_cents = int(item_data['price'] * 100)
        sku = item_data['sku']
        
        catalog_request = {
            "idempotency_key": str(uuid.uuid4()),
            "batches": [{
                "objects": [{
                    "type": "ITEM",
                    "id": f"#{sku}",
                    "present_at_all_locations": False,
                    "present_at_location_ids": [self.location_id],
                    "item_data": {
                        "name": item_data['title'],
                        "description": item_data['description'],
                        "categories": [
                            {"id": self.categories['timeless_treasures']},
                            {"id": self.categories['new_finds']}
                        ],
                        "reporting_category": {"id": self.categories['new_finds']},
                        "tax_ids": ["LPKEJF7H27NOPK7EE6A5CA7V"],
                        "is_taxable": True,
                        "ecom_visibility": "VISIBLE",
                        "ecom_seo_data": {
                            "page_title": item_data['seo_title'],
                            "page_description": item_data['seo_description'],
                            "permalink": item_data['permalink']
                        },
                        "variations": [{
                            "type": "ITEM_VARIATION",
                            "id": f"#{sku}-var",
                            "item_variation_data": {
                                "item_id": f"#{sku}",
                                "name": "Regular",
                                "sku": sku,
                                "pricing_type": "FIXED_PRICING",
                                "price_money": {
                                    "amount": price_cents,
                                    "currency": "USD"
                                },
                                "track_inventory": True,
                                "sellable": True,
                                "stockable": True
                            }
                        }]
                    }
                }]
            }]
        }
        
        print(f"📦 Creating catalog item: {sku}")
        response = requests.post(
            "https://connect.squareup.com/v2/catalog/batch-upsert",
            headers={
                'Square-Version': '2025-10-16',
                'Authorization': f'Bearer {self.square_token}',
                'Content-Type': 'application/json'
            },
            json=catalog_request
        )
        response.raise_for_status()
        
        result = response.json()
        item_id = result['objects'][0]['id']
        variation_id = result['objects'][0]['item_data']['variations'][0]['id']
        
        print(f"✅ Catalog item created!")
        print(f"   Item ID: {item_id}")
        print(f"   Variation ID: {variation_id}")
        
        # Set inventory count to 1
        self._set_inventory(variation_id)
        
        return {
            'item_id': item_id,
            'variation_id': variation_id
        }
    
    def _set_inventory(self, variation_id: str):
        """Set inventory count to 1 for new item."""
        print(f"📊 Setting inventory count to 1...")
        
        inventory_request = {
            "idempotency_key": str(uuid.uuid4()),
            "changes": [{
                "type": "PHYSICAL_COUNT",
                "physical_count": {
                    "catalog_object_id": variation_id,
                    "state": "IN_STOCK",
                    "location_id": self.location_id,
                    "quantity": "1",
                    "occurred_at": "2025-12-20T00:00:00Z"
                }
            }]
        }
        
        response = requests.post(
            "https://connect.squareup.com/v2/inventory/batch-change",
            headers={
                'Square-Version': '2025-10-16',
                'Authorization': f'Bearer {self.square_token}',
                'Content-Type': 'application/json'
            },
            json=inventory_request
        )
        response.raise_for_status()
        print(f"✅ Inventory set to 1")
    
    def run(self, image_path: str):
        """Run the complete workflow."""
        print("=" * 60)
        print("RICHMOND GENERAL - NEW ITEM WORKFLOW")
        print("=" * 60)
        
        # Phase 1: Research
        item_data = self.phase1_research(image_path)
        
        if not self.confirm("\n✅ Continue to Phase 2 (Photography)?"):
            print("Workflow cancelled.")
            return
        
        # Phase 2: Photography
        photo_data = self.phase2_photography(image_path, item_data['sku'])
        
        if not self.confirm("\n✅ Continue to Phase 3 (Square Catalog)?"):
            print("Workflow cancelled.")
            return
        
        # Phase 3: Catalog Creation
        catalog_data = self.phase3_catalog(item_data)
        
        print("\n" + "=" * 60)
        print("PHASE 3 COMPLETE - Remaining phases require additional implementation:")
        print("  Phase 2b: Upload image to Square (use square-image-upload)")
        print("  Phase 4: Fulfillment setup (Square Dashboard - manual)")
        print("  Phase 5: Payment link generation")
        print("  Phase 6: Label CSV")
        print("  Phase 7: GitHub Pages deployment")
        print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description='Process new Richmond General items through complete workflow',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        '--image', '-i',
        required=True,
        help='Path to item photo'
    )
    parser.add_argument(
        '--interactive',
        action='store_true',
        default=True,
        help='Interactive mode with user supervision (default)'
    )
    parser.add_argument(
        '--auto',
        action='store_true',
        help='Automatic mode (unsupervised - future)'
    )
    
    args = parser.parse_args()
    
    try:
        processor = RGItemProcessor(interactive=not args.auto)
        processor.run(args.image)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
