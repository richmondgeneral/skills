import json
from reconcile import run_reconcile, heal_guidance


def _item(items_dir, sku, price, status=None, label_extra=None):
    d = items_dir / sku; d.mkdir(parents=True)
    label = {"sku": sku, "price": price}
    if label_extra:
        label.update(label_extra)
    (d / "label.json").write_text(json.dumps(label), encoding="utf-8")
    if status:
        (d / "status.json").write_text(json.dumps({"status": status}), encoding="utf-8")


def test_run_reports_price_drift_and_sold_conflict(tmp_path):
    items_dir = tmp_path / "items"; items_dir.mkdir()
    _item(items_dir, "RG-0009", "95.00")              # square shows 45 -> WARNING
    _item(items_dir, "RG-0003", "25.00", status="sold")  # square active -> CRITICAL

    square_index = {"RG-0009": (4500, False), "RG-0003": (2500, False)}
    whatnot_index = {}

    report = run_reconcile(
        items_dir=str(items_dir),
        square_index=square_index,
        whatnot_index=whatnot_index,
    )
    sev = {(f["sku"], f["field"]): f["severity"] for f in report["findings"]}
    assert sev[("RG-0009", "price")] == "warning"
    assert sev[("RG-0003", "sold_state")] == "critical"
    assert report["summary"]["critical"] == 1
    assert report["summary"]["warning"] == 1
    assert report["items_scanned"] == 2


def test_heal_guidance_routes_to_right_tool():
    price = heal_guidance({"sku": "RG-0009", "channel": "square", "field": "price"})
    assert "RG-0009" in price and "square" in price
    assert "rg-set-price" in price

    sold = heal_guidance({"sku": "RG-0003", "channel": "square", "field": "sold_state"})
    assert "RG-0003" in sold and "square" in sold
    assert "rg-item-mark-sold" in sold

    presence = heal_guidance({"sku": "RG-0007", "channel": "whatnot", "field": "presence"})
    assert "RG-0007" in presence and "whatnot" in presence
    assert "verify" in presence

    other = heal_guidance({"sku": "RG-0005", "channel": "ebay", "field": "title"})
    assert "RG-0005" in other and "ebay" in other and "title" in other
