import pytest
from generate_labels import grams_to_oz, ml_to_floz, format_product_name, generate_sku

def test_grams_to_oz():
    # Test exact lookups
    assert grams_to_oz(34) == "1.2"
    assert grams_to_oz(100) == "3.5"
    
    # Test calculation
    # 50g * 0.035274 = 1.7637 -> 1.8
    assert grams_to_oz(50) == "1.8"

def test_ml_to_floz():
    # Test exact lookups
    assert ml_to_floz(500) == "16.9"
    
    # Test calculation
    # 100ml * 0.033814 = 3.3814 -> 3.4
    assert ml_to_floz(100) == "3.4"

def test_format_product_name():
    # Standard snack
    product = {
        'brand': 'Lays',
        'flavor': 'Seaweed',
        'size_metric': 70,
        'size_unit': 'g',
        'origin': 'China'
    }
    # 70g -> 2.5oz
    expected = "Lays Seaweed 2.5oz (70g) - China Import"
    assert format_product_name(product) == expected

    # Beverage
    drink = {
        'brand': 'Pepsi',
        'flavor': 'Peach',
        'size_metric': 500,
        'size_unit': 'ml',
        'origin': 'Japan'
    }
    expected = "Pepsi Peach 16.9 fl oz (500ml) - Japan Import"
    assert format_product_name(drink) == expected

def test_generate_sku():
    # Basic snack
    item = {
        'category': 'snack',
        'brand': 'Lays',
        'flavor': 'Seaweed',
        'size_metric': '70'
    }
    # SNACK-LSE-70 (Lays, SEaweed)
    assert generate_sku(item) == "SNACK-LSE-70"
    
    # With Lot prefix
    lot_item = {
        'category': 'vintage',
        'brand': 'Fenton',
        'flavor': 'Bowl', # flavor field reused for vintage descriptor often
        'size_metric': '01',
        'lot_prefix': 'L2-'
    }
    # L2-VINT-FBO-01 (Fenton, BOwl)
    assert generate_sku(lot_item) == "L2-VINT-FBO-01"
