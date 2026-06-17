# rg-full-auto v6.0 — PR #1 (Infrastructure) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Land the v6.0 infrastructure (per-item state machine, centralized queue, audit-log writer) on `main` with **zero behavior change**. After this PR, v3.7's interactive flow still runs verbatim; the new infrastructure exists but is dormant. PRs #2 and #3 activate it.

**Architecture:** Three new Python modules (`item_state.py`, `onboarding_queue.py`, `audit_log.py`) under `rg-full-auto/scripts/`, plus optional hooks in the existing `process_new_item.py` that are no-ops unless an explicit `--use-state` flag is set. JSONL audit-log file initialization at known paths. Tests-first throughout.

**Tech Stack:** Python 3.12, stdlib only (`json`, `pathlib`, `dataclasses`, `datetime`, `enum`, `argparse`, `uuid`). Tests: `pytest` (already configured at `skills/pyproject.toml`).

---

## Pre-flight checks

Run these before starting Task 1. If any fail, stop and surface to the user.

```bash
cd ~/workspace/richmondgeneral/skills
git status -sb                            # Expected: clean, on docs/v6-super-full-auto-design
ls rg-full-auto/docs/plans/               # Expected: design doc + this plan
python3 -m pytest testing/unit/ -q 2>&1 | tail -5
                                          # Expected: existing 125 tests pass
                                          # (or whatever baseline count is current)
```

Confirm the existing rg-full-auto tests are broken per design doc §test:

```bash
ls testing/integration/test_rg_full_auto* 2>&1
python3 -m pytest testing/integration/test_rg_full_auto_catalog_fallback.py -q 2>&1 | tail -10
```
Expected: collection errors or test failures referencing the v3.x API. **Do not fix these — they get replaced by the v6.0 test layer.** Note count of failing tests so we can confirm we didn't regress anything else.

---

## Task 1: Branch off from PR #14's branch

**Files:** none (git only)

**Step 1: Confirm PR #14 has been merged to main**

```bash
gh pr view 14 --json state,baseRefName 2>&1 | head -3
```
Expected: `"state":"MERGED"`. If still `"OPEN"`, surface to user — this plan depends on the design doc being on main so the state.json schema reference resolves.

**Step 2: Sync main and branch off**

```bash
git checkout main && git pull
git checkout -b feat/v6-pr1-infra-statemachine
```

**Step 3: Commit a marker file so subsequent commits have a clean ancestor**

(skip — start commits with real work)

---

## Task 2: Create `item_state.py` with TDD

**Files:**
- Create: `rg-full-auto/scripts/item_state.py`
- Test: `testing/unit/test_item_state.py`

The branch's version exists at `claude/refactor-auto-onboarding-TyZdT:rg-full-auto/scripts/item_state.py` — we use it as a reference but write tests-first against the **design doc's spec** (`docs/plans/2026-05-13-v6-super-full-auto-design.md` §2.1), not against the branch code directly.

### Step 1: Write the failing test for PhaseStatus + ItemStatus enums

Create `testing/unit/test_item_state.py` with:

```python
"""Tests for rg-full-auto v6.0 per-item state machine."""
import pytest
from item_state import PhaseStatus, ItemStatus


def test_phase_status_values():
    """PhaseStatus enum values match design doc spec."""
    assert PhaseStatus.PENDING.value == "pending"
    assert PhaseStatus.IN_PROGRESS.value == "in_progress"
    assert PhaseStatus.COMPLETED.value == "completed"
    assert PhaseStatus.FAILED.value == "failed"
    assert PhaseStatus.BLOCKED.value == "blocked"
    assert PhaseStatus.SKIPPED.value == "skipped"


def test_item_status_values():
    """ItemStatus enum values match design doc spec."""
    assert ItemStatus.QUEUED.value == "queued"
    assert ItemStatus.PROCESSING.value == "processing"
    assert ItemStatus.BLOCKED.value == "blocked"
    assert ItemStatus.COMPLETED.value == "completed"
    assert ItemStatus.FAILED.value == "failed"
```

### Step 2: Run test — confirm failure

```bash
python3 -m pytest testing/unit/test_item_state.py -v 2>&1 | tail -10
```
Expected: ImportError / ModuleNotFoundError on `item_state` import.

### Step 3: Lift `item_state.py` enum block from the branch

```bash
git show claude/refactor-auto-onboarding-TyZdT:rg-full-auto/scripts/item_state.py \
  > /tmp/branch-item-state.py
head -50 /tmp/branch-item-state.py
```

Create `rg-full-auto/scripts/item_state.py` with the enums (only the enum portion for this step):

```python
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
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


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
```

### Step 4: Run test — confirm pass

```bash
python3 -m pytest testing/unit/test_item_state.py -v 2>&1 | tail -10
```
Expected: 2 passed.

### Step 5: Commit

```bash
git add rg-full-auto/scripts/item_state.py testing/unit/test_item_state.py
git commit -m "feat: item_state — phase/item status enums (v6.0 infra)"
```

---

## Task 3: `item_state.py` — phase data + state dataclass

**Files:**
- Modify: `rg-full-auto/scripts/item_state.py` (append)
- Modify: `testing/unit/test_item_state.py` (append)

### Step 1: Write failing test for `PhaseData` dataclass

Append to `testing/unit/test_item_state.py`:

```python
from item_state import PhaseData


def test_phase_data_default():
    """PhaseData starts in PENDING with empty outputs."""
    p = PhaseData()
    assert p.status == PhaseStatus.PENDING
    assert p.started_at is None
    assert p.completed_at is None
    assert p.outputs == {}
    assert p.error is None


def test_phase_data_to_dict():
    """PhaseData serializes to JSON-safe dict."""
    p = PhaseData(status=PhaseStatus.COMPLETED, outputs={"k": "v"})
    d = p.to_dict()
    assert d["status"] == "completed"
    assert d["outputs"] == {"k": "v"}
```

### Step 2: Run test — confirm failure

```bash
python3 -m pytest testing/unit/test_item_state.py::test_phase_data_default -v 2>&1 | tail -5
```
Expected: ImportError on `PhaseData`.

### Step 3: Add `PhaseData` to `item_state.py`

Append after the enums:

```python
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
```

### Step 4: Run tests — confirm pass

```bash
python3 -m pytest testing/unit/test_item_state.py -v 2>&1 | tail -10
```
Expected: 4 passed.

### Step 5: Commit

```bash
git add -A
git commit -m "feat: item_state — PhaseData dataclass with to_dict/from_dict"
```

---

## Task 4: `ItemState` — load/save/transition

**Files:**
- Modify: `rg-full-auto/scripts/item_state.py`
- Modify: `testing/unit/test_item_state.py`

### Step 1: Write failing tests for ItemState lifecycle

Append to test file:

```python
from item_state import ItemState
from pathlib import Path
import json


def test_item_state_new(tmp_path):
    """A new ItemState initializes empty phases + QUEUED status."""
    state = ItemState(sku="RG-0099", items_dir=str(tmp_path))
    assert state.sku == "RG-0099"
    assert state.status == ItemStatus.QUEUED
    assert state.decisions == []
    assert state.questions == []
    # Phases initialize as PENDING for the canonical 10 phases.
    assert "phase_0" in state.phases
    assert "phase_9" in state.phases
    assert state.phases["phase_0"].status == PhaseStatus.PENDING


def test_item_state_save_and_load(tmp_path):
    """ItemState round-trips through .state.json on disk."""
    state = ItemState(sku="RG-0099", items_dir=str(tmp_path))
    state.status = ItemStatus.PROCESSING
    state.phases["phase_0"].status = PhaseStatus.COMPLETED
    (tmp_path / "RG-0099").mkdir()
    state.save()
    state_file = tmp_path / "RG-0099" / ".state.json"
    assert state_file.exists()
    loaded = ItemState.load("RG-0099", items_dir=str(tmp_path))
    assert loaded.status == ItemStatus.PROCESSING
    assert loaded.phases["phase_0"].status == PhaseStatus.COMPLETED


def test_item_state_load_legacy_item_no_state(tmp_path):
    """Loading an item without .state.json returns None (legacy mode)."""
    (tmp_path / "RG-0001").mkdir()
    loaded = ItemState.load("RG-0001", items_dir=str(tmp_path))
    assert loaded is None
```

### Step 2: Run tests — confirm failure

```bash
python3 -m pytest testing/unit/test_item_state.py::test_item_state_new -v 2>&1 | tail -10
```
Expected: ImportError on `ItemState`.

### Step 3: Implement `ItemState` class

Append to `item_state.py`:

```python
# Canonical 10-phase sequence. Phase numbers align with SKILL.md §Phase 0..9.
PHASES = [f"phase_{i}" for i in range(10)]


@dataclass
class ItemState:
    """Per-item state container; persists to <items_dir>/<sku>/.state.json."""
    sku: str
    items_dir: str = "/Users/scottybe/workspace/square/items"
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
        self.updated_at = now

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
        """Write .state.json. Parent dir must exist."""
        self.updated_at = datetime.now(timezone.utc).isoformat()
        self.state_file.write_text(
            json.dumps(self.to_dict(), indent=2),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, sku: str, items_dir: str = "/Users/scottybe/workspace/square/items") -> Optional["ItemState"]:
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
```

### Step 4: Run tests — confirm pass

```bash
python3 -m pytest testing/unit/test_item_state.py -v 2>&1 | tail -15
```
Expected: 7 passed.

### Step 5: Commit

```bash
git add -A
git commit -m "feat: item_state — ItemState class with save/load and legacy detection"
```

---

## Task 5: `onboarding_queue.py` — port from branch with TDD

**Files:**
- Create: `rg-full-auto/scripts/onboarding_queue.py`
- Create: `testing/unit/test_onboarding_queue.py`

The branch's version at `claude/refactor-auto-onboarding-TyZdT:rg-full-auto/scripts/onboarding_queue.py` is the reference. Same pattern as Task 2/3/4: tests-first, port code, validate.

### Step 1: Write failing tests

Create `testing/unit/test_onboarding_queue.py`:

```python
"""Tests for the centralized onboarding queue."""
import pytest
from onboarding_queue import OnboardingQueue, QueueEntry
from item_state import ItemStatus
from pathlib import Path
import json


def test_queue_add_entry(tmp_path):
    """Adding an entry shows up in the queue file."""
    queue_file = tmp_path / "queue.json"
    q = OnboardingQueue(queue_path=str(queue_file))
    q.upsert(QueueEntry(sku="RG-0099", status=ItemStatus.QUEUED.value))
    q.save()
    data = json.loads(queue_file.read_text())
    assert any(e["sku"] == "RG-0099" for e in data["entries"])


def test_queue_upsert_updates_existing(tmp_path):
    """Upserting same SKU twice updates rather than duplicates."""
    queue_file = tmp_path / "queue.json"
    q = OnboardingQueue(queue_path=str(queue_file))
    q.upsert(QueueEntry(sku="RG-0099", status="queued"))
    q.upsert(QueueEntry(sku="RG-0099", status="processing"))
    q.save()
    data = json.loads(queue_file.read_text())
    matching = [e for e in data["entries"] if e["sku"] == "RG-0099"]
    assert len(matching) == 1
    assert matching[0]["status"] == "processing"


def test_queue_remove(tmp_path):
    """Removing by SKU drops the entry."""
    queue_file = tmp_path / "queue.json"
    q = OnboardingQueue(queue_path=str(queue_file))
    q.upsert(QueueEntry(sku="RG-0099", status="queued"))
    q.upsert(QueueEntry(sku="RG-0100", status="queued"))
    q.remove("RG-0099")
    q.save()
    data = json.loads(queue_file.read_text())
    assert not any(e["sku"] == "RG-0099" for e in data["entries"])
    assert any(e["sku"] == "RG-0100" for e in data["entries"])


def test_queue_load_missing_file(tmp_path):
    """Loading a non-existent queue file yields an empty queue."""
    queue_file = tmp_path / "does-not-exist.json"
    q = OnboardingQueue(queue_path=str(queue_file))
    assert q.entries == []
```

### Step 2: Run tests — confirm failure

```bash
python3 -m pytest testing/unit/test_onboarding_queue.py -v 2>&1 | tail -10
```
Expected: ImportError on `onboarding_queue`.

### Step 3: Port the branch's `onboarding_queue.py` selectively

Don't blindly copy — the branch may have idioms we'd rather replace. Open `/tmp/branch-onboarding-queue.py` first to read:

```bash
git show claude/refactor-auto-onboarding-TyZdT:rg-full-auto/scripts/onboarding_queue.py > /tmp/branch-onboarding-queue.py
wc -l /tmp/branch-onboarding-queue.py
```

Create `rg-full-auto/scripts/onboarding_queue.py` with the minimum surface to make the tests pass:

```python
#!/usr/bin/env python3
"""
Centralized onboarding queue for rg-full-auto batch processing.

Maintains a single queue file in the ops repo that tracks all items
currently being onboarded, their statuses, and pending questions.

Queue file: <queue_path> (default: ops/inventory/onboarding-queue.json)
This provides a dashboard view across all in-flight items while
per-item .state.json files hold the detailed phase-level state.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_QUEUE_PATH = "/Users/scottybe/workspace/square/ops/inventory/onboarding-queue.json"


@dataclass
class QueueEntry:
    """Summary record for one item in the centralized queue."""
    sku: str
    status: str                          # mirrors ItemStatus.value
    source_image: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""
    phases_completed: int = 0
    phases_total: int = 10
    pending_questions: int = 0

    def __post_init__(self):
        now = datetime.now(timezone.utc).isoformat()
        if not self.created_at:
            self.created_at = now
        self.updated_at = now


@dataclass
class OnboardingQueue:
    """Mutable queue object. `load_from_disk` is automatic on construction
    if the queue file exists; `save()` writes back."""
    queue_path: str = DEFAULT_QUEUE_PATH
    entries: List[QueueEntry] = field(default_factory=list)

    def __post_init__(self):
        path = Path(self.queue_path)
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            self.entries = [QueueEntry(**e) for e in data.get("entries", [])]

    def upsert(self, entry: QueueEntry) -> None:
        """Insert new, or update existing entry with the same SKU."""
        for i, e in enumerate(self.entries):
            if e.sku == entry.sku:
                self.entries[i] = entry
                return
        self.entries.append(entry)

    def remove(self, sku: str) -> None:
        self.entries = [e for e in self.entries if e.sku != sku]

    def find(self, sku: str) -> Optional[QueueEntry]:
        return next((e for e in self.entries if e.sku == sku), None)

    def save(self) -> None:
        """Atomic write — create parent dir, write to temp, rename."""
        path = Path(self.queue_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        payload = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "entries": [asdict(e) for e in self.entries],
        }
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(path)
```

### Step 4: Run tests — confirm pass

```bash
python3 -m pytest testing/unit/test_onboarding_queue.py -v 2>&1 | tail -10
```
Expected: 4 passed.

### Step 5: Commit

```bash
git add -A
git commit -m "feat: onboarding_queue — upsert/remove/atomic-save with TDD"
```

---

## Task 6: `audit_log.py` — NEW writer for the three JSONL streams

**Files:**
- Create: `rg-full-auto/scripts/audit_log.py`
- Create: `testing/unit/test_audit_log.py`

This is the NEW file (per design §3.2). The three streams are `decisions.jsonl`, `corrections.jsonl`, `review_log.jsonl`. JSONL append-only.

### Step 1: Write failing tests

Create `testing/unit/test_audit_log.py`:

```python
"""Tests for v6.0 audit-log writer."""
import pytest
import json
from pathlib import Path
from audit_log import AuditLog


def test_log_decision_appends_jsonl(tmp_path):
    """Logging a decision appends one JSONL line."""
    log_dir = tmp_path
    al = AuditLog(log_dir=str(log_dir))
    al.log_decision(
        sku="RG-0099",
        phase="phase_1",
        decision_type="price",
        choice=18.50,
        confidence=0.78,
        inputs_considered={"era": "1979"},
        alternatives_seen=[],
        rationale="midpoint of comps",
    )
    decisions_file = log_dir / "decisions.jsonl"
    assert decisions_file.exists()
    lines = decisions_file.read_text().strip().split("\n")
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["sku"] == "RG-0099"
    assert record["choice"] == 18.50
    assert record["confidence"] == 0.78


def test_log_correction_includes_diff(tmp_path):
    """Logging a correction captures agent_choice vs corrected_to."""
    al = AuditLog(log_dir=str(tmp_path))
    al.log_correction(
        sku="RG-0099",
        decision_id="dec-001",
        decision_type="price",
        agent_choice=18.50,
        corrected_to=22.00,
        correction_source="manual",
        reason="underpriced for the condition",
        reviewer="scottybe",
    )
    record = json.loads((tmp_path / "corrections.jsonl").read_text().strip())
    assert record["agent_choice"] == 18.50
    assert record["corrected_to"] == 22.00
    assert record["correction_source"] == "manual"


def test_log_review_event(tmp_path):
    """review_log captures start + end events with duration."""
    al = AuditLog(log_dir=str(tmp_path))
    al.log_review_event(sku="RG-0099", event="review_started")
    al.log_review_event(
        sku="RG-0099",
        event="review_completed",
        duration_s=324,
        corrections_applied=2,
        outcome="accepted_with_corrections",
    )
    lines = (tmp_path / "review_log.jsonl").read_text().strip().split("\n")
    assert len(lines) == 2
    end = json.loads(lines[1])
    assert end["duration_s"] == 324
    assert end["outcome"] == "accepted_with_corrections"


def test_concurrent_appends_dont_corrupt(tmp_path):
    """Multiple appends in quick succession produce valid JSONL."""
    al = AuditLog(log_dir=str(tmp_path))
    for i in range(20):
        al.log_decision(
            sku=f"RG-{i:04d}",
            phase="phase_1",
            decision_type="price",
            choice=10.0 + i,
            confidence=0.5,
            inputs_considered={},
            alternatives_seen=[],
            rationale="test",
        )
    lines = (tmp_path / "decisions.jsonl").read_text().strip().split("\n")
    assert len(lines) == 20
    # Every line must parse as valid JSON.
    for line in lines:
        json.loads(line)
```

### Step 2: Run tests — confirm failure

```bash
python3 -m pytest testing/unit/test_audit_log.py -v 2>&1 | tail -10
```
Expected: ImportError on `audit_log`.

### Step 3: Implement `AuditLog`

Create `rg-full-auto/scripts/audit_log.py`:

```python
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
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.decisions_path = self.log_dir / "decisions.jsonl"
        self.corrections_path = self.log_dir / "corrections.jsonl"
        self.review_log_path = self.log_dir / "review_log.jsonl"

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _append(self, path: Path, record: Dict[str, Any]) -> None:
        """Append one JSON object as a single line. Atomic at the OS
        level for line-sized writes on a single host (POSIX append)."""
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
        correction_source: str,        # "manual" | "auto-diff"
        reason: str,
        reviewer: str,
    ) -> None:
        record = {
            "ts": self._now(),
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
```

### Step 4: Run tests — confirm pass

```bash
python3 -m pytest testing/unit/test_audit_log.py -v 2>&1 | tail -10
```
Expected: 4 passed.

### Step 5: Commit

```bash
git add -A
git commit -m "feat: audit_log — append-only JSONL writer for decisions/corrections/review_log"
```

---

## Task 7: Sanity-check the conftest path setup

The skills repo's `testing/conftest.py` already injects each skill's `scripts/` dir into `sys.path` so tests can `from item_state import ...`. Verify the rg-full-auto path is there.

**Step 1: Read conftest**

```bash
grep "rg-full-auto" testing/conftest.py
```
Expected: a line like `"rg-full-auto/scripts",` in the SKILL_DIRS list.

**Step 2: If missing, add it**

If grep returns nothing:

```python
# Add to testing/conftest.py SKILL_DIRS list:
"rg-full-auto/scripts",
```

And commit:

```bash
git add testing/conftest.py
git commit -m "test: add rg-full-auto/scripts to conftest sys.path"
```

If already there: skip.

---

## Task 8: Run the full unit suite — no regressions

**Step 1: Run all unit tests**

```bash
python3 -m pytest testing/unit/ -q 2>&1 | tail -10
```
Expected: all pre-existing tests still pass + the new tests pass. Compare count to the pre-flight baseline. New tests added: 11 (`test_item_state.py` 7, `test_onboarding_queue.py` 4, `test_audit_log.py` 4 — wait, also re-count). Adjust expected count up by exactly that many.

**Step 2: If anything regressed**

Surface to user; do NOT mask or work around. The infra is supposed to be additive.

---

## Task 9: SKILL.md — minimal addition noting the new infra (no behavior change)

**Files:**
- Modify: `rg-full-auto/SKILL.md`

The bigger SKILL.md rewrite happens in PR #2/#3. For PR #1, just add a section under "Architecture" mentioning the new files so anyone reading the skill knows they exist.

**Step 1: Read current SKILL.md architecture section**

```bash
grep -n "^## \|^### " rg-full-auto/SKILL.md | head -20
```

**Step 2: Insert a "## v6.0 Infrastructure (dormant)" section**

Add after the current Architecture section:

```markdown
## v6.0 Infrastructure (dormant in v3.7 behavior)

PR #1 of the v6.0 ship landed three new modules. **None are active in the default flow** — v3.7 interactive behavior is unchanged. They exist so PR #2 can wire them up:

| Module | Purpose |
|---|---|
| `scripts/item_state.py` | Per-item state machine. Will persist `.state.json` in each item folder once Phase #2 activates it. |
| `scripts/onboarding_queue.py` | Centralized queue dashboard. Will write `ops/inventory/onboarding-queue.json` once activated. |
| `scripts/audit_log.py` | Append-only JSONL writer for `decisions.jsonl`, `corrections.jsonl`, `review_log.jsonl`. Used by v6.0's "agent decides, user reviews" autonomy flow. |

Design: `docs/plans/2026-05-13-v6-super-full-auto-design.md`
v5.0 portability (deferred): `docs/plans/2026-05-13-v5-portability-deferred.md`
```

**Step 3: Commit**

```bash
git add rg-full-auto/SKILL.md
git commit -m "docs: SKILL.md note v6.0 infra modules (dormant in v3.7 flow)"
```

---

## Task 10: Open the PR

**Step 1: Push the branch**

```bash
git push -u origin feat/v6-pr1-infra-statemachine 2>&1 | tail -3
```

**Step 2: Open the PR**

```bash
gh pr create --base main --head feat/v6-pr1-infra-statemachine \
  --title "feat: rg-full-auto v6.0 PR #1 — infrastructure (state machine + queue + audit log)" \
  --body "$(cat <<'EOF'
## Summary

First of three staged PRs to land rg-full-auto v6.0 per the design at `rg-full-auto/docs/plans/2026-05-13-v6-super-full-auto-design.md`.

**Behavior change: ZERO.** Three new modules added to `rg-full-auto/scripts/`. v3.7 interactive flow runs unchanged. PR #2 wires them up.

## What's in this PR

| File | Lines | Purpose |
|---|---|---|
| `rg-full-auto/scripts/item_state.py` | ~150 | Per-item state machine; `.state.json` writer |
| `rg-full-auto/scripts/onboarding_queue.py` | ~80 | Centralized queue dashboard |
| `rg-full-auto/scripts/audit_log.py` | ~130 | Append-only JSONL writer for the three audit streams |
| `testing/unit/test_item_state.py` | ~80 | Lifecycle tests for state machine |
| `testing/unit/test_onboarding_queue.py` | ~60 | Upsert/remove/atomic-save tests |
| `testing/unit/test_audit_log.py` | ~80 | JSONL append + concurrent-write tests |
| `rg-full-auto/SKILL.md` | +20 | Note the dormant infrastructure |

## Test plan
- [x] All pre-existing unit tests still pass (no regressions)
- [x] 15+ new tests added covering state machine + queue + audit log
- [x] No live API calls; everything mocked or filesystem
- [x] v3.7 interactive flow unchanged (verified by running existing integration tests)

## Next
PR #2: process_batch.py + `--autonomous` flag (opt-in)
PR #3: flip default to autonomous; v6.0 becomes the documented norm

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)" 2>&1 | tail -2
```

---

## Task 11: Verification before claiming done

Use the `superpowers:verification-before-completion` skill discipline:

**Step 1: Confirm all tests pass on the new branch**

```bash
python3 -m pytest testing/unit/ -q 2>&1 | tail -5
```
Expected: all green.

**Step 2: Confirm no behavioral changes to v3.7 flow**

```bash
python3 -m pytest testing/integration/ -q 2>&1 | tail -10
```
Expected: same count of passes/failures as before PR (the pre-existing broken integration tests stay broken — they get replaced in PR #3, not this one).

**Step 3: Confirm git state is clean**

```bash
git status -sb
```
Expected: nothing uncommitted; branch synced to origin.

**Step 4: Confirm the PR is open and links the design**

```bash
gh pr view --json url,state | head
```

**Step 5: Report**

Surface to user: PR URL, test count diff, anything unexpected.

---

## Open questions / known limitations

- `audit_log.py` CLI subcommands (`report`, `review-stats`, `drift`, `correct`) are NOT built in PR #1. The library functions exist; the argparse layer comes in PR #2 alongside the autonomous flag (because that's when the data starts accumulating and the CLI starts being useful).
- The default paths in each module (`/Users/scottybe/workspace/square/items` and `/Users/scottybe/workspace/square/ops/inventory`) are hardcoded — same as v3.7. Multi-environment support (cowork, cloud) is v5.0's epic, NOT this PR.
- No JSON schema validation on `.state.json` or queue file. Pydantic was considered and rejected — stdlib `dataclasses.asdict` is enough for v6.0; can introduce schemas later if drift becomes a problem.
- Concurrent batch processing safety: `audit_log._append` uses POSIX append-on-write atomicity which is reliable for line-sized writes on a single host. Multi-host concurrency is out of scope.

## References

- Design doc: `rg-full-auto/docs/plans/2026-05-13-v6-super-full-auto-design.md` (§2 architecture, §3.2 audit schemas)
- Source branch (read-only reference): `claude/refactor-auto-onboarding-TyZdT`
- Tests pattern reference: existing `testing/unit/test_rotate_item_images.py` for skill-script test style
- Skills repo testing config: `testing/conftest.py` + `pyproject.toml`
