from __future__ import annotations
import argparse, json, os, sys
from pathlib import Path
from typing import Dict, Optional

# Make the item-model-core sibling skill's lib importable when run as a script.
# (Under pytest, conftest.py already injects this path; this makes the CLI work
# standalone too. insert is idempotent enough — duplicate paths are harmless.)
sys.path.insert(0, os.path.join(
    os.path.dirname(__file__), "..", "..", "item-model-core", "lib"))

from item_model.page_reader import read_page_record
from item_model.diff import diff_item
from item_model.models import Channel
from item_model.channels.square_reader import observe_square, build_square_index
from item_model.channels.whatnot_reader import observe_whatnot, build_whatnot_index


def run_reconcile(items_dir: str, square_index: Dict, whatnot_index: Dict) -> dict:
    """Pure orchestration over injected indexes. Returns the report dict."""
    findings = []
    for child in sorted(Path(items_dir).glob("RG-*")):
        if not (child / "label.json").exists():
            continue
        page = read_page_record(child)
        observations = [
            observe_square(page.sku, square_index),
            observe_whatnot(page.sku, whatnot_index),
        ]
        for f in diff_item(page, observations):
            findings.append(f.to_dict())

    summary = {"critical": 0, "warning": 0, "info": 0}
    for f in findings:
        summary[f["severity"]] = summary.get(f["severity"], 0) + 1
    return {"findings": findings, "summary": summary}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Read-only drift reconcile (pages vs channels).")
    ap.add_argument("--items-dir", default=os.environ.get(
        "RG_ITEMS_DIR", str(Path.home() / "workspace" / "richmondgeneral" / "items")))
    ap.add_argument("--whatnot-csv", default=None)
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args(argv)

    square_index = build_square_index()
    whatnot_csv = args.whatnot_csv or str(
        Path(args.items_dir) / "rg-inventory" / "whatnot-import.csv")
    whatnot_index = build_whatnot_index(whatnot_csv)

    report = run_reconcile(args.items_dir, square_index, whatnot_index)

    out = args.json_out
    if out is None:
        ops_reports = Path(args.items_dir).parent / "ops" / "reports"
        ops_reports.mkdir(parents=True, exist_ok=True)
        out = str(ops_reports / "reconcile-latest.json")
    Path(out).write_text(json.dumps(report, indent=2), encoding="utf-8")

    s = report["summary"]
    print(f"Reconcile: {s['critical']} critical, {s['warning']} warning, {s['info']} info")
    for f in report["findings"]:
        print(f"  [{f['severity'].upper():8}] {f['sku']} {f['field']} on {f['channel']}: {f['message']}")
    print(f"Report: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
