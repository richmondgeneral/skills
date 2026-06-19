#!/usr/bin/env python3
"""Square catalog operations wrapper for reusable cleanup/compliance workflows."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


TOOLKIT_CANDIDATES = (
    os.environ.get("SQUARE_CATALOG_TOOLKIT_ROOT"),
    "/Users/scottybe/workspace/square/square-tools/catalog-toolkit",
    os.path.expanduser("~/workspace/square/square-tools/catalog-toolkit"),
    os.path.expanduser("~/Workspace/square/square-tools/catalog-toolkit"),
)


def resolve_toolkit_root() -> Path:
    for value in TOOLKIT_CANDIDATES:
        if not value:
            continue
        path = Path(value).expanduser()
        if path.exists():
            return path
    raise FileNotFoundError(
        "Square catalog toolkit not found. Set SQUARE_CATALOG_TOOLKIT_ROOT "
        "or install at /Users/scottybe/workspace/square/square-tools/catalog-toolkit"
    )


def _run_script(script: Path, args: list[str]) -> int:
    command = [sys.executable, str(script), *args]
    result = subprocess.run(command, capture_output=True, text=True, timeout=300)
    if result.stdout:
        print(result.stdout.strip())
    if result.stderr:
        print(result.stderr.strip(), file=sys.stderr)
    return result.returncode


def _load_square_modules(toolkit_root: Path) -> tuple[Any, Any]:
    if str(toolkit_root) not in sys.path:
        sys.path.insert(0, str(toolkit_root))

    from square_catalog_toolkit.constants import DOC_LINKS  # noqa: WPS433
    from square_catalog_toolkit.rest_client import SquareRestClient  # noqa: WPS433

    return SquareRestClient, DOC_LINKS


def command_compliance(toolkit_root: Path) -> int:
    try:
        if str(toolkit_root) not in sys.path:
            sys.path.insert(0, str(toolkit_root))
        from square_catalog_toolkit.compliance import (  # noqa: WPS433
            docs_trace_for_core_calls,
            run_rest_version_check,
            run_sdk_version_check,
        )
        from square_catalog_toolkit.constants import API_VERSION, DOC_LINKS  # noqa: WPS433

        payload = {
            "api_version": API_VERSION,
            "release_docs": DOC_LINKS["release_2026_01_22"],
            "rest_check": run_rest_version_check(),
            "sdk_check": run_sdk_version_check(),
            "docs_traceability": docs_trace_for_core_calls(),
        }
        payload["ok"] = bool(payload["rest_check"]["ok"]) and bool(
            payload["sdk_check"]["invalid_version_rejected"]
        )
        print(json.dumps(payload, indent=2))
        return 0 if payload["ok"] else 1
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 1


def command_list_sites(toolkit_root: Path) -> int:
    SquareRestClient, DOC_LINKS = _load_square_modules(toolkit_root)
    client = SquareRestClient()
    channels = client.list_channels().get("channels", [])
    sites = client.list_sites().get("sites", [])

    site_by_id = {}
    for site in sites:
        site_id = site.get("id", "")
        if isinstance(site_id, str) and site_id.startswith("site_"):
            site_by_id[site_id.replace("site_", "")] = site

    active_sites: list[dict[str, Any]] = []
    for channel in channels:
        if channel.get("status") != "ACTIVE":
            continue
        reference = channel.get("reference") or {}
        if reference.get("type") != "ONLINE_SITE":
            continue
        ref_id = reference.get("id", "")
        site = site_by_id.get(ref_id, {})
        active_sites.append(
            {
                "channel_id": channel.get("id"),
                "channel_name": channel.get("name"),
                "site_id": site.get("id"),
                "site_title": site.get("site_title"),
                "domain": site.get("domain"),
                "is_published": site.get("is_published"),
            }
        )

    payload = {
        "docs": {
            "list_channels": DOC_LINKS["list_channels"],
            "list_sites": DOC_LINKS["list_sites"],
        },
        "active_online_sites": active_sites,
    }
    print(json.dumps(payload, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Square catalog operations workflow wrapper.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("compliance", help="Run API version compliance checks.")
    sub.add_parser("list-sites", help="List active online-site channels + domains.")

    merge = sub.add_parser("merge-food", help="Merge legacy food categories into one category.")
    merge.add_argument("--apply", action="store_true", help="Apply changes (default is dry-run).")
    merge.add_argument("--target-name", default="Food & Pantry", help="Target category name.")

    audit = sub.add_parser(
        "audit-cleanup",
        help="Run cleanup integrity audit (legacy food hidden/empty, channel coverage).",
    )
    audit.add_argument("--fail-on-issues", action="store_true", help="Exit non-zero if issues exist.")
    audit.add_argument(
        "--expect-new-arrivals-count",
        default=10,
        type=int,
        help="Expected item count in New Arrivals (the intake default tier).",
    )
    audit.add_argument("--json-out", default="", help="Optional path to save audit JSON.")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    toolkit_root = resolve_toolkit_root()
    scripts_dir = toolkit_root / "scripts"

    if args.command == "compliance":
        return command_compliance(toolkit_root)
    if args.command == "list-sites":
        return command_list_sites(toolkit_root)

    if args.command == "merge-food":
        script = scripts_dir / "merge_food_categories.py"
        script_args = ["--apply"] if args.apply else ["--dry-run"]
        script_args.extend(["--target-name", args.target_name])
        return _run_script(script, script_args)

    if args.command == "audit-cleanup":
        script = scripts_dir / "catalog_cleanup_audit.py"
        script_args = ["--expect-new-arrivals-count", str(args.expect_new_arrivals_count)]
        if args.fail_on_issues:
            script_args.append("--fail-on-issues")
        if args.json_out:
            script_args.extend(["--json-out", args.json_out])
        return _run_script(script, script_args)

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
