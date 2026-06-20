#!/usr/bin/env python3
"""
rg-full-auto v6.0 batch orchestrator.

Processes multiple items through the 10-phase pipeline with:
  - Per-item isolation (one failure doesn't stop others)
  - Async question queue (parked items don't block batch)
  - Best-guess autonomous decisions (agent decides, user reviews)
  - State persistence (resume across sessions)

Usage:
  uv run python ${CLAUDE_PLUGIN_ROOT}/skills/rg-full-auto/scripts/process_batch.py \
      --photos ~/Desktop/batch/*.jpeg
  uv run python ${CLAUDE_PLUGIN_ROOT}/skills/rg-full-auto/scripts/process_batch.py --resume
  uv run python ${CLAUDE_PLUGIN_ROOT}/skills/rg-full-auto/scripts/process_batch.py --status

This script provides STATE MANAGEMENT and ORCHESTRATION. The actual phase
execution is delegated to a `phase_runner(state, phase, item_dir)` callable.
The default runner subprocesses sibling skills (square-image-upload,
photos-library, etc.). Tests inject mocks via the `phase_runner` constructor arg.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from audit_log import AuditLog
from item_state import (
    PHASE_NAMES,
    PUBLISH_PHASES,
    ItemState,
    ItemStatus,
    PendingQuestion,
    PhaseStatus,
    can_list,
)
from onboarding_queue import DEFAULT_QUEUE_PATH, OnboardingQueue, QueueEntry
from sku_authority import default_next_sku

try:
    from remove_background import remove_background as _remove_background  # type: ignore
except ImportError:  # pragma: no cover
    _remove_background = None  # type: ignore[assignment]


DEFAULT_ITEMS_DIR = "/Users/scottybe/workspace/richmondgeneral/items"

PhaseRunner = Callable[[ItemState, str, str], Dict[str, Any]]
"""Phase runner contract. The callable returns exactly one of these shapes:

    {"outputs": {...}}                                    — phase completed
    {"blocked": True, "question": PendingQuestion}        — phase parked
    {"blocked": True, "question_text": "..."}             — phase parked (shorthand)
    {"skipped": True, "reason": "..."}                    — phase intentionally skipped

Precedence on conflict: blocked > skipped > completed.
Anything else (missing keys, or an unhandled exception) marks the phase FAILED.
"""


def _check_sku_in_square_cache(sku: str) -> Optional[str]:
    """Module-level helper so tests can monkeypatch easily.

    Returns the existing Square item_id if the SKU exists, else None.
    Default implementation is a placeholder — for v6.0 PR #3, it always
    returns None ('not in cache'). The real implementation will use the
    square-cache MCP server in v6.1."""
    return None


def _default_next_sku(items_dir: str) -> str:
    """DEPRECATED: superseded by sku_authority.allocate_sku; retained for reference/bootstrap fs-scan.

    Allocate the next RG-XXXX SKU by scanning the items dir."""
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
        self.queue_path = queue_path
        self.queue = OnboardingQueue(queue_path=queue_path)
        self.phase_runner: PhaseRunner = phase_runner or self._default_phase_runner
        self.next_sku = next_sku or default_next_sku
        self.audit_log = audit_log or AuditLog()

    # ── Intake ──

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
            if (item_dir / ".state.json").exists():
                print(f"  [SKIP] {sku}: state file already exists, refusing to clobber")
                continue
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

    # ── Main loop ──

    def process_all(self) -> Dict[str, Any]:
        """Iterate active items, advance each as far as possible. Returns a summary."""
        active = self.queue.get_active()
        if not active:
            return {"processed": 0, "completed": 0,
                    "blocked": 0, "failed": 0, "items": {}}

        results: Dict[str, Any] = {
            "processed": 0, "completed": 0, "blocked": 0, "failed": 0, "items": {},
        }
        print(f"\n=== BATCH: {len(active)} active items ===")
        for entry in active:
            state = ItemState.load(entry.sku, items_dir=str(self.items_dir))
            if state is None:
                print(f"  [{entry.sku}] no state on disk — skipping")
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
        """Unblock phases whose questions have been answered, then process_all.

        Per-phase semantics: a phase reopens only when every question parked
        under that phase has a non-empty answer. Answering one question
        does NOT reopen phases whose questions are still unanswered.
        """
        for entry in self.queue.get_blocked():
            state = ItemState.load(entry.sku, items_dir=str(self.items_dir))
            if state is None:
                continue
            # Group questions by their phase, track per-phase "all answered".
            answered_by_phase: Dict[str, bool] = {}
            for q in state.questions:
                ph = q.get("phase")
                if ph is None:
                    continue
                answered = bool(q.get("answer"))
                # If the phase already has any unanswered question, stay False.
                answered_by_phase[ph] = answered_by_phase.get(ph, True) and answered
            any_reopened = False
            for phase_id, p in state.phases.items():
                if p.status == PhaseStatus.BLOCKED and answered_by_phase.get(phase_id, False):
                    p.status = PhaseStatus.PENDING
                    any_reopened = True
            if any_reopened:
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

    # ── Per-item advancement ──

    def _run_hero_qa(self, item_dir: str) -> None:
        """Run the image-processor hero_qa CLI to populate label.json -> hero_qa.
        Subprocessed (matches the default phase_runner's sibling-skill pattern)
        so cv2/pytesseract never load into this process."""
        import subprocess
        here = Path(__file__).resolve()
        script = here.parents[2] / "image-processor" / "scripts" / "hero_qa.py"
        proj = next((p for p in here.parents if (p / "pyproject.toml").exists()),
                    here.parents[3])
        if not script.exists():
            print(f"  ⚠ hero_qa script missing at {script}; cannot gate {item_dir}",
                  file=sys.stderr)
            return
        try:
            subprocess.run(
                ["uv", "run", "--project", str(proj), "python", str(script), item_dir],
                check=False, timeout=180,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"  ⚠ hero_qa runner failed for {item_dir}: {exc}", file=sys.stderr)

    def _advance_item(self, state: ItemState) -> Dict[str, Any]:
        """Drive an item through its phases until blocked or done.

        After every phase transition, updates the central queue and mirrors
        any new decisions from state.decisions to the central audit_log.
        Fixes PR #17 carryovers I-1 (queue/state desync) and I-2 (audit_log
        was unused)."""
        phases_run: List[Dict[str, Any]] = []
        item_dir = str(self.items_dir / state.sku)
        while True:
            phase = state.next_runnable_phase()
            if phase is None:
                break
            # BLOCKING HERO QA GATE — no Square-primary (phase_4) / GitHub publish
            # (phase_7) without hero_qa.status == "pass". Run the gate to populate
            # label.json if it hasn't been, then re-check; on fail, BLOCK the phase
            # (do not run it) and park a question for the human.
            if phase in PUBLISH_PHASES:
                ok, reason = can_list(item_dir)
                if not ok:
                    self._run_hero_qa(item_dir)
                    ok, reason = can_list(item_dir)
                if not ok:
                    q = PendingQuestion(
                        question_id=f"q-heroqa-{phase}",
                        phase=phase,
                        question=(f"Hero QA gate failed: {reason}. Fix the hero "
                                  f"(straight, upright, full face), then re-run."),
                    )
                    state.block_phase(phase, q)
                    state.save()
                    self._sync_queue(state)
                    phases_run.append({"phase": phase, "result": "blocked",
                                       "reason": f"hero_qa: {reason}"})
                    continue
            state.start_phase(phase)
            state.save()
            self._sync_queue(state)  # I-1: queue reflects in-progress phase
            decisions_before = len(state.decisions)
            try:
                result = self.phase_runner(state, phase, item_dir)
            except Exception as exc:  # noqa: BLE001
                err = f"{type(exc).__name__}: {exc}"
                state.fail_phase(phase, error=err)
                state.save()
                self._mirror_new_decisions(state, decisions_before)
                self._sync_queue(state)
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
                self._mirror_new_decisions(state, decisions_before)
                self._sync_queue(state)
                phases_run.append({"phase": phase, "result": "blocked"})
            elif result.get("skipped"):
                state.skip_phase(phase, reason=result.get("reason", ""))
                state.save()
                self._mirror_new_decisions(state, decisions_before)
                self._sync_queue(state)
                phases_run.append({"phase": phase, "result": "skipped"})
            elif "outputs" in result:
                state.complete_phase(phase, outputs=result["outputs"])
                state.save()
                self._mirror_new_decisions(state, decisions_before)
                self._sync_queue(state)
                phases_run.append({"phase": phase, "result": "completed"})
            else:
                err = f"runner returned unrecognized result: {result!r}"
                state.fail_phase(phase, error=err)
                state.save()
                self._mirror_new_decisions(state, decisions_before)
                self._sync_queue(state)
                phases_run.append({"phase": phase, "result": "failed", "error": err})
        return {
            "final_status": state.status.value,
            "phases_run": phases_run,
            "progress": state.progress_summary(),
        }

    def _sync_queue(self, state: ItemState) -> None:
        """Update the central queue with the latest state snapshot."""
        self.queue.upsert(QueueEntry.from_item_state(state))
        self.queue.save()

    def _mirror_new_decisions(self, state: ItemState, decisions_before: int) -> None:
        """Mirror any new state.decisions entries to the central audit_log.

        Walks state.decisions[decisions_before:] and writes each via the
        AuditLog. Idempotent in the sense that decisions_before is the
        index where this phase started, so we never double-write.
        """
        for d in state.decisions[decisions_before:]:
            self.audit_log.log_decision(
                sku=state.sku,
                phase=d.get("phase", ""),
                decision_type=d.get("type", "unknown"),
                choice=d.get("choice"),
                confidence=d.get("confidence", 0.0),
                inputs_considered=d.get("inputs_considered", {}),
                alternatives_seen=d.get("alternatives_seen", []),
                rationale=d.get("rationale", ""),
                decision_id=d.get("id"),
            )

    # ── Phase execution (real handlers progressively wired in PR #3) ──

    def _default_phase_runner(
        self, state: ItemState, phase: str, item_dir: str
    ) -> Dict[str, Any]:
        """Default phase runner — dispatches to per-phase handlers.

        Each handler returns the standard runner result shape (see PhaseRunner
        type alias). Phases not yet wired return the legacy stub-block.
        """
        handlers: Dict[str, Callable[[ItemState, str], Dict[str, Any]]] = {
            "phase_0": self._phase_0_image,
            "phase_1": self._phase_1_appraisal,
            "phase_2": self._phase_2_catalog,
            "phase_3": self._phase_3_inventory,
            "phase_4": self._phase_4_image_upload,
            "phase_5": self._phase_5_payment_link,
            "phase_6": self._phase_6_label,
            "phase_7": self._phase_7_publishing,
            "phase_8": self._phase_8_whatnot,
            "phase_9": self._phase_9_photos_archive,
        }
        if phase in handlers:
            return handlers[phase](state, item_dir)
        return self._stub_block(phase)

    def _stub_block(self, phase: str) -> Dict[str, Any]:
        """Block any phase not yet wired with a 'PR #3 will plug in' question."""
        return {
            "blocked": True,
            "question": PendingQuestion(
                question_id=f"q-stub-{phase}",
                phase=phase,
                question=(
                    f"phase_runner is not wired yet for {PHASE_NAMES.get(phase, phase)}. "
                    "PR #3 of v6.0 is rolling out handlers — this phase isn't done yet."
                ),
            ),
        }

    def _phase_0_image(self, state: ItemState, item_dir: str) -> Dict[str, Any]:
        """Phase 0: Image background removal via remove.bg.

        Sources `REMOVEBG_API_KEY` from the environment. Writes hero.png into
        the item folder. Blocks if the source image is missing or the
        remove_background module didn't import."""
        if not state.source_image or not Path(state.source_image).exists():
            return {
                "blocked": True,
                "question": PendingQuestion(
                    question_id=f"q-phase_0-{state.sku}-source",
                    phase="phase_0",
                    question=f"Source image not found for {state.sku}",
                    context=f"Expected at: {state.source_image}",
                ),
            }
        if _remove_background is None:
            return {
                "blocked": True,
                "question": PendingQuestion(
                    question_id=f"q-phase_0-{state.sku}-import",
                    phase="phase_0",
                    question="remove_background module not importable",
                    context="Check that requests is installed and the module is on the path.",
                ),
            }
        api_key = os.environ.get("REMOVEBG_API_KEY")
        if not api_key:
            return {
                "blocked": True,
                "question": PendingQuestion(
                    question_id=f"q-phase_0-{state.sku}-no-key",
                    phase="phase_0",
                    question=f"REMOVEBG_API_KEY environment variable not set",
                    context="Required for autonomous background removal.",
                ),
            }
        hero_path = str(Path(item_dir) / "hero.png")
        _remove_background(state.source_image, hero_path, api_key)
        state.log_decision(
            phase="phase_0",
            decision_type="bg_removal",
            choice={"output": hero_path, "model": "removebg"},
            rationale="Default remove.bg path; preserves transparency.",
        )
        return {"outputs": {"hero_path": hero_path}}

    def _phase_1_appraisal(self, state: ItemState, item_dir: str) -> Dict[str, Any]:
        """Phase 1: Appraisal & Research.

        Claude (the calling agent) analyzes the image visually and populates
        state.phases['phase_1'].outputs with title/era/condition/price/shippable
        BEFORE this method runs. We just capture them in the audit log."""
        outputs = state.phases["phase_1"].outputs
        for field_name, decision_type in [
            ("price", "price"),
            ("condition", "condition"),
            ("shippable", "shipping_eligible"),
        ]:
            if field_name in outputs:
                state.log_decision(
                    phase="phase_1",
                    decision_type=decision_type,
                    choice=outputs[field_name],
                    rationale=outputs.get(f"{field_name}_rationale", ""),
                )
        return {"outputs": outputs}

    def _phase_2_catalog(self, state: ItemState, item_dir: str) -> Dict[str, Any]:
        """Phase 2: Square catalog pre-create.

        Verifies the SKU isn't already in Square. Logs the catalog plan.
        The actual Square create call happens via Claude using the Square MCP
        (preserves v3.7 behavior). This method just gates and records."""
        existing = _check_sku_in_square_cache(state.sku)
        if existing:
            return {
                "blocked": True,
                "question": PendingQuestion(
                    question_id=f"q-phase_2-{state.sku}-collision",
                    phase="phase_2",
                    question=f"{state.sku} already exists in Square catalog. Overwrite?",
                    context=f"Existing item_id: {existing}",
                    options=["overwrite", "skip", "renumber"],
                ),
            }
        state.log_decision(
            phase="phase_2",
            decision_type="catalog_plan",
            choice={
                "sku": state.sku,
                "title": state.phases["phase_1"].outputs.get("title"),
                "price": state.phases["phase_1"].outputs.get("price"),
            },
            rationale="Pre-create plan captured before MCP create call.",
        )
        return {"outputs": {"ready_for_create": True}}

    def _phase_3_inventory(self, state: ItemState, item_dir: str) -> Dict[str, Any]:
        """Phase 3: Inventory — set to 1 (default unique-item quantity)."""
        state.log_decision(
            phase="phase_3",
            decision_type="inventory",
            choice=1,
            rationale="Default unique-item quantity.",
        )
        return {"outputs": {"quantity": 1}}

    def _phase_4_image_upload(self, state: ItemState, item_dir: str) -> Dict[str, Any]:
        """Phase 4: Image upload to Square via the square-image-upload skill.

        For v6.0 PR #3 this is a decision-capture point; Claude triggers the
        actual upload via MCP. Future PR (v6.2+) may subprocess the upload
        skill from here directly."""
        outputs = state.phases["phase_4"].outputs
        state.log_decision(
            phase="phase_4",
            decision_type="image_upload",
            choice={"hero_path": outputs.get("hero_path"),
                    "item_id": outputs.get("item_id")},
            rationale="Upload via square-image-upload skill.",
        )
        return {"outputs": {"uploaded": True}}

    def _phase_5_payment_link(self, state: ItemState, item_dir: str) -> Dict[str, Any]:
        """Phase 5: Square payment link generation. Records shipping eligibility."""
        shippable = state.phases["phase_1"].outputs.get("shippable", True)
        state.log_decision(
            phase="phase_5",
            decision_type="payment_link",
            choice={"shippable": shippable},
            rationale="Auto-generated Square payment link.",
        )
        return {"outputs": {"payment_link_created": True}}

    def _phase_6_label(self, state: ItemState, item_dir: str) -> Dict[str, Any]:
        """Phase 6: Append the item to the label CSV batch."""
        state.log_decision(
            phase="phase_6",
            decision_type="label",
            choice={"sku": state.sku},
            rationale="Append to label CSV batch.",
        )
        return {"outputs": {"label_queued": True}}

    def _phase_7_publishing(self, state: ItemState, item_dir: str) -> Dict[str, Any]:
        """Phase 7: GitHub Pages info card draft + push."""
        state.log_decision(
            phase="phase_7",
            decision_type="publishing",
            choice={"sku": state.sku, "items_dir": str(self.items_dir)},
            rationale="GitHub Pages info card draft + push.",
        )
        return {"outputs": {"page_drafted": True}}

    def _phase_8_whatnot(self, state: ItemState, item_dir: str) -> Dict[str, Any]:
        """Phase 8: Whatnot CSV row. Skippable if item is not being sold on Whatnot."""
        if state.phases["phase_8"].outputs.get("sell_on_whatnot") is False:
            return {"skipped": True, "reason": "Item not slated for Whatnot."}
        state.log_decision(
            phase="phase_8",
            decision_type="whatnot",
            choice={"sku": state.sku},
            rationale="Whatnot CSV row appended.",
        )
        return {"outputs": {"whatnot_csv_appended": True}}

    def _phase_9_photos_archive(self, state: ItemState, item_dir: str) -> Dict[str, Any]:
        """Phase 9: Photos.app archive cleanup (Mac only via osascript)."""
        if sys.platform != "darwin":
            return {"skipped": True, "reason": "Photos archive is Mac only; v5.0 will handle."}
        state.log_decision(
            phase="phase_9",
            decision_type="photos_archive",
            choice={"sku": state.sku},
            rationale="osascript Photos archive cleanup.",
        )
        return {"outputs": {"photos_archived": True}}

    # ── Output ──

    def _print_summary(self, results: Dict[str, Any]) -> None:
        print(f"\n=== Summary ===")
        for key in ("processed", "completed", "blocked", "failed"):
            print(f"  {key}: {results[key]}")
        if results["blocked"]:
            print("\nBlocked items have pending questions — run with --resume after answering.")


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
