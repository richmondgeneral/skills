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


def test_whatnot_listed_but_absent_from_csv_is_not_flagged(tmp_path):
    # Regression: the Whatnot CSV is positive-only. An item the page lists on Whatnot but
    # that isn't in the import CSV (listed directly via the Whatnot UI — e.g. RG-0022/RG-0027)
    # must NOT produce a presence finding: "not in the CSV" != "absent from Whatnot".
    items_dir = tmp_path / "items"; items_dir.mkdir()
    _item(items_dir, "RG-0022", "32.00",
          label_extra={"channels": {"whatnot": {"status": "listed"}}})
    report = run_reconcile(items_dir=str(items_dir), square_index={}, whatnot_index={})
    assert all(f["field"] != "presence" for f in report["findings"])
    assert report["summary"] == {"critical": 0, "warning": 0, "info": 0}


def test_whatnot_affirmed_observation_is_diffed_not_dropped(tmp_path):
    # Counterpart to the positive-only filter: it must drop ONLY absent (None) observations.
    # When the import CSV AFFIRMS a SKU, its price/sold must still be diffed — a conflict has
    # to surface, not get swallowed alongside the genuine absences.
    items_dir = tmp_path / "items"; items_dir.mkdir()
    _item(items_dir, "RG-0040", "60.00",
          label_extra={"channels": {"whatnot": {"status": "listed"}}})
    # CSV affirms RG-0040 at $48 (price drift) and Status=sold (sold-state conflict).
    whatnot_index = {"RG-0040": (48.0, True)}
    report = run_reconcile(items_dir=str(items_dir), square_index={}, whatnot_index=whatnot_index)
    flagged = {(f["sku"], f["field"]): (f["channel"], f["severity"]) for f in report["findings"]}
    assert flagged[("RG-0040", "sold_state")] == ("whatnot", "critical")
    assert flagged[("RG-0040", "price")] == ("whatnot", "warning")
    assert report["summary"] == {"critical": 1, "warning": 1, "info": 0}
