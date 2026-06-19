#!/usr/bin/env python3
"""CSV-first Whatnot sync scaffold for Richmond General items.

Reads item-level label metadata exported as CSV (from items repo), maps it into a
Whatnot-friendly listing CSV, and optionally runs through a future API adapter.

This implementation is intentionally CSV-first while keeping an API-ready contract.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional


WHATNOT_HEADERS = [
    "Title",
    "Description",
    "StartingPrice",
    "BuyItNowPrice",
    "Quantity",
    "Condition",
    "Category",
    "SKU",
    "Tags",
    "ImageURLs",
    "ExternalURL",
    "Status",
]


@dataclass
class LabelRecord:
    product_name: str
    attributes: str
    price: float
    condition: str
    condition_notes: str
    sku: str
    qr_code_url: str


def _clean(value: Optional[str]) -> str:
    return (value or "").strip()


def _parse_price(raw_value: str) -> float:
    cleaned = _clean(raw_value).replace("$", "")
    if not cleaned:
        return 0.0
    return round(float(cleaned), 2)


def _normalize_condition(condition: str) -> str:
    value = _clean(condition).lower()
    mapping = {
        "mint": "Mint",
        "excellent": "Excellent",
        "very good": "Very Good",
        "vg": "Very Good",
        "good": "Good",
        "g": "Good",
        "like new": "Like New",
        "ln": "Like New",
        "fair": "Fair",
        "as-is": "As-Is",
        "as is": "As-Is",
    }
    return mapping.get(value, _clean(condition) or "Good")


def _extract_tags(attributes: str, sku: str) -> List[str]:
    raw_tokens = (
        _clean(attributes)
        .replace("•", "|")
        .replace(",", "|")
        .split("|")
    )

    tags: List[str] = []
    for token in raw_tokens:
        cleaned = token.strip().lower()
        if cleaned and cleaned not in tags:
            tags.append(cleaned)

    if sku and sku.lower() not in tags:
        tags.append(sku.lower())

    return tags[:10]


def _build_description(record: LabelRecord) -> str:
    lines = [record.product_name]

    if record.attributes:
        lines.append(f"Attributes: {record.attributes}")

    lines.append(f"Condition: {_normalize_condition(record.condition)}")

    if record.condition_notes:
        lines.append(f"Condition Notes: {record.condition_notes}")

    if record.qr_code_url:
        lines.append(f"More details: {record.qr_code_url}")

    return "\n".join(lines)


def load_label_records(input_csv: str) -> List[LabelRecord]:
    path = Path(input_csv)
    if not path.exists():
        raise FileNotFoundError(f"Input CSV not found: {path}")

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows: List[LabelRecord] = []
        for row in reader:
            sku = _clean(row.get("SKU"))
            if not sku:
                continue
            rows.append(
                LabelRecord(
                    product_name=_clean(row.get("Product Name")),
                    attributes=_clean(row.get("Attributes")),
                    price=_parse_price(_clean(row.get("Price"))),
                    condition=_clean(row.get("Condition")),
                    condition_notes=_clean(row.get("Condition Notes")),
                    sku=sku,
                    qr_code_url=_clean(row.get("QR Code URL")),
                )
            )

    return rows


def map_record_to_whatnot_row(
    record: LabelRecord,
    *,
    category: str,
    quantity: int,
    status: str,
) -> Dict[str, str]:
    tags = _extract_tags(record.attributes, record.sku)
    description = _build_description(record)
    price = f"{record.price:.2f}"

    return {
        "Title": record.product_name[:120],
        "Description": description,
        "StartingPrice": price,
        "BuyItNowPrice": price,
        "Quantity": str(max(1, quantity)),
        "Condition": _normalize_condition(record.condition),
        "Category": category,
        "SKU": record.sku,
        "Tags": ",".join(tags),
        "ImageURLs": "",
        "ExternalURL": record.qr_code_url,
        "Status": status,
    }


def build_whatnot_rows(
    records: Iterable[LabelRecord],
    *,
    category: str,
    quantity: int,
    status: str,
) -> List[Dict[str, str]]:
    return [
        map_record_to_whatnot_row(
            record,
            category=category,
            quantity=quantity,
            status=status,
        )
        for record in records
    ]


def write_whatnot_csv(output_csv: str, rows: List[Dict[str, str]]) -> None:
    output_path = Path(output_csv)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=WHATNOT_HEADERS)
        writer.writeheader()
        writer.writerows(rows)


class WhatnotApiAdapter:
    """API adapter scaffold for future Seller API integration."""

    def __init__(self, api_key: Optional[str] = None, base_url: str = "https://api.whatnot.com/v1"):
        self.api_key = api_key or os.environ.get("WHATNOT_API_KEY") or os.environ.get("WHATNOT_SELLER_API_KEY")
        self.base_url = base_url

    def sync(self, rows: List[Dict[str, str]], *, live: bool = False) -> Dict[str, object]:
        if not self.api_key:
            return {
                "success": False,
                "mode": "api",
                "live": live,
                "error": "Missing WHATNOT_API_KEY/WHATNOT_SELLER_API_KEY",
                "uploaded": 0,
            }

        if not live:
            return {
                "success": True,
                "mode": "api-dry-run",
                "live": False,
                "uploaded": len(rows),
                "note": "API adapter scaffold only. No live requests were sent.",
            }

        raise NotImplementedError(
            "Whatnot Seller API live sync is not implemented yet. "
            "Keep using CSV export until API access and endpoint contracts are finalized."
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync Richmond General items to Whatnot (CSV-first scaffold)")
    parser.add_argument(
        "--input",
        required=True,
        help="Input label CSV (typically items/rg-inventory/rg-labels-batch.csv)",
    )
    parser.add_argument(
        "--output",
        # Default matches SKILL.md Phase 8.1 (append target). Previously
        # hardcoded to /Users/scottybe/... which won't exist on another
        # machine and pointed at a stale qa-artifacts path.
        default=str(Path.home() / "workspace" / "square" / "items"
                    / "rg-inventory" / "whatnot-import.csv"),
        help="Output Whatnot CSV path (default: ~/workspace/richmondgeneral/items/rg-inventory/whatnot-import.csv)",
    )
    parser.add_argument(
        "--category",
        default="Collectibles",
        help="Default category value in output CSV",
    )
    parser.add_argument(
        "--quantity",
        type=int,
        default=1,
        help="Default quantity per listing row",
    )
    parser.add_argument(
        "--status",
        default="draft",
        choices=["draft", "active"],
        help="Listing status in output CSV",
    )
    parser.add_argument(
        "--api-mode",
        default="off",
        choices=["off", "dry-run", "live"],
        help="Optional API adapter mode (scaffold). CSV is always generated.",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON summary")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    records = load_label_records(args.input)
    rows = build_whatnot_rows(
        records,
        category=args.category,
        quantity=args.quantity,
        status=args.status,
    )
    write_whatnot_csv(args.output, rows)

    summary: Dict[str, object] = {
        "success": True,
        "input": str(Path(args.input)),
        "output": str(Path(args.output)),
        "records_read": len(records),
        "rows_written": len(rows),
        "api_mode": args.api_mode,
    }

    if args.api_mode != "off":
        adapter = WhatnotApiAdapter()
        adapter_summary = adapter.sync(rows, live=(args.api_mode == "live"))
        summary["api"] = adapter_summary

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(f"Whatnot CSV export complete: {summary['rows_written']} row(s)")
        print(f"Output: {summary['output']}")
        if summary.get("api"):
            print(f"API mode: {args.api_mode}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
