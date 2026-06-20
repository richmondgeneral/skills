#!/usr/bin/env python3
"""
Per-item state machine for rg-full-auto batch onboarding.

Tracks each item through the 10-phase pipeline independently.
State persists as .state.json inside each item's folder, enabling:
- Resume after failures
- Async user clarification (park → continue)
- Cross-session persistence

State file: <items_dir>/RG-XXXX/.state.json
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_ITEMS_DIR = "/Users/scottybe/workspace/richmondgeneral/items"


class PhaseStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"       # Waiting on user input or external dependency
    SKIPPED = "skipped"       # Intentionally skipped (e.g., no Whatnot listing)


class ItemStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    BLOCKED = "blocked"       # At least one phase needs user input
    COMPLETED = "completed"
    FAILED = "failed"         # Unrecoverable failure


@dataclass
class PhaseData:
    """One phase's status + outputs for a single item."""
    status: PhaseStatus = PhaseStatus.PENDING
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_s: Optional[float] = None
    outputs: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PhaseData":
        d = dict(d)
        d["status"] = PhaseStatus(d.get("status", "pending"))
        return cls(**d)


@dataclass
class PendingQuestion:
    """A question parked for the user to answer asynchronously."""
    question_id: str
    phase: str
    question: str
    context: str = ""
    options: List[str] = field(default_factory=list)
    answer: Optional[str] = None
    asked_at: str = ""

    def __post_init__(self):
        if not self.asked_at:
            self.asked_at = datetime.now(timezone.utc).isoformat()

    def is_answered(self) -> bool:
        return bool(self.answer)


# Canonical 10-phase sequence. Phase numbers align with SKILL.md §Phase 0..9.
PHASES = [f"phase_{i}" for i in range(10)]


# Each phase lists its required predecessors. Used by next_runnable_phase()
# to determine which phases can run when others are blocked.
PHASE_DEPENDENCIES: Dict[str, List[str]] = {
    "phase_0": [],                              # image bg-removal
    "phase_1": ["phase_0"],                     # appraisal (needs cleaned hero)
    "phase_2": ["phase_1"],                     # catalog (needs price + title)
    "phase_3": ["phase_2"],                     # inventory (needs variation_id)
    "phase_4": ["phase_0", "phase_2"],          # image upload (hero + item_id)
    "phase_5": ["phase_2"],                     # payment link (needs price)
    "phase_6": ["phase_1", "phase_5"],          # label CSV (needs appraisal + link)
    "phase_7": ["phase_0", "phase_1", "phase_5"], # publishing (hero + content + link)
    "phase_8": ["phase_7"],                     # Whatnot CSV (needs published card)
    "phase_9": ["phase_0", "phase_7"],          # Photos archive (cleanup last)
}


# Human-readable labels for logs and dashboards. The on-disk schema uses
# the numeric phase_N keys; labels are display-only.
PHASE_NAMES: Dict[str, str] = {
    "phase_0": "Image Processing",
    "phase_1": "Appraisal & Research",
    "phase_2": "Square Catalog",
    "phase_3": "Inventory Setup",
    "phase_4": "Image Upload",
    "phase_5": "Payment Link",
    "phase_6": "Label CSV",
    "phase_7": "Publishing",
    "phase_8": "Whatnot CSV",
    "phase_9": "Photos Archive",
}


# Phases that publish a hero externally; the Hero QA gate must pass before them.
# phase_4 = Square primary image upload, phase_7 = GitHub Pages publishing.
PUBLISH_PHASES = ("phase_4", "phase_7")


def can_list(item_dir: str) -> "tuple[bool, str]":
    """Read-side chokepoint: True only if label.json -> hero_qa.status == 'pass'.
    Pure label.json read (no cv2) so the orchestrator can call it cheaply before
    every publish phase. No item may go Listed / publish a hero without a pass."""
    p = Path(item_dir) / "label.json"
    if not p.exists():
        return False, "no label.json — hero_qa gate not run"
    try:
        hero_qa = (json.loads(p.read_text(encoding="utf-8")).get("hero_qa") or {})
    except Exception as exc:
        return False, f"label.json unreadable: {exc}"
    status = hero_qa.get("status")
    if status == "pass":
        return True, "hero_qa pass"
    return False, f"hero_qa status={status or 'not_checked'} (must be 'pass' before publish)"


@dataclass
class ItemState:
    """Per-item state container; persists to <items_dir>/<sku>/.state.json."""
    sku: str
    items_dir: str = DEFAULT_ITEMS_DIR
    status: ItemStatus = ItemStatus.QUEUED
    source_image: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""
    created_in: str = "mac_cli"   # mac_cli | linux_cli | cowork | cloud
    phases: Dict[str, PhaseData] = field(default_factory=dict)
    decisions: List[Dict[str, Any]] = field(default_factory=list)
    questions: List[Dict[str, Any]] = field(default_factory=list)
    review: Dict[str, Any] = field(default_factory=lambda: {
        "agent_finished_at": None,
        "human_reviewed_at": None,
        "elapsed_review_s": None,
        "outcome": None,
    })

    def __post_init__(self):
        if not self.phases:
            self.phases = {p: PhaseData() for p in PHASES}
        now = datetime.now(timezone.utc).isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:                    # NEW — only set on first creation
            self.updated_at = now

    def touch(self) -> None:                       # NEW
        """Bump updated_at to now. Call before save() on mutations."""
        self.updated_at = datetime.now(timezone.utc).isoformat()

    @property
    def state_file(self) -> Path:
        return Path(self.items_dir) / self.sku / ".state.json"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sku": self.sku,
            "status": self.status.value,
            "source_image": self.source_image,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "created_in": self.created_in,
            "phases": {k: v.to_dict() for k, v in self.phases.items()},
            "decisions": self.decisions,
            "questions": self.questions,
            "review": self.review,
        }

    def save(self) -> None:
        """Write .state.json atomically (tmp → rename). Parent dir must exist."""
        self.touch()
        tmp = self.state_file.with_suffix(self.state_file.suffix + ".tmp")
        tmp.write_text(
            json.dumps(self.to_dict(), indent=2),
            encoding="utf-8",
        )
        tmp.replace(self.state_file)

    @classmethod
    def load(cls, sku: str, items_dir: str = DEFAULT_ITEMS_DIR) -> Optional["ItemState"]:
        """Load .state.json from disk. Returns None if no state file
        (legacy item that predates v6.0)."""
        path = Path(items_dir) / sku / ".state.json"
        if not path.exists():
            return None
        d = json.loads(path.read_text(encoding="utf-8"))
        phases = {k: PhaseData.from_dict(v) for k, v in d.get("phases", {}).items()}
        return cls(
            sku=d["sku"],
            items_dir=items_dir,
            status=ItemStatus(d.get("status", "queued")),
            source_image=d.get("source_image"),
            created_at=d.get("created_at", ""),
            updated_at=d.get("updated_at", ""),
            created_in=d.get("created_in", "mac_cli"),
            phases=phases,
            decisions=d.get("decisions", []),
            questions=d.get("questions", []),
            review=d.get("review", {}),
        )

    def _validate_phase(self, phase: str) -> None:
        if phase not in self.phases:
            raise ValueError(f"Unknown phase: {phase}. Known: {list(self.phases.keys())}")

    def start_phase(self, phase: str) -> None:
        """Transition a phase from PENDING to IN_PROGRESS and update item status."""
        self._validate_phase(phase)
        p = self.phases[phase]
        p.status = PhaseStatus.IN_PROGRESS
        p.started_at = datetime.now(timezone.utc).isoformat()
        self._recalculate_status()

    def complete_phase(self, phase: str, outputs: Optional[Dict[str, Any]] = None) -> None:
        """Mark a phase COMPLETED with its produced outputs."""
        self._validate_phase(phase)
        p = self.phases[phase]
        p.status = PhaseStatus.COMPLETED
        p.completed_at = datetime.now(timezone.utc).isoformat()
        if p.started_at:
            try:
                started = datetime.fromisoformat(p.started_at)
                completed = datetime.fromisoformat(p.completed_at)
                p.duration_s = (completed - started).total_seconds()
            except ValueError:
                pass
        if outputs:
            p.outputs.update(outputs)
        self._recalculate_status()

    def fail_phase(self, phase: str, error: str) -> None:
        """Mark a phase FAILED with the error message. Item status becomes FAILED."""
        self._validate_phase(phase)
        p = self.phases[phase]
        p.status = PhaseStatus.FAILED
        p.completed_at = datetime.now(timezone.utc).isoformat()
        p.error = error
        self._recalculate_status()

    def block_phase(self, phase: str, question: "PendingQuestion") -> None:
        """Park a phase BLOCKED with a question. Item status becomes BLOCKED."""
        self._validate_phase(phase)
        self.phases[phase].status = PhaseStatus.BLOCKED
        # Store as plain dict so existing decisions/questions JSON layout still works.
        from dataclasses import asdict
        self.questions.append(asdict(question))
        self._recalculate_status()

    def skip_phase(self, phase: str, reason: str = "") -> None:
        """Intentionally skip a phase (e.g., no Whatnot listing for this item)."""
        self._validate_phase(phase)
        p = self.phases[phase]
        p.status = PhaseStatus.SKIPPED
        if reason:
            p.outputs["skip_reason"] = reason
        self._recalculate_status()

    def _recalculate_status(self) -> None:
        """Sync item-level status with the aggregate of phase statuses."""
        statuses = {p.status for p in self.phases.values()}
        if PhaseStatus.FAILED in statuses:
            self.status = ItemStatus.FAILED
        elif PhaseStatus.BLOCKED in statuses:
            self.status = ItemStatus.BLOCKED
        elif PhaseStatus.IN_PROGRESS in statuses:
            self.status = ItemStatus.PROCESSING
        elif statuses.issubset({PhaseStatus.COMPLETED, PhaseStatus.SKIPPED}):
            self.status = ItemStatus.COMPLETED
        else:
            self.status = ItemStatus.QUEUED

    def next_runnable_phase(self) -> Optional[str]:
        """Return the next phase that's PENDING and has all dependencies completed.
        Returns None if nothing is runnable (all done, all blocked-by-deps, etc.)."""
        for phase, deps in PHASE_DEPENDENCIES.items():
            if self.phases[phase].status != PhaseStatus.PENDING:
                continue
            if all(self.phases[d].status == PhaseStatus.COMPLETED for d in deps):
                return phase
        return None

    def progress_summary(self) -> Dict[str, int]:
        """Phase-status counts for dashboard display."""
        counts = {s.value: 0 for s in PhaseStatus}
        for p in self.phases.values():
            counts[p.status.value] += 1
        counts["total"] = len(self.phases)
        return counts

    def log_decision(
        self,
        phase: str,
        decision_type: str,
        choice: Any,
        rationale: str = "",
        confidence: Optional[float] = None,
        inputs_considered: Optional[Dict[str, Any]] = None,
        alternatives_seen: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Append a decision record to state.decisions. Returns the decision_id."""
        import uuid
        did = f"dec-{uuid.uuid4().hex[:8]}"
        record = {
            "id": did,
            "phase": phase,
            "type": decision_type,
            "choice": choice,
            "rationale": rationale,
            "made_at": datetime.now(timezone.utc).isoformat(),
        }
        if confidence is not None:
            record["confidence"] = confidence
        if inputs_considered is not None:
            record["inputs_considered"] = inputs_considered
        if alternatives_seen is not None:
            record["alternatives_seen"] = alternatives_seen
        self.decisions.append(record)
        return did

    def answer_question(self, question_id: str, answer: str) -> Optional[str]:
        """Fill in an answer for a parked question. Returns the phase id if found, else None."""
        for q in self.questions:
            if q.get("question_id") == question_id:
                q["answer"] = answer
                q["answered_at"] = datetime.now(timezone.utc).isoformat()
                return q.get("phase")
        return None
