# rg-full-auto v6.0 — PR #2 (Orchestrator + Autonomous Mode, Opt-In) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Wire the PR #1 infrastructure into a working batch orchestrator and add an `--autonomous` opt-in flag to `process_new_item.py`. After this PR, autonomous mode runs end-to-end on real items but only when explicitly invoked. v3.7 interactive behavior remains the documented default.

**Architecture:** Three layers of work:
1. **Extend `item_state.py`** with the orchestration API (`PendingQuestion`, phase-lifecycle methods, dependency graph, decision logging) needed by the batch orchestrator.
2. **Create `process_batch.py`** — a stand-alone batch entry point with a `BatchOrchestrator` class that ingests photos, allocates SKUs, runs phases via state-machine transitions, parks blocked items, and prints a summary.
3. **Add `--autonomous` flag** to `process_new_item.py` plus an `AuditLog` CLI surface. Address the carry-over Important+Minor items from PR #1's final review.

**Tech Stack:** Python 3.11+ stdlib (`json`, `pathlib`, `dataclasses`, `datetime`, `enum`, `argparse`, `uuid`, `subprocess`). Tests: `pytest` via `uv run python -m pytest`. Reference source (read-only): `origin/claude/refactor-auto-onboarding-TyZdT` for the v4.0 implementation we're selectively porting.

---

## Pre-flight checks

Run these before Task 1. Stop and surface to user if any fail.

```bash
cd ~/workspace/richmondgeneral/skills
git status -sb                                    # Expected: clean, on main or this docs branch
git log --oneline -1                              # Confirm PR #15 (v6.0 PR #1) is on main
uv run python -m pytest testing/unit/ -q | tail -3
                                                  # Expected: 145 passed (PR #1 baseline)
```

Confirm reference branch is fetched:

```bash
git rev-parse origin/claude/refactor-auto-onboarding-TyZdT 2>&1 | head -1
```
If `fatal: invalid object name`, run `git fetch origin` first.

---

## PR #1 review carry-overs addressed in this PR

Three items flagged in PR #15's final review that this PR closes:

- **M-3:** `AuditLog.log_correction()` returns a `correction_id` (Task 9).
- **M-4:** `AuditLog.iter_records(stream)` read API for the JSONL streams (Task 9).
- **M-6:** `ItemState.__post_init__` and `QueueEntry.__post_init__` no longer bump `updated_at` when loaded from disk (Task 2).

The naming convention for phases (`phase_0` vs branch's `phase_0_image`): **keep PR #1's `phase_N` naming.** Add a `PHASE_NAMES` constant mapping numeric IDs to human-readable labels for log/dashboard output, but don't break the on-disk schema. Branch's descriptive scheme was aesthetic, not load-bearing.

---

## Task 1: Branch off main

**Files:** none (git only)

### Step 1: Sync main

```bash
cd ~/workspace/richmondgeneral/skills
git checkout main && git pull
git log --oneline -3
```
Expected: `3f31701 feat: rg-full-auto v6.0 PR #1 — infrastructure ...` at the top.

### Step 2: Branch

```bash
git checkout -b feat/v6-pr2-orchestrator
git status -sb
```
Expected: `## feat/v6-pr2-orchestrator`

---

## Task 2: Fix `updated_at`-on-load (M-6 carryover) + add `PHASE_DEPENDENCIES`

**Files:**
- Modify: `rg-full-auto/scripts/item_state.py`
- Modify: `testing/unit/test_item_state.py`

### Step 1: Write failing test for "load preserves updated_at"

Append to `testing/unit/test_item_state.py`:

```python
def test_item_state_load_preserves_updated_at(tmp_path):
    """Loading a serialized item should NOT bump updated_at — only mutations should."""
    import time
    (tmp_path / "RG-0099").mkdir()
    state = ItemState(sku="RG-0099", items_dir=str(tmp_path))
    state.save()
    original_updated = state.updated_at
    time.sleep(0.01)
    loaded = ItemState.load("RG-0099", items_dir=str(tmp_path))
    assert loaded.updated_at == original_updated, \
        "load() must preserve updated_at; bumping makes the in-memory model disagree with disk"


def test_phase_dependencies_constant_exists():
    """PHASE_DEPENDENCIES maps each phase to its required predecessors."""
    from item_state import PHASE_DEPENDENCIES, PHASES
    assert set(PHASE_DEPENDENCIES.keys()) == set(PHASES)
    # phase_0 has no deps
    assert PHASE_DEPENDENCIES["phase_0"] == []
    # phase_4 (image upload) needs phase_0 (image) AND phase_2 (catalog)
    assert "phase_0" in PHASE_DEPENDENCIES["phase_4"]
    assert "phase_2" in PHASE_DEPENDENCIES["phase_4"]
```

### Step 2: Run tests — confirm failure

```bash
uv run python -m pytest testing/unit/test_item_state.py::test_item_state_load_preserves_updated_at testing/unit/test_item_state.py::test_phase_dependencies_constant_exists -v 2>&1 | tail -10
```
Expected: 2 FAILED (load bumps updated_at; PHASE_DEPENDENCIES doesn't exist).

### Step 3: Implement

Modify `item_state.py`:

1. Move the `updated_at` bump out of `__post_init__` into save():

```python
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
```

2. In `save()`, call `touch()` explicitly:

```python
    def save(self) -> None:
        """Write .state.json atomically (tmp → rename). Parent dir must exist."""
        self.touch()
        tmp = self.state_file.with_suffix(self.state_file.suffix + ".tmp")
        tmp.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        tmp.replace(self.state_file)
```

3. Add `PHASE_DEPENDENCIES` constant after `PHASES`:

```python
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
```

4. Add `PHASE_NAMES` for human-readable output:

```python
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
```

### Step 4: Run tests — expect pass

```bash
uv run python -m pytest testing/unit/test_item_state.py -v 2>&1 | tail -15
```
Expected: 13 passed (11 from PR #1 + 2 new).

### Step 5: Commit

```bash
git add -A
git commit -m "feat: item_state — load preserves updated_at + PHASE_DEPENDENCIES + PHASE_NAMES"
```

---

## Task 3: `PendingQuestion` dataclass

**Files:**
- Modify: `rg-full-auto/scripts/item_state.py`
- Modify: `testing/unit/test_item_state.py`

The branch has this class verbatim. Port with TDD.

### Step 1: Write failing tests

Append to `testing/unit/test_item_state.py`:

```python
def test_pending_question_defaults():
    """A new PendingQuestion has empty answer + asked_at timestamp."""
    from item_state import PendingQuestion
    q = PendingQuestion(question_id="q-001", phase="phase_1", question="What era?")
    assert q.answer is None
    assert q.is_answered() is False
    assert q.context == ""
    assert q.options == []
    assert q.asked_at != ""  # __post_init__ sets it


def test_pending_question_is_answered():
    """is_answered returns True when answer is non-empty."""
    from item_state import PendingQuestion
    q = PendingQuestion(question_id="q-001", phase="phase_1", question="?")
    assert q.is_answered() is False
    q.answer = "1979"
    assert q.is_answered() is True
    q.answer = ""
    assert q.is_answered() is False  # empty string doesn't count


def test_pending_question_round_trip(tmp_path):
    """PendingQuestion round-trips through asdict / from_dict."""
    from item_state import PendingQuestion
    from dataclasses import asdict
    q = PendingQuestion(
        question_id="q-001",
        phase="phase_1",
        question="What era?",
        context="The cover has 1979 stamped",
        options=["1970s", "1980s"],
        answer="1979",
    )
    d = asdict(q)
    assert d["answer"] == "1979"
    q2 = PendingQuestion(**d)
    assert q2.is_answered()
    assert q2.options == ["1970s", "1980s"]
```

### Step 2: Run tests — confirm failure

```bash
uv run python -m pytest testing/unit/test_item_state.py::test_pending_question_defaults -v 2>&1 | tail -5
```
Expected: ImportError on `PendingQuestion`.

### Step 3: Add `PendingQuestion` to `item_state.py`

Insert after the `PhaseData` class:

```python
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
```

### Step 4: Run tests — expect pass

```bash
uv run python -m pytest testing/unit/test_item_state.py -v 2>&1 | tail -15
```
Expected: 16 passed (13 + 3 new).

### Step 5: Commit

```bash
git add -A
git commit -m "feat: item_state — PendingQuestion dataclass for parked-question model"
```

---

## Task 4: `ItemState` phase-lifecycle methods

**Files:**
- Modify: `rg-full-auto/scripts/item_state.py`
- Modify: `testing/unit/test_item_state.py`

Add `start_phase`, `complete_phase`, `fail_phase`, `block_phase`, `skip_phase`, plus the status-recalc helper that keeps `state.status` consistent with phase states.

### Step 1: Write failing tests

Append to `testing/unit/test_item_state.py`:

```python
def test_start_phase_transitions_pending_to_in_progress(tmp_path):
    """start_phase records started_at and transitions to IN_PROGRESS."""
    state = ItemState(sku="RG-0099", items_dir=str(tmp_path))
    state.start_phase("phase_0")
    assert state.phases["phase_0"].status == PhaseStatus.IN_PROGRESS
    assert state.phases["phase_0"].started_at != ""
    assert state.status == ItemStatus.PROCESSING


def test_complete_phase_records_outputs(tmp_path):
    """complete_phase records completed_at and stores outputs."""
    state = ItemState(sku="RG-0099", items_dir=str(tmp_path))
    state.start_phase("phase_0")
    state.complete_phase("phase_0", outputs={"hero_path": "/tmp/hero.png"})
    p = state.phases["phase_0"]
    assert p.status == PhaseStatus.COMPLETED
    assert p.completed_at != ""
    assert p.outputs["hero_path"] == "/tmp/hero.png"


def test_fail_phase_records_error(tmp_path):
    """fail_phase records the error and transitions item status to FAILED."""
    state = ItemState(sku="RG-0099", items_dir=str(tmp_path))
    state.start_phase("phase_0")
    state.fail_phase("phase_0", error="remove.bg returned 500")
    assert state.phases["phase_0"].status == PhaseStatus.FAILED
    assert state.phases["phase_0"].error == "remove.bg returned 500"
    assert state.status == ItemStatus.FAILED


def test_block_phase_parks_question_and_blocks_item(tmp_path):
    """block_phase moves phase to BLOCKED and item to BLOCKED."""
    from item_state import PendingQuestion
    state = ItemState(sku="RG-0099", items_dir=str(tmp_path))
    state.start_phase("phase_1")
    q = PendingQuestion(question_id="q-001", phase="phase_1", question="What era?")
    state.block_phase("phase_1", q)
    assert state.phases["phase_1"].status == PhaseStatus.BLOCKED
    assert state.status == ItemStatus.BLOCKED
    assert len(state.questions) == 1


def test_skip_phase(tmp_path):
    """skip_phase marks a phase SKIPPED with reason."""
    state = ItemState(sku="RG-0099", items_dir=str(tmp_path))
    state.skip_phase("phase_8", reason="not selling on Whatnot")
    assert state.phases["phase_8"].status == PhaseStatus.SKIPPED
    assert state.phases["phase_8"].outputs.get("skip_reason") == "not selling on Whatnot"


def test_item_status_recalculates(tmp_path):
    """After all phases complete or skip, item status becomes COMPLETED."""
    state = ItemState(sku="RG-0099", items_dir=str(tmp_path))
    for phase in [f"phase_{i}" for i in range(10)]:
        state.start_phase(phase)
        state.complete_phase(phase, outputs={})
    assert state.status == ItemStatus.COMPLETED
```

### Step 2: Run tests — confirm failure

```bash
uv run python -m pytest testing/unit/test_item_state.py::test_start_phase_transitions_pending_to_in_progress -v 2>&1 | tail -5
```
Expected: AttributeError on `start_phase`.

### Step 3: Implement on `ItemState`

Append these methods inside the `ItemState` class:

```python
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
```

### Step 4: Run tests — expect pass

```bash
uv run python -m pytest testing/unit/test_item_state.py -v 2>&1 | tail -20
```
Expected: 22 passed (16 + 6 new).

### Step 5: Commit

```bash
git add -A
git commit -m "feat: item_state — phase lifecycle methods (start/complete/fail/block/skip) with status recalc"
```

---

## Task 5: `ItemState` queries — `next_runnable_phase`, `progress_summary`, `log_decision`, `answer_question`

**Files:**
- Modify: `rg-full-auto/scripts/item_state.py`
- Modify: `testing/unit/test_item_state.py`

### Step 1: Write failing tests

Append to test file:

```python
def test_next_runnable_phase_starts_at_phase_0(tmp_path):
    state = ItemState(sku="RG-0099", items_dir=str(tmp_path))
    assert state.next_runnable_phase() == "phase_0"


def test_next_runnable_phase_respects_dependencies(tmp_path):
    """After phase_0 completes, phase_1 is runnable. phase_2 isn't until phase_1 done."""
    state = ItemState(sku="RG-0099", items_dir=str(tmp_path))
    state.start_phase("phase_0")
    state.complete_phase("phase_0", outputs={})
    runnable = state.next_runnable_phase()
    assert runnable == "phase_1"


def test_next_runnable_phase_returns_none_when_all_done(tmp_path):
    state = ItemState(sku="RG-0099", items_dir=str(tmp_path))
    for p in [f"phase_{i}" for i in range(10)]:
        state.start_phase(p)
        state.complete_phase(p, outputs={})
    assert state.next_runnable_phase() is None


def test_next_runnable_phase_skips_blocked_branch(tmp_path):
    """If phase_1 is BLOCKED, phase_2 (depends on phase_1) can't run; but phase_4 only
    needs phase_0 AND phase_2 — also can't run. Returns None when nothing runnable."""
    from item_state import PendingQuestion
    state = ItemState(sku="RG-0099", items_dir=str(tmp_path))
    state.start_phase("phase_0")
    state.complete_phase("phase_0", outputs={})
    state.start_phase("phase_1")
    state.block_phase("phase_1", PendingQuestion(question_id="q", phase="phase_1", question="?"))
    # phase_1 is blocked. phase_2 depends on phase_1, can't run. Nothing else has phase_0 as
    # its ONLY dep (phase_4 needs phase_2 too). So next runnable = None.
    assert state.next_runnable_phase() is None


def test_progress_summary(tmp_path):
    """progress_summary returns counts by phase status."""
    state = ItemState(sku="RG-0099", items_dir=str(tmp_path))
    state.start_phase("phase_0")
    state.complete_phase("phase_0", outputs={})
    summary = state.progress_summary()
    assert summary["completed"] == 1
    assert summary["pending"] == 9
    assert summary["total"] == 10


def test_log_decision_appends_to_state(tmp_path):
    """log_decision appends a decision record to state.decisions."""
    state = ItemState(sku="RG-0099", items_dir=str(tmp_path))
    state.log_decision(
        phase="phase_1",
        decision_type="price",
        choice=18.50,
        rationale="midpoint of comps",
    )
    assert len(state.decisions) == 1
    assert state.decisions[0]["type"] == "price"
    assert state.decisions[0]["choice"] == 18.50


def test_answer_question_unblocks(tmp_path):
    """answer_question fills in the answer + can transition the phase back."""
    from item_state import PendingQuestion
    state = ItemState(sku="RG-0099", items_dir=str(tmp_path))
    state.start_phase("phase_1")
    state.block_phase("phase_1", PendingQuestion(
        question_id="q-001", phase="phase_1", question="?"
    ))
    result = state.answer_question("q-001", "1979")
    assert result == "phase_1"
    assert state.questions[0]["answer"] == "1979"
    # Phase remains BLOCKED until orchestrator decides to re-run it; just stores answer.
    assert state.phases["phase_1"].status == PhaseStatus.BLOCKED
```

### Step 2: Run tests — confirm failure

```bash
uv run python -m pytest testing/unit/test_item_state.py::test_next_runnable_phase_starts_at_phase_0 -v 2>&1 | tail -5
```
Expected: AttributeError.

### Step 3: Implement

Append to `ItemState`:

```python
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
```

### Step 4: Run tests — expect pass

```bash
uv run python -m pytest testing/unit/test_item_state.py -v 2>&1 | tail -25
```
Expected: 29 passed (22 + 7 new).

### Step 5: Commit

```bash
git add -A
git commit -m "feat: item_state — next_runnable_phase + progress_summary + log_decision + answer_question"
```

---

## Task 6: Extend `OnboardingQueue` — `from_item_state`, `get_active`, `get_blocked`

**Files:**
- Modify: `rg-full-auto/scripts/onboarding_queue.py`
- Modify: `testing/unit/test_onboarding_queue.py`

### Step 1: Write failing tests

Append to `testing/unit/test_onboarding_queue.py`:

```python
def test_queue_entry_from_item_state(tmp_path):
    """QueueEntry.from_item_state populates fields from a live ItemState."""
    from item_state import ItemState, ItemStatus, PhaseStatus
    (tmp_path / "RG-0099").mkdir()
    state = ItemState(sku="RG-0099", items_dir=str(tmp_path))
    state.start_phase("phase_0")
    state.complete_phase("phase_0", outputs={})
    entry = QueueEntry.from_item_state(state)
    assert entry.sku == "RG-0099"
    assert entry.status == state.status.value
    assert entry.phases_completed == 1
    assert entry.phases_total == 10


def test_queue_get_active_excludes_completed_and_failed(tmp_path):
    q = OnboardingQueue(queue_path=str(tmp_path / "queue.json"))
    q.upsert(QueueEntry(sku="RG-0001", status="queued"))
    q.upsert(QueueEntry(sku="RG-0002", status="processing"))
    q.upsert(QueueEntry(sku="RG-0003", status="completed"))
    q.upsert(QueueEntry(sku="RG-0004", status="failed"))
    q.upsert(QueueEntry(sku="RG-0005", status="blocked"))
    active = q.get_active()
    skus = {e.sku for e in active}
    assert skus == {"RG-0001", "RG-0002", "RG-0005"}  # blocked stays active for resume


def test_queue_get_blocked(tmp_path):
    q = OnboardingQueue(queue_path=str(tmp_path / "queue.json"))
    q.upsert(QueueEntry(sku="RG-0001", status="queued"))
    q.upsert(QueueEntry(sku="RG-0002", status="blocked"))
    blocked = q.get_blocked()
    assert len(blocked) == 1
    assert blocked[0].sku == "RG-0002"
```

### Step 2: Run tests — confirm failure

```bash
uv run python -m pytest testing/unit/test_onboarding_queue.py -v 2>&1 | tail -8
```
Expected: AttributeError on `from_item_state` / `get_active` / `get_blocked`.

### Step 3: Implement

Add to `onboarding_queue.py`:

1. At top of file, import `ItemState`:
```python
from item_state import ItemState, ItemStatus, PhaseStatus  # type: ignore
```

2. To `QueueEntry`, add classmethod:
```python
    @classmethod
    def from_item_state(cls, state: "ItemState") -> "QueueEntry":
        """Build a queue entry from a live ItemState. Both sides share strings."""
        completed = sum(
            1 for p in state.phases.values() if p.status == PhaseStatus.COMPLETED
        )
        unanswered = sum(1 for q in state.questions if not q.get("answer"))
        return cls(
            sku=state.sku,
            status=state.status.value,
            source_image=state.source_image,
            created_at=state.created_at,
            phases_completed=completed,
            phases_total=len(state.phases),
            pending_questions=unanswered,
        )
```

3. To `OnboardingQueue`, add methods:
```python
    def get_active(self) -> List[QueueEntry]:
        """Entries in non-terminal states: queued / processing / blocked."""
        terminal = {ItemStatus.COMPLETED.value, ItemStatus.FAILED.value}
        return [e for e in self.entries if e.status not in terminal]

    def get_blocked(self) -> List[QueueEntry]:
        return [e for e in self.entries if e.status == ItemStatus.BLOCKED.value]
```

### Step 4: Run tests — expect pass

```bash
uv run python -m pytest testing/unit/test_onboarding_queue.py -v 2>&1 | tail -10
```
Expected: 7 passed (4 + 3 new).

### Step 5: Commit

```bash
git add -A
git commit -m "feat: onboarding_queue — from_item_state + get_active/get_blocked"
```

---

## Task 7: `AuditLog` carryovers — `correction_id` return + `iter_records`

**Files:**
- Modify: `rg-full-auto/scripts/audit_log.py`
- Modify: `testing/unit/test_audit_log.py`

### Step 1: Write failing tests

Append to `testing/unit/test_audit_log.py`:

```python
def test_log_correction_returns_id(tmp_path):
    """log_correction returns a correction_id for chained traceability."""
    al = AuditLog(log_dir=str(tmp_path))
    cid = al.log_correction(
        sku="RG-0099",
        decision_id="dec-001",
        decision_type="price",
        agent_choice=18.50,
        corrected_to=22.00,
        correction_source="manual",
        reason="underpriced",
        reviewer="scottybe",
    )
    assert cid.startswith("cor-")
    assert len(cid) == 12  # "cor-" + 8 hex


def test_iter_records_yields_decoded_jsonl(tmp_path):
    """iter_records yields one dict per JSONL line, lazily."""
    al = AuditLog(log_dir=str(tmp_path))
    for i in range(3):
        al.log_decision(
            sku=f"RG-{i:04d}",
            phase="phase_1",
            decision_type="price",
            choice=float(10 + i),
            confidence=0.5,
            inputs_considered={},
            alternatives_seen=[],
            rationale="t",
        )
    records = list(al.iter_records("decisions"))
    assert len(records) == 3
    assert records[0]["sku"] == "RG-0000"
    assert records[2]["choice"] == 12.0


def test_iter_records_empty_file(tmp_path):
    """iter_records on a non-existent stream returns an empty iterator."""
    al = AuditLog(log_dir=str(tmp_path / "empty"))
    records = list(al.iter_records("decisions"))
    assert records == []


def test_iter_records_invalid_stream_raises(tmp_path):
    """iter_records rejects unknown stream names."""
    al = AuditLog(log_dir=str(tmp_path))
    with pytest.raises(ValueError, match="Unknown stream"):
        list(al.iter_records("not_a_stream"))
```

### Step 2: Run tests — confirm failure

```bash
uv run python -m pytest testing/unit/test_audit_log.py -v 2>&1 | tail -10
```
Expected: 3 FAILED + 1 ERROR (correction returns None; iter_records doesn't exist).

### Step 3: Implement

Modify `log_correction` signature + return type:

```python
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
```

Add `iter_records` method:

```python
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
```

### Step 4: Run tests — expect pass

```bash
uv run python -m pytest testing/unit/test_audit_log.py -v 2>&1 | tail -10
```
Expected: 9 passed (5 + 4 new).

### Step 5: Commit

```bash
git add -A
git commit -m "feat: audit_log — log_correction returns correction_id + iter_records reader API"
```

---

## Task 8: `AuditLog` CLI subcommands (report, review-stats, drift)

**Files:**
- Modify: `rg-full-auto/scripts/audit_log.py` (add CLI block)
- Create: `testing/unit/test_audit_log_cli.py`

`drift` detects decisions where the agent's choice doesn't match the current item state (e.g., price drifted in Square). For PR #2, implement `report` and `review-stats`. Mark `drift` and `correct` as **TODO for PR #3** — they need integration with the live Square cache and the L3 layer that's deferred to v6.1+.

### Step 1: Write failing CLI tests

Create `testing/unit/test_audit_log_cli.py`:

```python
"""Tests for audit_log.py CLI subcommands."""
import json
import subprocess
import sys
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[2] / "rg-full-auto" / "scripts" / "audit_log.py"


def _seed(log_dir: Path):
    """Write a few records to the streams under log_dir."""
    from audit_log import AuditLog
    al = AuditLog(log_dir=str(log_dir))
    did = al.log_decision(
        sku="RG-0099", phase="phase_1", decision_type="price",
        choice=18.50, confidence=0.78,
        inputs_considered={}, alternatives_seen=[], rationale="t",
    )
    al.log_correction(
        sku="RG-0099", decision_id=did, decision_type="price",
        agent_choice=18.50, corrected_to=22.00,
        correction_source="manual", reason="underpriced", reviewer="scottybe",
    )
    al.log_review_event(sku="RG-0099", event="review_started")
    al.log_review_event(
        sku="RG-0099", event="review_completed",
        duration_s=324, corrections_applied=1, outcome="accepted_with_corrections",
    )


def test_cli_report_by_sku(tmp_path, capsys):
    """audit_log.py report --sku RG-0099 prints decisions for that SKU."""
    _seed(tmp_path)
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "report", "--sku", "RG-0099", "--log-dir", str(tmp_path)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "RG-0099" in result.stdout
    assert "phase_1" in result.stdout
    assert "18.5" in result.stdout


def test_cli_review_stats(tmp_path):
    """review-stats prints the per-SKU review duration + outcome."""
    _seed(tmp_path)
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "review-stats", "--log-dir", str(tmp_path)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "RG-0099" in result.stdout
    assert "324" in result.stdout
    assert "accepted_with_corrections" in result.stdout
```

### Step 2: Run tests — confirm failure

```bash
uv run python -m pytest testing/unit/test_audit_log_cli.py -v 2>&1 | tail -10
```
Expected: 2 FAILED (script doesn't have CLI yet).

### Step 3: Implement CLI

Add to bottom of `audit_log.py`:

```python
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
    sub = parser.add_subparsers(dest="cmd", required=True)

    rp = sub.add_parser("report", help="Print decisions filtered by SKU or date")
    rp.add_argument("--sku", help="Filter to one SKU")
    rp.add_argument("--since", help="ISO timestamp; show decisions on/after this")

    sub.add_parser("review-stats", help="Aggregate review timings + outcomes per SKU")

    # Placeholders for PR #3 (need live state diff):
    drift = sub.add_parser("drift", help="(TODO v6.1) Detect decisions that drifted from current state")
    correct = sub.add_parser("correct", help="(TODO PR #3) Apply a manual correction interactively")

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


import argparse  # imported lazily so library use doesn't pay the cost

if __name__ == "__main__":
    sys.exit(main())
```

Note: `argparse` and `sys` are now actually used; the prior unused-import flag clears.

### Step 4: Run tests — expect pass

```bash
uv run python -m pytest testing/unit/test_audit_log_cli.py -v 2>&1 | tail -10
```
Expected: 2 passed.

Also confirm full unit suite still passes:

```bash
uv run python -m pytest testing/unit/ -q 2>&1 | tail -3
```

### Step 5: Commit

```bash
git add -A
git commit -m "feat: audit_log — CLI subcommands report + review-stats (drift/correct TODO)"
```

---

## Task 9: Create `process_batch.py` — orchestrator scaffold

**Files:**
- Create: `rg-full-auto/scripts/process_batch.py`
- Create: `testing/unit/test_process_batch.py`

This task lands the orchestrator class with the structural API. The actual phase handlers (`_phase_0_image`, etc.) get stubs that delegate to a single configurable callback so tests can inject mocks. PR #3 wires the real Square/remove.bg integration.

### Step 1: Write failing tests

Create `testing/unit/test_process_batch.py`:

```python
"""Tests for the batch orchestrator (PR #2)."""
import json
from pathlib import Path

import pytest

from process_batch import BatchOrchestrator
from item_state import ItemState, ItemStatus, PhaseStatus, PendingQuestion


def test_orchestrator_ingest_creates_state_files(tmp_path, monkeypatch):
    """ingest_photos creates one .state.json per valid image."""
    photo = tmp_path / "input" / "photo1.jpeg"
    photo.parent.mkdir()
    photo.write_bytes(b"fake")  # extension is what matters for the filter
    items_dir = tmp_path / "items"
    queue_path = tmp_path / "queue.json"

    orch = BatchOrchestrator(
        items_dir=str(items_dir),
        queue_path=str(queue_path),
        next_sku=lambda: "RG-0099",
    )
    states = orch.ingest_photos([str(photo)])
    assert len(states) == 1
    assert states[0].sku == "RG-0099"
    assert (items_dir / "RG-0099" / ".state.json").exists()


def test_orchestrator_advance_runs_phases_until_blocked(tmp_path):
    """_advance_item iterates next_runnable_phase until phase returns blocked or no more runnable."""
    items_dir = tmp_path / "items"
    items_dir.mkdir()
    sku = "RG-0099"
    (items_dir / sku).mkdir()
    state = ItemState(sku=sku, items_dir=str(items_dir),
                      source_image=str(tmp_path / "src.jpg"))
    (tmp_path / "src.jpg").write_bytes(b"x")
    state.save()

    # Phase handler that completes phase_0 with outputs, blocks phase_1.
    def fake_runner(state, phase, item_dir):
        if phase == "phase_0":
            return {"outputs": {"hero_path": "/tmp/x.png"}}
        if phase == "phase_1":
            return {
                "blocked": True,
                "question": PendingQuestion(
                    question_id="q-001", phase="phase_1",
                    question="What era?",
                ),
            }
        return {"outputs": {}}

    orch = BatchOrchestrator(
        items_dir=str(items_dir),
        queue_path=str(tmp_path / "queue.json"),
        phase_runner=fake_runner,
    )
    result = orch._advance_item(state)
    assert state.phases["phase_0"].status == PhaseStatus.COMPLETED
    assert state.phases["phase_1"].status == PhaseStatus.BLOCKED
    assert state.status == ItemStatus.BLOCKED


def test_orchestrator_process_all_returns_summary(tmp_path):
    """process_all returns counts of completed/blocked/failed across items."""
    items_dir = tmp_path / "items"
    items_dir.mkdir()
    queue_path = tmp_path / "queue.json"

    for sku in ("RG-0001", "RG-0002"):
        (items_dir / sku).mkdir()
        state = ItemState(sku=sku, items_dir=str(items_dir),
                          source_image=str(tmp_path / f"{sku}.jpg"))
        (tmp_path / f"{sku}.jpg").write_bytes(b"x")
        state.save()

    from onboarding_queue import OnboardingQueue, QueueEntry
    queue = OnboardingQueue(queue_path=str(queue_path))
    queue.upsert(QueueEntry(sku="RG-0001", status="queued"))
    queue.upsert(QueueEntry(sku="RG-0002", status="queued"))
    queue.save()

    # Trivial runner that completes every phase with empty outputs
    def trivial(state, phase, item_dir):
        return {"outputs": {}}

    orch = BatchOrchestrator(
        items_dir=str(items_dir),
        queue_path=str(queue_path),
        phase_runner=trivial,
    )
    summary = orch.process_all()
    assert summary["processed"] == 2
    assert summary["completed"] == 2
    assert summary["blocked"] == 0
    assert summary["failed"] == 0
```

### Step 2: Run tests — confirm failure

```bash
uv run python -m pytest testing/unit/test_process_batch.py -v 2>&1 | tail -10
```
Expected: ImportError on `process_batch`.

### Step 3: Implement orchestrator

Create `rg-full-auto/scripts/process_batch.py`:

```python
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
            return {"status": "idle", "processed": 0, "completed": 0,
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

    # ── Per-item advancement ──

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

    # ── Phase execution stub (replaced in PR #3) ──

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
```

### Step 4: Run tests — expect pass

```bash
uv run python -m pytest testing/unit/test_process_batch.py -v 2>&1 | tail -10
```
Expected: 3 passed.

Full suite:

```bash
uv run python -m pytest testing/unit/ -q 2>&1 | tail -3
```

### Step 5: Commit

```bash
git add -A
git commit -m "feat: process_batch — BatchOrchestrator with injectable phase_runner + CLI"
```

---

## Task 10: Add `--autonomous` flag to `process_new_item.py`

**Files:**
- Modify: `rg-full-auto/scripts/process_new_item.py`
- Create: `testing/unit/test_process_new_item_autonomous_flag.py`

The flag is opt-in. When set, `process_new_item` initializes an `ItemState`, opens a `BatchOrchestrator`, and runs the single item through it. When NOT set (default), the existing v3.7 interactive flow runs unchanged.

### Step 1: Write failing test

Create `testing/unit/test_process_new_item_autonomous_flag.py`:

```python
"""Tests for the --autonomous flag plumbing on process_new_item.py."""
import subprocess
import sys
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[2] / "rg-full-auto" / "scripts" / "process_new_item.py"


def test_help_lists_autonomous_flag():
    """--help output must mention --autonomous."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "--autonomous" in result.stdout


def test_autonomous_flag_short_circuits_interactive(monkeypatch, tmp_path):
    """Importing the module and calling main with --autonomous should NOT call input()."""
    import importlib.util

    # Stage a fake image and a fake items_dir
    photo = tmp_path / "photo.jpeg"
    photo.write_bytes(b"x")
    items_dir = tmp_path / "items"
    items_dir.mkdir()

    spec = importlib.util.spec_from_file_location("process_new_item", str(SCRIPT))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore

    # Sanity-check: the v6.0 dispatcher branch exists
    assert hasattr(mod, "_run_autonomous"), \
        "--autonomous flag must dispatch to a _run_autonomous function"
```

### Step 2: Run tests — confirm failure

```bash
uv run python -m pytest testing/unit/test_process_new_item_autonomous_flag.py -v 2>&1 | tail -10
```
Expected: 2 FAILED — flag not listed; `_run_autonomous` not present.

### Step 3: Implement

Modify `process_new_item.py`:

1. At top of file, after the existing imports:

```python
from item_state import ItemState
from onboarding_queue import OnboardingQueue, QueueEntry
```

2. Add a new function before `main()`:

```python
def _run_autonomous(image_path: str, items_dir: Optional[str] = None) -> int:
    """v6.0 autonomous entry point. Init item state, run through orchestrator.

    Opt-in path: only reached when `--autonomous` is passed. Default behavior
    remains v3.7 interactive. PR #3 makes autonomous the default.
    """
    from process_batch import BatchOrchestrator

    orch = BatchOrchestrator(items_dir=items_dir) if items_dir else BatchOrchestrator()
    states = orch.ingest_photos([image_path])
    if not states:
        print("Could not ingest image. Aborting.", file=sys.stderr)
        return 1
    print(f"Ingested {states[0].sku}. Running orchestrator…")
    summary = orch.process_all()
    print(f"\nFinal: {summary['completed']} completed, {summary['blocked']} blocked, "
          f"{summary['failed']} failed.")
    return 0 if summary["failed"] == 0 else 1
```

3. Update argparse and `main()`:

```python
    parser.add_argument(
        "--autonomous",
        action="store_true",
        help="v6.0 opt-in: run through BatchOrchestrator instead of interactive flow",
    )
    parser.add_argument(
        "--items-dir",
        default=None,
        help="Override the items directory (default: /Users/scottybe/workspace/square/items)",
    )

    args = parser.parse_args()

    if args.autonomous:
        return _run_autonomous(args.image, items_dir=args.items_dir)

    # Existing v3.7 interactive path
    try:
        processor = RGItemProcessor(interactive=not args.auto)
        processor.run(args.image)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0
```

(Adjust the existing `main()` to `return` instead of `sys.exit`.)

### Step 4: Run tests — expect pass

```bash
uv run python -m pytest testing/unit/test_process_new_item_autonomous_flag.py -v 2>&1 | tail -5
```
Expected: 2 passed.

### Step 5: Commit

```bash
git add -A
git commit -m "feat: process_new_item — add --autonomous opt-in flag that dispatches to BatchOrchestrator"
```

---

## Task 11: Integration test — fixture item end-to-end with mocked Square + remove.bg

**Files:**
- Create: `testing/integration/test_v6_autonomous_e2e.py`
- Create: `testing/fixtures/sample-photo.jpeg` (1×1 px placeholder)

This test exercises the full ingest → orchestrate → save flow using a mock `phase_runner` that simulates each phase succeeding with deterministic outputs. **No live Square or remove.bg calls.**

### Step 1: Stage the fixture

```bash
mkdir -p testing/fixtures
uv run python -c "from PIL import Image; Image.new('RGB', (1,1)).save('testing/fixtures/sample-photo.jpeg')"
ls -la testing/fixtures/
```

### Step 2: Write failing test

Create `testing/integration/test_v6_autonomous_e2e.py`:

```python
"""End-to-end autonomous flow with mock phase runner."""
import json
from pathlib import Path

import pytest

from process_batch import BatchOrchestrator
from item_state import ItemState, ItemStatus, PhaseStatus
from audit_log import AuditLog


FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "sample-photo.jpeg"


def test_autonomous_e2e_one_item(tmp_path):
    items_dir = tmp_path / "items"
    queue_path = tmp_path / "queue.json"
    audit_dir = tmp_path / "audit"

    # Phase runner that simulates every phase succeeding.
    decisions_made = []

    def fake_runner(state, phase, item_dir):
        # Log a decision for phases 1, 2, 5 (the ones with real choices)
        if phase == "phase_1":
            state.log_decision(
                phase=phase, decision_type="price",
                choice=18.50, confidence=0.78, rationale="midpoint comps",
            )
            decisions_made.append("price")
        if phase == "phase_2":
            state.log_decision(
                phase=phase, decision_type="type_category",
                choice="CLZCJ62H4TTHDQ3ZBYMZQASQ", confidence=0.95,
                rationale="visible binding suggests Books & Paper",
            )
            decisions_made.append("type_category")
        return {"outputs": {"phase": phase, "result": "mocked-success"}}

    orch = BatchOrchestrator(
        items_dir=str(items_dir),
        queue_path=str(queue_path),
        phase_runner=fake_runner,
        next_sku=lambda: "RG-9999",
        audit_log=AuditLog(log_dir=str(audit_dir)),
    )

    states = orch.ingest_photos([str(FIXTURE)])
    assert len(states) == 1
    assert states[0].sku == "RG-9999"

    summary = orch.process_all()
    assert summary["completed"] == 1
    assert summary["blocked"] == 0
    assert summary["failed"] == 0

    final = ItemState.load("RG-9999", items_dir=str(items_dir))
    assert final.status == ItemStatus.COMPLETED
    assert all(p.status == PhaseStatus.COMPLETED for p in final.phases.values())
    assert len(final.decisions) == 2
    assert "price" in decisions_made
```

### Step 3: Run — confirm pass

```bash
uv run python -m pytest testing/integration/test_v6_autonomous_e2e.py -v 2>&1 | tail -5
```
Expected: 1 passed.

### Step 4: Confirm pre-existing integration tests are unaffected

```bash
uv run python -m pytest testing/integration/ -q 2>&1 | tail -3
```
Expected: 7 passed (6 prior + 1 new).

### Step 5: Commit

```bash
git add testing/fixtures/sample-photo.jpeg testing/integration/test_v6_autonomous_e2e.py
git commit -m "test: v6.0 integration — autonomous e2e with mock phase runner"
```

---

## Task 12: SKILL.md — document `--autonomous` as opt-in (no default flip)

**Files:**
- Modify: `rg-full-auto/SKILL.md`

The "v6.0 Infrastructure (dormant)" section from PR #1 gets replaced with an "Autonomous mode (opt-in)" section. v3.7 interactive remains the documented default. PR #3 makes autonomous the default.

### Step 1: Update the section in `SKILL.md`

Replace the block currently labeled `## v6.0 Infrastructure (dormant in v3.7 behavior)` with:

```markdown
## v6.0 Autonomous Mode (opt-in)

PR #2 of the v6.0 ship wired the infrastructure from PR #1 into a working batch orchestrator. Autonomous mode runs end-to-end on real items but **only when explicitly invoked** — v3.7 interactive remains the default. PR #3 will flip the default.

### Invocation

```bash
# Single item, autonomous
uv run python ~/.claude/skills/rg-full-auto/scripts/process_new_item.py \
    --image ~/Desktop/photo.jpeg --autonomous

# Batch
uv run python ~/.claude/skills/rg-full-auto/scripts/process_batch.py \
    ingest --photos ~/Desktop/batch/*.jpeg
uv run python ~/.claude/skills/rg-full-auto/scripts/process_batch.py run
uv run python ~/.claude/skills/rg-full-auto/scripts/process_batch.py status
uv run python ~/.claude/skills/rg-full-auto/scripts/process_batch.py resume
```

### Audit trail

Every autonomous decision is recorded. Inspect with:

```bash
uv run python ~/.claude/skills/rg-full-auto/scripts/audit_log.py report --sku RG-XXXX
uv run python ~/.claude/skills/rg-full-auto/scripts/audit_log.py review-stats
```

### What's still TODO

- The default `phase_runner` in `process_batch.py` blocks every phase pending PR #3, which wires the real Square / remove.bg / Photos integrations.
- `audit_log.py drift` and `correct` are stubbed (TODO PR #3 / v6.1).

Design: `docs/plans/2026-05-13-v6-super-full-auto-design.md`
v5.0 portability (deferred): `docs/plans/2026-05-13-v5-portability-deferred.md`
PR #2 plan (this one): `docs/plans/2026-05-13-v6-pr2-orchestrator.md`
PR #3 plan: `docs/plans/2026-05-13-v6-pr3-flip-default.md`
```

### Step 2: Commit

```bash
git add rg-full-auto/SKILL.md
git commit -m "docs: SKILL.md — document v6.0 autonomous mode as opt-in (PR #3 flips default)"
```

---

## Task 13: Push branch and open PR

### Step 1: Push

```bash
git push -u origin feat/v6-pr2-orchestrator 2>&1 | tail -3
```

### Step 2: Stat the diff

```bash
git diff main..HEAD --stat | tail -15
```

### Step 3: Open the PR

```bash
gh pr create --base main --head feat/v6-pr2-orchestrator \
  --title "feat: rg-full-auto v6.0 PR #2 — orchestrator + autonomous opt-in" \
  --body "$(cat <<'EOF'
## Summary

Second of three staged PRs for v6.0. Wires the PR #1 infrastructure into a working `BatchOrchestrator` and adds a `--autonomous` opt-in flag to `process_new_item.py`. v3.7 interactive remains the default behavior; PR #3 flips it.

## What's in this PR

| Area | What |
|---|---|
| `item_state.py` | Phase lifecycle (`start/complete/fail/block/skip`), `next_runnable_phase`, `progress_summary`, `log_decision`, `answer_question`, `PendingQuestion`, `PHASE_DEPENDENCIES`, `PHASE_NAMES`, `touch()`. Load no longer bumps `updated_at` (M-6 carryover). |
| `onboarding_queue.py` | `QueueEntry.from_item_state`, `get_active`, `get_blocked`. |
| `audit_log.py` | `log_correction` returns `correction_id` (M-3). `iter_records(stream)` reader API (M-4). CLI subcommands: `report`, `review-stats`. `drift` + `correct` stubbed (PR #3 / v6.1). |
| **`process_batch.py` (NEW)** | `BatchOrchestrator` class with `ingest_photos`, `process_all`, `resume`, `status`. Phase runner is injectable for testing. Default runner blocks every phase pending PR #3. |
| `process_new_item.py` | `--autonomous` opt-in flag dispatches to `BatchOrchestrator`. v3.7 interactive path untouched when flag is off. |
| Tests | ~20 new unit tests + 1 integration e2e test with mock phase runner. |

## Test plan

- [x] All pre-existing unit tests still pass (no regressions)
- [x] ~20 new unit tests added across item_state, onboarding_queue, audit_log, audit_log_cli, process_batch, process_new_item
- [x] Integration test exercises full ingest → orchestrate → save with mock phase runner
- [x] No live Square or remove.bg calls
- [x] v3.7 interactive flow unchanged (existing tests for it remain green)

## Carryovers from PR #1 final review

- **M-3** correction_id return → ✅ Task 7
- **M-4** AuditLog.iter_records → ✅ Task 7
- **M-6** updated_at-on-load → ✅ Task 2

## Next

PR #3 (final): wire the default `phase_runner` to call sibling skills for real Square/remove.bg/Photos work; flip the default to autonomous; replace the broken `test_rg_full_auto_catalog_fallback.py`; bump SKILL.md version to v6.0.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)" 2>&1 | tail -2
```

---

## Task 14: Verification before claiming done

### Step 1: Unit + integration suites

```bash
uv run python -m pytest testing/unit/ testing/integration/ -q 2>&1 | tail -3
```
Expected: green; new tests added without regression.

### Step 2: Smoke-test the CLI scripts

```bash
uv run python rg-full-auto/scripts/process_batch.py --help | head -10
uv run python rg-full-auto/scripts/process_batch.py status
uv run python rg-full-auto/scripts/audit_log.py --help | head -10
uv run python rg-full-auto/scripts/process_new_item.py --help | head -15
```
All should exit 0 and show their help / empty-state output.

### Step 3: Git clean

```bash
git status -sb
git log --oneline main..HEAD
```

### Step 4: PR is open

```bash
gh pr view --json url,state,mergeable,mergeStateStatus
```

### Step 5: Report

Surface to user: PR URL, test count diff, anything unexpected.

---

## Open questions / known limitations

- **Phase runner stub.** The default runner blocks every phase. This is intentional — wiring the real Square / remove.bg / Photos integration is PR #3's scope. Reviewers should NOT request that this PR also include those handlers; doing so doubles the diff and the risk surface.
- **No concurrency.** Items run sequentially. The design doc accepts this and defers parallel-within-batch to a follow-up.
- **Audit log CLI on macOS only.** `audit_log.py` writes to `/Users/scottybe/workspace/square/ops/inventory/` by default. Linux/CI test runs always pass an explicit `--log-dir`.
- **`drift` and `correct` subcommands not implemented.** They need a live Square cache integration; deferred to PR #3 or v6.1.
- **No fault injection test for atomic save.** PR #1 review noted the gap; still deferred. The cleanup test (`test_item_state_save_is_atomic_via_tmp_rename`) covers the invariant we care most about (no orphan `.tmp` files).

## References

- Design doc: `rg-full-auto/docs/plans/2026-05-13-v6-super-full-auto-design.md`
- PR #1 plan: `rg-full-auto/docs/plans/2026-05-13-v6-pr1-infrastructure.md`
- PR #1 final review carryovers: M-3, M-4, M-6 (addressed here)
- Source branch reference (read-only): `origin/claude/refactor-auto-onboarding-TyZdT`
- PR #3 plan (next): `rg-full-auto/docs/plans/2026-05-13-v6-pr3-flip-default.md`
