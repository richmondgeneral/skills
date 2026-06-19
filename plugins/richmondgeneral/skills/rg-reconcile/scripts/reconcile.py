from __future__ import annotations
import argparse, json, os, sys
from pathlib import Path
from typing import Dict

# Make the item-model-core sibling skill's lib importable when run as a script.
# (Under pytest, conftest.py already injects this path; this makes the CLI work
# standalone too. insert is idempotent enough — duplicate paths are harmless.)
sys.path.insert(0, os.path.join(
    os.path.dirname(__file__), "..", "..", "item-model-core", "lib"))

from item_model.page_reader import read_page_record
from item_model.diff import diff_item
from item_model.catalog_state import build_catalog_state
from item_model.channels.square_reader import observe_square, build_square_index
from item_model.channels.whatnot_reader import observe_whatnot, build_whatnot_index
from item_model.instance import load_instance_config  # import-safe: no network


def gather_records_and_obs(items_dir, square_index, whatnot_index):
    """Walk items/RG-* pages -> [(PageRecord, [ChannelObservation])]. Skips dirs without label.json."""
    out = []
    for child in sorted(Path(items_dir).glob("RG-*")):
        if not (child / "label.json").exists():
            continue
        page = read_page_record(child)
        obs = [observe_square(page.sku, square_index), observe_whatnot(page.sku, whatnot_index)]
        out.append((page, obs))
    return out


def run_reconcile(items_dir: str, square_index: Dict, whatnot_index: Dict) -> dict:
    """Pure orchestration over injected indexes. Returns the report dict."""
    findings = []
    records = gather_records_and_obs(items_dir, square_index, whatnot_index)
    for page, observations in records:
        for f in diff_item(page, observations):
            findings.append(f.to_dict())

    summary = {"critical": 0, "warning": 0, "info": 0}
    for f in findings:
        summary[f["severity"]] = summary.get(f["severity"], 0) + 1
    return {"findings": findings, "summary": summary, "items_scanned": len(records)}


def heal_guidance(finding: dict) -> str:
    sku, ch = finding["sku"], finding["channel"]
    field = finding["field"]
    if field == "price":
        return f"{sku}: price drift on {ch} — run `rg-set-price {sku} <reference>` to push, or record the {ch} price as an intended override on the page."
    if field == "sold_state":
        return f"{sku}: sold-state conflict on {ch} — run `rg-item-mark-sold {sku}` (propagates sold across channels + deletes the payment link)."
    if field == "presence":
        return f"{sku}: page lists {ch} but it wasn't confirmed there — verify the {ch} listing."
    return f"{sku}: {field} drift on {ch} — review."


def main(argv=None):
    ap = argparse.ArgumentParser(description="Read-only drift reconcile (pages vs channels).")
    ap.add_argument("--items-dir", default=load_instance_config().items_dir)
    ap.add_argument("--whatnot-csv", default=None)
    ap.add_argument("--json-out", default=None)
    ap.add_argument("--heal", action="store_true",
                    help="Safe page-side heal: (re)write catalog_state.json and print "
                         "per-finding guidance. No production channel writes.")
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

    state = build_catalog_state(gather_records_and_obs(args.items_dir, square_index, whatnot_index))
    state_path = Path(args.items_dir).parent / "catalog_state.json"
    state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    print(f"Snapshot: {state_path} ({state['item_count']} items)")

    s = report["summary"]
    print(f"Scanned {report['items_scanned']} items")
    print(f"Reconcile: {s['critical']} critical, {s['warning']} warning, {s['info']} info")
    for f in report["findings"]:
        print(f"  [{f['severity'].upper():8}] {f['sku']} {f['field']} on {f['channel']}: {f['message']}")
    print(f"Report: {out}")

    if args.heal:
        # SAFE, page-side only: catalog_state.json was already (re)written above;
        # here we just announce it and route each finding to the right confirmed
        # tool. No production channel writes happen — guidance is print-only.
        print("HEAL (safe, page-side — no channel writes)")
        print(f"  Snapshot confirmed: {state_path}")
        if not report["findings"]:
            print("  No findings — channels match the pages. Nothing to heal.")
        for f in report["findings"]:
            print(f"  {heal_guidance(f)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
