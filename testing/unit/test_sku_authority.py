import pytest
from sku_authority import (
    format_sku, format_counter_name, parse_counter_n, parse_rg_n,
    SkuAllocationError,
)

def test_format_sku_zero_pads():
    assert format_sku(31) == "RG-0031"
    assert format_sku(7) == "RG-0007"

def test_format_counter_name_roundtrips():
    assert parse_counter_n(format_counter_name(30)) == 30

def test_parse_rg_n_matches_only_real_skus():
    assert parse_rg_n("RG-0030") == 30
    assert parse_rg_n("__RG_SKU_COUNTER__") is None      # sentinel never counts
    assert parse_rg_n("RG-SKU-COUNTER:0030") is None     # counter name never counts
    assert parse_rg_n("RG-0030-test") is None

def test_parse_counter_n_rejects_garbage():
    with pytest.raises(SkuAllocationError):
        parse_counter_n("not-a-counter")
