import json
from item_model.page_writer import write_page_record
from item_model.page_reader import read_page_record
from item_model.models import PageRecord, Channel


def _read(item_dir):
    return json.loads((item_dir / "label.json").read_text(encoding="utf-8"))


def test_write_sets_listed_status_fresh(tmp_path):
    rec = PageRecord(sku="RG-9999", reference_price=25.0, listed_on=[Channel.SQUARE])
    write_page_record(tmp_path / "RG-9999", rec)
    label = _read(tmp_path / "RG-9999")
    assert label["sku"] == "RG-9999"
    assert label["price"] == "25.00"
    assert label["channels"]["square"]["status"] == "listed"


def test_write_preserves_extras_and_channel_ids(tmp_path):
    d = tmp_path / "RG-0001"; d.mkdir()
    (d / "label.json").write_text(json.dumps({
        "sku": "RG-0001", "price": "0.00", "product_name": "Widget",
        "condition": "VG", "channels": {"square": {"status": "pending", "object_id": "OBJ123"}},
    }), encoding="utf-8")
    rec = PageRecord(sku="RG-0001", reference_price=19.5, listed_on=[Channel.SQUARE])
    write_page_record(d, rec)
    label = _read(d)
    assert label["product_name"] == "Widget"          # extra preserved
    assert label["condition"] == "VG"                  # extra preserved
    assert label["channels"]["square"]["object_id"] == "OBJ123"  # platform id preserved
    assert label["channels"]["square"]["status"] == "listed"     # status updated
    assert label["price"] == "19.50"


def test_write_does_not_downgrade_other_channels(tmp_path):
    d = tmp_path / "RG-0002"; d.mkdir()
    (d / "label.json").write_text(json.dumps({
        "sku": "RG-0002", "price": "5.00",
        "channels": {"whatnot": {"status": "sold"}},
    }), encoding="utf-8")
    rec = PageRecord(sku="RG-0002", reference_price=5.0, listed_on=[Channel.SQUARE])
    write_page_record(d, rec)
    label = _read(d)
    assert label["channels"]["whatnot"]["status"] == "sold"   # NOT flipped
    assert label["channels"]["square"]["status"] == "listed"


def test_write_intended_prices(tmp_path):
    rec = PageRecord(sku="RG-0016", reference_price=7.0,
                     listed_on=[Channel.SQUARE, Channel.WHATNOT],
                     intended_channel_prices={Channel.WHATNOT: 6.0})
    write_page_record(tmp_path / "RG-0016", rec)
    assert _read(tmp_path / "RG-0016")["intended_channel_prices"] == {"whatnot": 6.0}


def test_roundtrip_fresh(tmp_path):
    original = PageRecord(sku="RG-0020", reference_price=9.0,
                          listed_on=[Channel.SQUARE, Channel.WHATNOT],
                          intended_channel_prices={Channel.WHATNOT: 8.5})
    write_page_record(tmp_path / "RG-0020", original)
    back = read_page_record(tmp_path / "RG-0020")
    assert back.sku == original.sku
    assert back.reference_price == original.reference_price
    assert set(back.listed_on) == set(original.listed_on)
    assert back.intended_channel_prices == original.intended_channel_prices


def test_write_clears_shrunk_intended_prices(tmp_path):
    d = tmp_path / "RG-0030"; d.mkdir()
    (d / "label.json").write_text(json.dumps({
        "sku": "RG-0030", "price": "5.00", "intended_channel_prices": {"whatnot": 4.0},
    }), encoding="utf-8")
    rec = PageRecord(sku="RG-0030", reference_price=5.0, listed_on=[Channel.SQUARE])  # no overrides
    write_page_record(d, rec)
    assert "intended_channel_prices" not in _read(d)   # stale override cleared, not retained


def test_write_migrates_legacy_listed_on(tmp_path):
    d = tmp_path / "RG-0031"; d.mkdir()
    (d / "label.json").write_text(json.dumps({
        "sku": "RG-0031", "price": "5.00", "listed_on": ["square"],
    }), encoding="utf-8")
    rec = PageRecord(sku="RG-0031", reference_price=5.0, listed_on=[Channel.SQUARE])
    write_page_record(d, rec)
    label = _read(d)
    assert "listed_on" not in label                            # deprecated array removed
    assert label["channels"]["square"]["status"] == "listed"   # migrated into the registry
