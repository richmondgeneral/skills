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


DEFAULT_ITEMS_DIR = "/Users/scottybe/workspace/square/items"


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
