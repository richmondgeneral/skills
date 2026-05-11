#!/usr/bin/env python3
"""
Richmond General - New Item Processing Workflow

Claude-supervised, agent-run workflow for processing items from photo to live listing.

This script orchestrates phases 0-3 of the 10-phase SKILL.md workflow:
0. Image Processing (background removal, file prep)
1. Appraisal & Research (visual analysis)
2. Square Catalog Creation (uses description_html with <p> tags per v3.2)
3. Inventory Setup

Phases 4-9 (image upload, payment link, label, info card, Whatnot,
Photos archive) are documented in SKILL.md and run via sibling skills /
osascript steps; the script prints next-step hints at the end of run().

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
from datetime import datetime, timezone
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
            'real_rarities': 'FL4L42RRUE5UXMWFDLXOCNB5',
            'new_finds': 'P34KX3L7XRZJJ5RP6W35K4YO'
        }
        
        if not self.square_token:
            raise ValueError("SQUARE_ACCESS_TOKEN environment variable required")
        if not self.removebg_token:
            raise ValueError("REMOVEBG_API_KEY environment variable required")
    
    def get_next_sku(self) -> str:
        """Generate next available SKU number.
        
        NOTE: This is a fallback local directory scan.
        Preferred method: Use square-cache skill (MCP) to query existing SKUs.
        See SKILL.md Phase 0 for details.
        """
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
    
    def phase1_research(self, image_path: str, default_sku: Optional[str] = None) -> Dict:
        """Phase 1: Appraisal & Research (requires Claude visual analysis).

        Pass `default_sku` when the caller has already allocated one (so the
        prompt suggests the SKU we used for the working-image filename in
        phase2_photography). If omitted, falls back to scanning local dirs.
        """
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
            'sku': self.prompt("SKU", default_sku or self.get_next_sku()),
            'title': self.prompt("Item title"),
            'era': self.prompt("Era (e.g., 1930s)"),
            'price': float(self.prompt("Price (dollars)", "19.99")),
            'condition': self.prompt("Condition (e.g., Very Good)"),
            'maker': self.prompt("Maker/Publisher"),
            'origin': self.prompt("Origin (e.g., USA)"),
            'description': self.prompt("Description (HTML with <p> tags)"),
            'seo_title': self.prompt("SEO Title"),
            'seo_description': self.prompt("SEO Description (150-160 chars)"),
            'permalink': self.prompt("Permalink slug"),
        }
        
        return item_data
    
    def phase2_photography(self, input_path: str, sku: str) -> Dict:
        """Phase 2: Photography & Background Removal.
        
        NOTE: This only handles background removal via remove.bg API.
        Image upload to Square must be done via the square-image-upload skill (MCP)
        to avoid 403 authentication errors. See SKILL.md Phase 2 for details.
        """
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
        print(f"\n⚠️  NEXT: Use square-image-upload skill to upload {converted_path}")
        print(f"   Do NOT use direct API calls - use MCP-based square-image-upload skill")
        
        return {
            'original_path': str(original_path),
            'converted_path': str(converted_path)
        }

    def _square_headers(self) -> Dict[str, str]:
        """Shared headers for Square API calls."""
        return {
            'Square-Version': '2026-04-21',
            'Authorization': f'Bearer {self.square_token}',
            'Content-Type': 'application/json'
        }

    # Map TYPE category -> ROOM (top-level parent) category. Verified against
    # the live Square catalog (searchObjects/CATEGORY) on 2026-05-11. Adding an
    # item to its room ensures it appears in the "Shop All <Room>" flat product
    # grid below the storefront hero tiles (e.g., /shop/the-general-store/...
    # and /shop/the-vintage-market/...). See May 2026 enrollment incident and
    # references/square-catalog.md for the full hierarchy.
    ROOM_BY_TYPE = {
        # The General Store (QLM2GZ643LOCYHB653YIDJWT)
        'I5PMPWGTVR7IDBL4RUJWN3A4': 'QLM2GZ643LOCYHB653YIDJWT',  # Wellness & Apothecary
        'AR3ZTA45KU4BH23AJ7LOLLRA': 'QLM2GZ643LOCYHB653YIDJWT',  # Gifts
        'CLZCJ62H4TTHDQ3ZBYMZQASQ': 'QLM2GZ643LOCYHB653YIDJWT',  # Books & Paper
        'APSTFSN4UXQI44HBFSDTSEX7': 'QLM2GZ643LOCYHB653YIDJWT',  # Pottery & Ceramics
        'CYTCL6ES7TSG2XCUVHIDG5B2': 'QLM2GZ643LOCYHB653YIDJWT',  # Food & Pantry
        '43IPDJV36K4AX55M4QFPYHHO': 'QLM2GZ643LOCYHB653YIDJWT',  # Home
        'F4JQYK4Z5MEBV5VFCDYHIAWT': 'QLM2GZ643LOCYHB653YIDJWT',  # Art & Craft Kits
        # The Vintage Market (TX6SBQLJDMZOCVXBUD3KT3CL)
        'W3EYAJJPTNC46WSLNYI4WH7V': 'TX6SBQLJDMZOCVXBUD3KT3CL',  # Furniture
        'YQWBSOJDENMXDGUUQ3TGI3HF': 'TX6SBQLJDMZOCVXBUD3KT3CL',  # Collectibles
        'QPDGKT3BGR63MSZ6AQ6VI4ZP': 'TX6SBQLJDMZOCVXBUD3KT3CL',  # Vintage Media
        'N35REXL33FZWJNJV24IUQGPN': 'TX6SBQLJDMZOCVXBUD3KT3CL',  # Analog
        'XQY33UQNPA7IPZ4CBIYJX3VM': 'TX6SBQLJDMZOCVXBUD3KT3CL',  # Trésor Vintage Market
    }

    # Categories that are themselves top-level rooms (is_top_level: true in
    # Square). When an item's TYPE is one of these, no ROOM upcast is needed
    # — the type IS the room — so we don't emit the "not in ROOM_BY_TYPE"
    # warning. Verified live 2026-05-11.
    TOP_LEVEL_ROOMS = {
        'QLM2GZ643LOCYHB653YIDJWT',  # The General Store
        'TX6SBQLJDMZOCVXBUD3KT3CL',  # The Vintage Market
        'QIPW32HGKMU5BDPU3A7YZCM4',  # The Apothecary Cabinet
        'UMWTT7Q6UU4PXPUKU3DVNLFJ',  # The Gallery
        'TGWDFETSQPR6BF67YJCTOLW6',  # New Arrivals
    }

    def _build_catalog_object(self, item_data: Dict, price_cents: int, sku: str) -> Dict:
        """Build a catalog ITEM object shared by both create methods.

        Per catalog-classifier v2.0+ (refactored Feb 2026), every item must carry:
          - a TYPE category (Books & Paper, Pottery & Ceramics, Collectibles, etc.),
            consumed by storefront nav surfaces and by reporting_category for analytics
          - a TIER category (New Finds or Real Rarities), required so items appear in
            tier-level nav surfaces and don't fall off the storefront's discovery index
          - a ROOM category (The General Store or The Vintage Market), the top-level
            parent under which the storefront hero tiles route. Auto-derived from
            type_category_id via ROOM_BY_TYPE.

        Items shipped without these end up invisible to one or more nav paths on
        richmondgeneral.com — see RG-0004 / RG-0010 / Vintage Market enrollment
        incidents (May 2026).

        Callers should pass `type_category_id` in item_data (resolved upstream via
        the catalog-classifier skill). If absent, we log a warning and ship with
        only the tier so the item still gets onto the storefront, but the gap
        should be patched at the caller.
        """
        tier_category_id = item_data.get(
            'tier_category_id', self.categories['new_finds']
        )
        type_category_id = item_data.get('type_category_id')

        if type_category_id:
            categories = [
                {"id": type_category_id},
                {"id": tier_category_id},
            ]
            # Auto-derive ROOM from TYPE so items show on the "Shop All <Room>"
            # flat product grid below the storefront hero tiles.
            room_id = self.ROOM_BY_TYPE.get(type_category_id)
            if room_id:
                categories.append({"id": room_id})
            elif type_category_id in self.TOP_LEVEL_ROOMS:
                # The type IS already a top-level room (Apothecary Cabinet,
                # Gallery, etc.). No upcast needed — the type already routes
                # the item to its own Shop All grid.
                pass
            else:
                print(
                    f"⚠️  {sku}: type_category_id '{type_category_id}' not in "
                    f"ROOM_BY_TYPE map — item will be reachable via its type "
                    f"sub-category but won't show on the room-level Shop All grid. "
                    f"Update ROOM_BY_TYPE in process_new_item.py."
                )
            # Per square-catalog.md spec, reporting_category is the TYPE.
            reporting_category_id = type_category_id
        else:
            print(
                f"⚠️  {sku}: no type_category_id provided — shipping with TIER only "
                f"({tier_category_id}). Item may be hard to discover on the storefront. "
                f"Patch the caller to resolve a TYPE via catalog-classifier."
            )
            categories = [{"id": tier_category_id}]
            reporting_category_id = tier_category_id

        return {
            "type": "ITEM",
            "id": f"#{sku}",
            "present_at_all_locations": False,
            "present_at_location_ids": [self.location_id],
            "item_data": {
                "name": item_data['title'],
                # description_html (with <p> tags) per v3.2 BREAKING change;
                # the plain `description` field is deprecated and would render
                # raw HTML tags on richmondgeneral.com.
                "description_html": item_data['description'],
                "categories": categories,
                "reporting_category": {"id": reporting_category_id},
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
                    "present_at_all_locations": False,
                    "present_at_location_ids": [self.location_id],
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
        }

    def _extract_catalog_ids(self, result: Dict, sku: str) -> Dict[str, str]:
        """
        Extract item and variation IDs from Square catalog responses.

        Prioritizes `id_mappings` for reliability, then falls back to object traversal.
        """
        temp_item_id = f"#{sku}"
        temp_variation_id = f"#{sku}-var"

        id_mappings = result.get('id_mappings', []) or []
        mapped = {
            m.get('client_object_id'): m.get('object_id')
            for m in id_mappings
            if m.get('client_object_id') and m.get('object_id')
        }

        item_id = mapped.get(temp_item_id)
        variation_id = mapped.get(temp_variation_id)

        catalog_object = result.get('catalog_object')
        if not catalog_object:
            objects = result.get('objects', []) or []
            catalog_object = objects[0] if objects else {}

        if not item_id:
            item_id = catalog_object.get('id')

        if not variation_id:
            variations = catalog_object.get('item_data', {}).get('variations', []) or []
            if variations:
                variation_id = variations[0].get('id')

        if not item_id or not variation_id:
            raise ValueError("Could not resolve catalog item/variation IDs from Square response")

        return {
            'item_id': item_id,
            'variation_id': variation_id,
        }

    def phase3_catalog(self, item_data: Dict) -> Dict:
        """Phase 3: Square Catalog Creation."""
        print(f"\n=== PHASE 3: SQUARE CATALOG CREATION ===")
        
        price_cents = int(item_data['price'] * 100)
        sku = item_data['sku']

        catalog_object = self._build_catalog_object(item_data, price_cents, sku)
        idempotency_key = str(uuid.uuid4())

        attempts = [
            (
                'batch-upsert',
                "https://connect.squareup.com/v2/catalog/batch-upsert",
                {
                    "idempotency_key": idempotency_key,
                    "batches": [{
                        "objects": [catalog_object]
                    }]
                }
            ),
            (
                'upsertCatalogObject',
                "https://connect.squareup.com/v2/catalog/object",
                {
                    "idempotency_key": idempotency_key,
                    "object": catalog_object
                }
            )
        ]

        print(f"📦 Creating catalog item: {sku}")
        last_error: Optional[Exception] = None
        catalog_ids: Optional[Dict[str, str]] = None

        for index, (method_name, url, payload) in enumerate(attempts):
            try:
                print(f"   → Trying {method_name}")
                response = requests.post(
                    url,
                    headers=self._square_headers(),
                    json=payload
                )
                response.raise_for_status()
                result = response.json()
                catalog_ids = self._extract_catalog_ids(result, sku)
                break
            except Exception as e:
                last_error = e
                if index < len(attempts) - 1:
                    print(f"   ⚠️ {method_name} failed ({e}); attempting fallback.")
                    continue
                raise

        if not catalog_ids:
            raise RuntimeError(f"Catalog creation failed: {last_error}")

        item_id = catalog_ids['item_id']
        variation_id = catalog_ids['variation_id']
        
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
                    "occurred_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                }
            }]
        }
        
        response = requests.post(
            "https://connect.squareup.com/v2/inventory/batch-change",
            headers=self._square_headers(),
            json=inventory_request
        )
        response.raise_for_status()
        print(f"✅ Inventory set to 1")
    
    def run(self, image_path: str):
        """Run the complete workflow.

        Ordering per SKILL.md: Phase 0 (background removal) runs FIRST so
        the appraiser views the processed hero image in Phase 1 Step 1.0,
        not the raw input. The previous research-before-photography ordering
        forced Claude to appraise from the unprocessed shot and burned the
        bg-removal API credit even when the user bailed at research.
        """
        print("=" * 60)
        print("RICHMOND GENERAL - NEW ITEM WORKFLOW")
        print("=" * 60)

        # Phase 0 / 2 in script terms: photography (background removal first).
        # We need a SKU for the working filename; fall back to the next-available
        # local SKU if Claude hasn't supplied one upstream via square-cache.
        sku = self.get_next_sku()
        photo_data = self.phase2_photography(image_path, sku)

        if not self.confirm("\n✅ Continue to Phase 1 (Appraisal & Research)?"):
            print("Workflow cancelled.")
            return

        # Phase 1: appraisal/research with the cleaned hero in hand.
        item_data = self.phase1_research(image_path, default_sku=sku)

        if not self.confirm("\n✅ Continue to Phase 3 (Square Catalog)?"):
            print("Workflow cancelled.")
            return

        # Phase 3: Catalog Creation
        catalog_data = self.phase3_catalog(item_data)
        
        print("\n" + "=" * 60)
        print("PHASE 3 COMPLETE - Remaining phases require additional implementation:")
        print("  Phase 2b: Upload image to Square (use square-image-upload skill)")
        print("  Phase 4: Fulfillment setup (Square Dashboard - manual)")
        print("  Phase 5: Payment link generation")
        print("  Phase 6: Label CSV")
        print("  Phase 7: GitHub Pages deployment")
        print("\nFor Phase 7 file placement, use place_files.py:")
        print("  python3 ~/.claude/skills/rg-full-auto/scripts/place_files.py \\")
        print("    --sku RG-XXXX --qr-base64 <data> --image <path>")
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
