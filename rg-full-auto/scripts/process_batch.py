#!/usr/bin/env python3
"""
rg-full-auto v6.0 batch orchestrator.

Processes multiple items through the 10-phase pipeline with:
  - Per-item isolation (one failure doesn't stop others)
  - Async question queue (parked items don't block batch)
  - Best-guess autonomous decisions (agent decides, user reviews)
  - State persistence (resume across sessions)

Usage:
  uv run python ~/.claude/skills/rg-full-auto/scripts/process_batch.py \
      --photos ~/Desktop/batch/*.jpeg
  uv run python ~/.claude/skills/rg-full-auto/scripts/process_batch.py --resume
  uv run python ~/.claude/skills/rg-full-auto/scripts/process_batch.py --status

This script provides STATE MANAGEMENT and ORCHESTRATION. The actual phase
execution is delegated to a `phase_runner(state, phase, item_dir)` callable.
The default runner subprocesses sibling skills (square-image-upload,
photos-library, etc.). Tests inject mocks via the `phase_runner` constructor arg.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from audit_log import AuditLog
from item_state import (
    PHASE_NAMES,
    ItemState,
    ItemStatus,
    PendingQuestion,
    PhaseStatus,
)
from onboarding_queue import DEFAULT_QUEUE_PATH, OnboardingQueue, QueueEntry


DEFAULT_ITEMS_DIR = "/Users/scottybe/workspace/square/items"

PhaseRunner = Callable[[ItemState, str, str], Dict[str, Any]]


def _default_next_sku(items_dir: str) -> str:
    """Allocate the next RG-XXXX SKU by scanning the items dir."""
    max_n = 0
    for child in Path(items_dir).glob("RG-*"):
        if child.is_dir():
            try:
                n = int(child.name.removeprefix("RG-"))
                max_n = max(max_n, n)
            except ValueError:
                continue
    return f"RG-{max_n + 1:04d}"


class BatchOrchestrator:
    """Runs the batch loop. Constructor accepts injection points for tests."""

    def __init__(
        self,
        items_dir: str = DEFAULT_ITEMS_DIR,
        queue_path: str = DEFAULT_QUEUE_PATH,
        phase_runner: Optional[PhaseRunner] = None,
        next_sku: Optional[Callable[[], str]] = None,
        audit_log: Optional[AuditLog] = None,
    ):
        self.items_dir = Path(items_dir)
        self.items_dir.mkdir(parents=True, exist_ok=True)
        self.queue_path = queue_path
        self.queue = OnboardingQueue(queue_path=queue_path)
        self.phase_runner: PhaseRunner = phase_runner or self._default_phase_runner
        self.next_sku = next_sku or (lambda: _default_next_sku(str(self.items_dir)))
        self.audit_log = audit_log or AuditLog()

    # -- Intake --

    def ingest_photos(self, photo_paths: List[str]) -> List[ItemState]:
        """Allocate one item per valid image, init state, register in queue."""
        states = []
        for raw in photo_paths:
            p = Path(raw)
            if not p.exists():
                print(f"  [SKIP] {raw}: file not found")
                continue
            if p.suffix.lower() not in (".jpg", ".jpeg", ".png", ".heic", ".webp"):
                print(f"  [SKIP] {raw}: not an image extension")
                continue
            sku = self.next_sku()
            item_dir = self.items_dir / sku
            item_dir.mkdir(parents=True, exist_ok=True)
            state = ItemState(
                sku=sku,
                items_dir=str(self.items_dir),
                source_image=str(p.resolve()),
            )
            state.save()
            self.queue.upsert(QueueEntry.from_item_state(state))
            states.append(state)
            print(f"  [QUEUED] {sku} <- {p.name}")
        self.queue.save()
        return states

    # -- Main loop --

    def process_all(self) -> Dict[str, Any]:
        """Iterate active items, advance each as far as possible. Returns a summary."""
        active = self.queue.get_active()
        if not active:
            return {"status": "idle", "processed": 0, "completed": 0,
                    "blocked": 0, "failed": 0, "items": {}}

        results: Dict[str, Any] = {
            "processed": 0, "completed": 0, "blocked": 0, "failed": 0, "items": {},
        }
        print(f"\n=== BATCH: {len(active)} active items ===")
        for entry in active:
            state = ItemState.load(entry.sku, items_dir=str(self.items_dir))
            if state is None:
                print(f"  [{entry.sku}] no state on disk - skipping")
                continue
            item_result = self._advance_item(state)
            results["items"][state.sku] = item_result
            results["processed"] += 1
            if state.status == ItemStatus.COMPLETED:
                results["completed"] += 1
            elif state.status == ItemStatus.BLOCKED:
                results["blocked"] += 1
            elif state.status == ItemStatus.FAILED:
                results["failed"] += 1
            self.queue.upsert(QueueEntry.from_item_state(state))
        self.queue.save()
        self._print_summary(results)
        return results

    def resume(self) -> Dict[str, Any]:
        """Unblock items whose questions have been answered, then process_all."""
        for entry in self.queue.get_blocked():
            state = ItemState.load(entry.sku, items_dir=str(self.items_dir))
            if state is None:
                continue
            unanswered = [q for q in state.questions if not q.get("answer")]
            if not unanswered:
                # Re-open the blocked phase so next_runnable_phase will pick it up.
                for phase_id, p in state.phases.items():
                    if p.status == PhaseStatus.BLOCKED:
                        p.status = PhaseStatus.PENDING
                state._recalculate_status()
                state.save()
                self.queue.upsert(QueueEntry.from_item_state(state))
        self.queue.save()
        return self.process_all()

    def status(self) -> Dict[str, Any]:
        return {
            "entries": [asdict(e) for e in self.queue.entries],
            "active": len(self.queue.get_active()),
            "blocked": len(self.queue.get_blocked()),
            "total": len(self.queue.entries),
        }

    # -- Per-item advancement --

    def _advance_item(self, state: ItemState) -> Dict[str, Any]:
        """Drive an item through its phases until blocked or done."""
        phases_run: List[Dict[str, Any]] = []
        item_dir = str(self.items_dir / state.sku)
        while True:
            phase = state.next_runnable_phase()
            if phase is None:
                break
            state.start_phase(phase)
            state.save()
            try:
                result = self.phase_runner(state, phase, item_dir)
            except Exception as exc:  # noqa: BLE001
                err = f"{type(exc).__name__}: {exc}"
                state.fail_phase(phase, error=err)
                state.save()
                phases_run.append({"phase": phase, "result": "failed", "error": err})
                continue
            if result.get("blocked"):
                question = result.get("question")
                if not isinstance(question, PendingQuestion):
                    question = PendingQuestion(
                        question_id=f"q-{phase}",
                        phase=phase,
                        question=result.get("question_text", "needs input"),
                    )
                state.block_phase(phase, question)
                state.save()
                phases_run.append({"phase": phase, "result": "blocked"})
            elif result.get("skipped"):
                state.skip_phase(phase, reason=result.get("reason", ""))
                state.save()
                phases_run.append({"phase": phase, "result": "skipped"})
            else:
                state.complete_phase(phase, outputs=result.get("outputs", {}))
                state.save()
                phases_run.append({"phase": phase, "result": "completed"})
        return {
            "final_status": state.status.value,
            "phases_run": phases_run,
            "progress": state.progress_summary(),
        }

    # -- Phase execution stub (replaced in PR #3) --

    def _default_phase_runner(
        self, state: ItemState, phase: str, item_dir: str
    ) -> Dict[str, Any]:
        """Stub default: blocks every phase, asking the user to wire the real runner.

        PR #3 replaces this with calls into the sibling skills:
        square-image-upload, photos-library, rg-lot-tracker, etc.
        """
        return {
            "blocked": True,
            "question": PendingQuestion(
                question_id=f"q-stub-{phase}",
                phase=phase,
                question=(
                    f"phase_runner is not wired yet for {PHASE_NAMES.get(phase, phase)}. "
                    "PR #3 of v6.0 will plug in the real handlers."
                ),
            ),
        }

    # -- Output --

    def _print_summary(self, results: Dict[str, Any]) -> None:
        print(f"\n=== Summary ===")
        for key in ("processed", "completed", "blocked", "failed"):
            print(f"  {key}: {results[key]}")
        if results["blocked"]:
            print("\nBlocked items have pending questions - run with --resume after answering.")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="rg-full-auto v6.0 batch orchestrator")
    p.add_argument("--items-dir", default=DEFAULT_ITEMS_DIR)
    p.add_argument("--queue-path", default=DEFAULT_QUEUE_PATH)
    sub = p.add_subparsers(dest="cmd")  # cmd is optional so --photos shorthand still works

    ing = sub.add_parser("ingest", help="Ingest photos and queue them")
    ing.add_argument("--photos", nargs="+", required=True)

    sub.add_parser("run", help="Process all active items in the queue")
    sub.add_parser("resume", help="Unblock answered items, then process")
    sub.add_parser("status", help="Show queue status")
    return p


def main() -> int:
    args = _build_parser().parse_args()
    orch = BatchOrchestrator(items_dir=args.items_dir, queue_path=args.queue_path)
    if args.cmd == "ingest":
        orch.ingest_photos(args.photos)
        return 0
    if args.cmd == "run":
        orch.process_all()
        return 0
    if args.cmd == "resume":
        orch.resume()
        return 0
    if args.cmd == "status":
        print(json.dumps(orch.status(), indent=2))
        return 0
    print("Use one of: ingest, run, resume, status (see --help).")
    return 2


if __name__ == "__main__":
    sys.exit(main())
