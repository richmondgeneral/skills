#!/usr/bin/env python3
"""
Audit-log writer for rg-full-auto v6.0.

Three append-only JSONL streams under <log_dir>:
  decisions.jsonl    — every autonomous decision the agent made
  corrections.jsonl  — human corrections to those decisions, plus
                       auto-detected drift between agent's choice
                       and current Square/state-on-disk
  review_log.jsonl   — review-timing events (started, completed)
                       + outcomes, for L2 time tracking

Default log_dir: /Users/scottybe/workspace/square/ops/inventory/

JSONL = one JSON object per line, append-only. Lets us grep/jq with
zero parse overhead and never rewrite the whole file.

CLI subcommands (planned but not all built in PR #1):
  audit_log.py report --sku <SKU>
  audit_log.py report --since <DATE>
  audit_log.py review-stats
  audit_log.py drift
  audit_log.py correct --sku ... --decision ... --new ... --reason ...
"""
from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_LOG_DIR = "/Users/scottybe/workspace/square/ops/inventory"


class AuditLog:
    """Append-only JSONL writer for the three audit streams."""

    def __init__(self, log_dir: str = DEFAULT_LOG_DIR):
        self.log_dir = Path(log_dir)
        self.decisions_path = self.log_dir / "decisions.jsonl"
        self.corrections_path = self.log_dir / "corrections.jsonl"
        self.review_log_path = self.log_dir / "review_log.jsonl"

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _append(self, path: Path, record: Dict[str, Any]) -> None:
        """Append one JSON object as a single line. Atomic at the OS
        level for line-sized writes on a single host (POSIX append)."""
        self.log_dir.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, ensure_ascii=False) + "\n"
        with path.open("a", encoding="utf-8") as f:
            f.write(line)

    def log_decision(
        self,
        sku: str,
        phase: str,
        decision_type: str,
        choice: Any,
        confidence: float,
        inputs_considered: Dict[str, Any],
        alternatives_seen: List[Dict[str, Any]],
        rationale: str,
        decision_id: Optional[str] = None,
    ) -> str:
        """Append one decision; returns the decision_id."""
        decision_id = decision_id or f"dec-{uuid.uuid4().hex[:8]}"
        record = {
            "ts": self._now(),
            "decision_id": decision_id,
            "sku": sku,
            "phase": phase,
            "type": decision_type,
            "choice": choice,
            "confidence": confidence,
            "inputs_considered": inputs_considered,
            "alternatives_seen": alternatives_seen,
            "rationale": rationale,
        }
        self._append(self.decisions_path, record)
        return decision_id

    def log_correction(
        self,
        sku: str,
        decision_id: str,
        decision_type: str,
        agent_choice: Any,
        corrected_to: Any,
        correction_source: str,
        reason: str,
        reviewer: str,
        correction_id: Optional[str] = None,
    ) -> str:
        """Append one correction; returns the correction_id."""
        correction_id = correction_id or f"cor-{uuid.uuid4().hex[:8]}"
        record = {
            "ts": self._now(),
            "correction_id": correction_id,
            "sku": sku,
            "decision_id": decision_id,
            "decision_type": decision_type,
            "agent_choice": agent_choice,
            "corrected_to": corrected_to,
            "correction_source": correction_source,
            "reason": reason,
            "reviewer": reviewer,
        }
        self._append(self.corrections_path, record)
        return correction_id

    def log_review_event(
        self,
        sku: str,
        event: str,                    # "review_started" | "review_completed"
        duration_s: Optional[int] = None,
        corrections_applied: Optional[int] = None,
        outcome: Optional[str] = None, # accepted_as_is | accepted_with_corrections | rejected_redo
    ) -> None:
        record: Dict[str, Any] = {
            "ts": self._now(),
            "sku": sku,
            "event": event,
        }
        if duration_s is not None:
            record["duration_s"] = duration_s
        if corrections_applied is not None:
            record["corrections_applied"] = corrections_applied
        if outcome is not None:
            record["outcome"] = outcome
        self._append(self.review_log_path, record)

    def iter_records(self, stream: str):
        """Iterate records from one of the three streams, lazily.

        stream ∈ {"decisions", "corrections", "review_log"}.
        Returns an empty iterator if the stream file doesn't exist yet."""
        paths = {
            "decisions": self.decisions_path,
            "corrections": self.corrections_path,
            "review_log": self.review_log_path,
        }
        if stream not in paths:
            raise ValueError(f"Unknown stream: {stream}. Use one of {list(paths)}")
        path = paths[stream]
        if not path.exists():
            return
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                yield json.loads(line)


def _cli_report(args, al: AuditLog) -> int:
    """Print decisions filtered by --sku and/or --since."""
    decisions = list(al.iter_records("decisions"))
    if args.sku:
        decisions = [d for d in decisions if d.get("sku") == args.sku]
    if args.since:
        decisions = [d for d in decisions if d.get("ts", "") >= args.since]
    if not decisions:
        print("(no decisions match)")
        return 0
    for d in decisions:
        print(
            f"[{d['ts']}] {d['sku']} {d['phase']} {d['type']}={d.get('choice')} "
            f"(conf={d.get('confidence', '?')}, rationale={d.get('rationale', '')[:60]})"
        )
    return 0


def _cli_review_stats(args, al: AuditLog) -> int:
    """Aggregate review_log per SKU and print a table."""
    by_sku: Dict[str, Dict[str, Any]] = {}
    for record in al.iter_records("review_log"):
        sku = record["sku"]
        by_sku.setdefault(sku, {})
        if record["event"] == "review_started":
            by_sku[sku]["started_at"] = record["ts"]
        elif record["event"] == "review_completed":
            by_sku[sku]["duration_s"] = record.get("duration_s")
            by_sku[sku]["corrections_applied"] = record.get("corrections_applied", 0)
            by_sku[sku]["outcome"] = record.get("outcome")
    if not by_sku:
        print("(no review events yet)")
        return 0
    print(f"{'SKU':<10} {'Duration (s)':<14} {'Corrections':<13} {'Outcome'}")
    for sku, stats in sorted(by_sku.items()):
        print(
            f"{sku:<10} {str(stats.get('duration_s', '-')):<14} "
            f"{str(stats.get('corrections_applied', '-')):<13} {stats.get('outcome', '-')}"
        )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="rg-full-auto v6.0 audit log reader/writer CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--log-dir",
        default=DEFAULT_LOG_DIR,
        help=f"Audit log directory (default: {DEFAULT_LOG_DIR})",
    )

    # Shared parent so --log-dir works either before or after the subcommand.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--log-dir",
        default=DEFAULT_LOG_DIR,
        help=f"Audit log directory (default: {DEFAULT_LOG_DIR})",
    )

    sub = parser.add_subparsers(dest="cmd", required=True)

    rp = sub.add_parser("report", help="Print decisions filtered by SKU or date", parents=[common])
    rp.add_argument("--sku", help="Filter to one SKU")
    rp.add_argument("--since", help="ISO timestamp; show decisions on/after this")

    sub.add_parser("review-stats", help="Aggregate review timings + outcomes per SKU", parents=[common])

    # Placeholders for PR #3 (need live state diff):
    sub.add_parser("drift", help="(TODO v6.1) Detect decisions that drifted from current state", parents=[common])
    sub.add_parser("correct", help="(TODO PR #3) Apply a manual correction interactively", parents=[common])

    args = parser.parse_args()
    al = AuditLog(log_dir=args.log_dir)
    if args.cmd == "report":
        return _cli_report(args, al)
    if args.cmd == "review-stats":
        return _cli_review_stats(args, al)
    if args.cmd in ("drift", "correct"):
        print(f"(not implemented yet — see v6.0 plan PR #3 / v6.1)")
        return 2
    return 1


if __name__ == "__main__":
    sys.exit(main())
