#!/usr/bin/env python3
"""
Generate product label CSVs for Print Master batch printing.

Usage:
    python generate_labels.py --type price --output labels.csv
    python generate_labels.py --type detailed --output labels.csv
    
Input: JSON array of products via stdin or --input file
Output: CSV file ready for Print Master import
"""

import argparse
import csv
import json
import sys
from pathlib import Path

# Metric to Imperial conversions
WEIGHT_CONVERSIONS = {
    34: "1.2", 40: "1.4", 48: "1.7", 80: "2.8", 100: "3.5",
    150: "5.3", 200: "7.1", 250: "8.8", 500: "17.6"
}

VOLUME_CONVERSIONS = {
    250: "8.5", 330: "11.2", 350: "11.8", 355: "12.0",
    500: "16.9", 600: "20.3", 1000: "33.8"
}

def grams_to_oz(grams: int) -> str:
    """Convert grams to ounces, using lookup or calculation."""
    if grams in WEIGHT_CONVERSIONS:
        return WEIGHT_CONVERSIONS[grams]
    return f"{grams * 0.035274:.1f}"

def ml_to_floz(ml: int) -> str:
    """Convert milliliters to fluid ounces."""
    if ml in VOLUME_CONVERSIONS:
        return VOLUME_CONVERSIONS[ml]
    return f"{ml * 0.033814:.1f}"

def format_product_name(product: dict) -> str:
    """Format product name according to style guide."""
    brand = product.get('brand', '')
    flavor = product.get('flavor', '')
    size_metric = product.get('size_metric', '')
    size_unit = product.get('size_unit', 'g')
    origin = product.get('origin', '')
    
    # Convert metric to imperial
    try:
        size_num = int(size_metric)
        if size_unit == 'g':
            imperial = f"{grams_to_oz(size_num)}oz"
            metric = f"{size_num}g"
        elif size_unit == 'ml':
            imperial = f"{ml_to_floz(size_num)} fl oz"
            metric = f"{size_num}ml"
        else:
            imperial = f"{size_metric}{size_unit}"
            metric = ""
    except (ValueError, TypeError):
        imperial = size_metric
        metric = ""
    
    # Build name
    name_parts = [brand, flavor]
    name = ' '.join(p for p in name_parts if p)
    
    if imperial:
        name += f" {imperial}"
    if metric:
        name += f" ({metric})"
    if origin:
        name += f" - {origin} Import"
    
    return name

def generate_sku(product: dict) -> str:
    """Generate SKU from product data."""
    category_map = {
        'snack': 'SNACK', 'chips': 'SNACK', 'crackers': 'SNACK',
        'cookie': 'COOKIE', 'cookies': 'COOKIE',
        'candy': 'CANDY', 'chocolate': 'CANDY',
        'beverage': 'BEV', 'drink': 'BEV', 'soda': 'BEV',
        'sage': 'SAGE',
        'vintage': 'VINT',
        'wellness': 'WELL'
    }
    
    cat = product.get('category', 'misc').lower()
    prefix = category_map.get(cat, 'MISC')
    
    # Generate code from brand/flavor
    brand = product.get('brand', 'X')[:1].upper()
    flavor = product.get('flavor', 'XX')[:2].upper()
    size = product.get('size_metric', '00')
    
    lot = product.get('lot_prefix', '')
    if lot:
        return f"{lot}{prefix}-{brand}{flavor}-{size}"
    
    return f"{prefix}-{brand}{flavor}-{size}"

def generate_price_labels(products: list) -> list:
    """Generate simple price label rows."""
    rows = []
    for p in products:
        rows.append({
            'Product Name': format_product_name(p),
            'Price': f"{p.get('price', 0):.2f}",
            'SKU': p.get('sku') or generate_sku(p)
        })
    return rows

def generate_detailed_labels(products: list) -> list:
    """Generate detailed label rows with all info."""
    rows = []
    for p in products:
        size_metric = p.get('size_metric', '')
        size_unit = p.get('size_unit', 'g')
        
        try:
            size_num = int(size_metric)
            if size_unit == 'g':
                imperial = f"{grams_to_oz(size_num)}oz"
            elif size_unit == 'ml':
                imperial = f"{ml_to_floz(size_num)} fl oz"
            else:
                imperial = f"{size_metric}{size_unit}"
        except (ValueError, TypeError):
            imperial = size_metric
            
        rows.append({
            'Product Name': format_product_name(p),
            'Price': f"{p.get('price', 0):.2f}",
            'Size': imperial,
            'Origin': f"{p.get('origin', '')} Import" if p.get('origin') else '',
            'SKU': p.get('sku') or generate_sku(p)
        })
    return rows

def main():
    parser = argparse.ArgumentParser(description='Generate product label CSVs')
    parser.add_argument('--type', choices=['price', 'detailed'], default='price',
                        help='Label type: price (simple) or detailed (full info)')
    parser.add_argument('--input', '-i', type=Path, help='Input JSON file (default: stdin)')
    parser.add_argument('--output', '-o', type=Path, required=True, help='Output CSV file')
    
    args = parser.parse_args()
    
    # Read products
    if args.input:
        with open(args.input) as f:
            products = json.load(f)
    else:
        products = json.load(sys.stdin)
    
    if not isinstance(products, list):
        products = [products]
    
    # Enforce Print Master limit
    if len(products) > 100:
        print(f"Warning: {len(products)} products exceeds Print Master's 100-row limit", 
              file=sys.stderr)
        print("Truncating to first 100 products", file=sys.stderr)
        products = products[:100]
    
    # Generate labels
    if args.type == 'price':
        rows = generate_price_labels(products)
        fieldnames = ['Product Name', 'Price', 'SKU']
    else:
        rows = generate_detailed_labels(products)
        fieldnames = ['Product Name', 'Price', 'Size', 'Origin', 'SKU']
    
    # Write CSV
    with open(args.output, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"Generated {len(rows)} labels to {args.output}")

if __name__ == '__main__':
    main()
