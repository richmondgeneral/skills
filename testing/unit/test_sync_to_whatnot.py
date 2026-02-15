import csv
from pathlib import Path

from sync_to_whatnot import (
    LabelRecord,
    WhatnotApiAdapter,
    build_whatnot_rows,
    load_label_records,
    map_record_to_whatnot_row,
    write_whatnot_csv,
)


def test_map_record_to_whatnot_row_contains_expected_fields():
    record = LabelRecord(
        product_name="Dick Tracy Exhibition Catalogue",
        attributes="1978 • Book • Museum",
        price=40.0,
        condition="Very Good",
        condition_notes="Minor edge wear",
        sku="RG-0015",
        qr_code_url="https://richmondgeneral.github.io/items/RG-0015/",
    )

    row = map_record_to_whatnot_row(
        record,
        category="Books",
        quantity=1,
        status="draft",
    )

    assert row["Title"] == "Dick Tracy Exhibition Catalogue"
    assert row["StartingPrice"] == "40.00"
    assert row["BuyItNowPrice"] == "40.00"
    assert row["Condition"] == "Very Good"
    assert row["Category"] == "Books"
    assert row["SKU"] == "RG-0015"
    assert "Condition Notes: Minor edge wear" in row["Description"]
    assert "rg-0015" in row["Tags"]


def test_load_and_write_whatnot_csv_round_trip(tmp_path):
    input_csv = tmp_path / "labels.csv"
    output_csv = tmp_path / "whatnot.csv"

    input_csv.write_text(
        "Product Name,Attributes,Price,Condition,Condition Notes,SKU,QR Code URL\n"
        "Little Orphan Annie Book,1979 • Book • Comic,19.99,Good,Light shelf wear,RG-0001,https://richmondgeneral.github.io/items/RG-0001/\n",
        encoding="utf-8",
    )

    records = load_label_records(str(input_csv))
    rows = build_whatnot_rows(
        records,
        category="Collectibles",
        quantity=1,
        status="draft",
    )
    write_whatnot_csv(str(output_csv), rows)

    with output_csv.open("r", encoding="utf-8") as handle:
        parsed = list(csv.DictReader(handle))

    assert len(records) == 1
    assert len(parsed) == 1
    assert parsed[0]["SKU"] == "RG-0001"
    assert parsed[0]["Status"] == "draft"


def test_api_adapter_dry_run_requires_key(monkeypatch):
    monkeypatch.delenv("WHATNOT_API_KEY", raising=False)
    monkeypatch.delenv("WHATNOT_SELLER_API_KEY", raising=False)

    adapter = WhatnotApiAdapter()
    result = adapter.sync([], live=False)

    assert result["success"] is False
    assert "Missing WHATNOT_API_KEY" in result["error"]


def test_api_adapter_dry_run_with_key(monkeypatch):
    monkeypatch.setenv("WHATNOT_API_KEY", "test-key")

    adapter = WhatnotApiAdapter()
    result = adapter.sync([{"SKU": "RG-0001"}], live=False)

    assert result["success"] is True
    assert result["mode"] == "api-dry-run"
    assert result["uploaded"] == 1
