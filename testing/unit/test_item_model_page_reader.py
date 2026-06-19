import json
from item_model.page_reader import read_page_record
from item_model.models import Channel

def _write_item(items_dir, sku, label, status=None):
    d = items_dir / sku
    d.mkdir(parents=True)
    (d / "label.json").write_text(json.dumps(label), encoding="utf-8")
    if status is not None:
        (d / "status.json").write_text(json.dumps(status), encoding="utf-8")
    return d

def test_reads_reference_price_and_defaults(tmp_path):
    _write_item(tmp_path, "RG-0009", {"sku": "RG-0009", "price": "95.00"})
    rec = read_page_record(tmp_path / "RG-0009")
    assert rec.sku == "RG-0009"
    assert rec.reference_price == 95.0
    assert rec.sold is False

def test_status_json_marks_sold(tmp_path):
    _write_item(tmp_path, "RG-0003",
                {"sku": "RG-0003", "price": "25.00"},
                {"status": "sold"})
    rec = read_page_record(tmp_path / "RG-0003")
    assert rec.sold is True

def test_optional_listed_on_and_intended_prices(tmp_path):
    _write_item(tmp_path, "RG-0016", {
        "sku": "RG-0016", "price": "7.00",
        "listed_on": ["square", "whatnot"],
        "intended_channel_prices": {"whatnot": 6.0},
    })
    rec = read_page_record(tmp_path / "RG-0016")
    assert Channel.WHATNOT in rec.listed_on
    assert rec.intended_channel_prices[Channel.WHATNOT] == 6.0
