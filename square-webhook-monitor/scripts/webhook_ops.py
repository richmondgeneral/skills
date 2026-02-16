#!/usr/bin/env python3
"""Square webhook monitor and subscription operations wrapper."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys


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


def run_script(script: Path, script_args: list[str], extra_env: dict[str, str] | None = None) -> int:
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    command = [sys.executable, str(script), *script_args]
    result = subprocess.run(command, capture_output=True, text=True, env=env, timeout=300)
    if result.stdout:
        print(result.stdout.strip())
    if result.stderr:
        print(result.stderr.strip(), file=sys.stderr)
    return result.returncode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Square webhook operations wrapper.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="List webhook event types + current subscriptions.")

    create = sub.add_parser("create", help="Create webhook subscription.")
    create.add_argument("--name", required=True, help="Subscription display name.")
    create.add_argument("--notification-url", required=True, help="Public webhook callback URL.")
    create.add_argument(
        "--event-type",
        action="append",
        required=True,
        help="Event type (repeat for multiple).",
    )

    test = sub.add_parser("test", help="Send test webhook event.")
    test.add_argument("--subscription-id", required=True, help="Webhook subscription ID.")
    test.add_argument(
        "--event-type",
        default="catalog.version.updated",
        help="Event type for the test event.",
    )

    rotate = sub.add_parser("rotate-signature-key", help="Rotate webhook signature key.")
    rotate.add_argument("--subscription-id", required=True, help="Webhook subscription ID.")

    run = sub.add_parser("run-monitor", help="Run local FastAPI webhook monitor.")
    run.add_argument("--host", default="0.0.0.0", help="Monitor host.")
    run.add_argument("--port", type=int, default=8087, help="Monitor port.")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    toolkit_root = resolve_toolkit_root()
    scripts_dir = toolkit_root / "scripts"

    if args.command == "list":
        return run_script(scripts_dir / "webhook_bootstrap.py", ["list"])

    if args.command == "create":
        command = [
            "create",
            "--name",
            args.name,
            "--notification-url",
            args.notification_url,
        ]
        for event_type in args.event_type:
            command.extend(["--event-type", event_type])
        return run_script(scripts_dir / "webhook_bootstrap.py", command)

    if args.command == "test":
        command = [
            "test",
            "--subscription-id",
            args.subscription_id,
            "--event-type",
            args.event_type,
        ]
        return run_script(scripts_dir / "webhook_bootstrap.py", command)

    if args.command == "rotate-signature-key":
        command = [
            "rotate-signature-key",
            "--subscription-id",
            args.subscription_id,
        ]
        return run_script(scripts_dir / "webhook_bootstrap.py", command)

    if args.command == "run-monitor":
        env = {
            "SQUARE_WEBHOOK_MONITOR_HOST": str(args.host),
            "SQUARE_WEBHOOK_MONITOR_PORT": str(args.port),
        }
        return run_script(scripts_dir / "run_webhook_monitor.py", [], extra_env=env)

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
