# PRD: rg-full-auto v5.0 — Environment-Aware Autonomous Onboarding

**Version:** 0.1 (Draft)
**Date:** 2026-02-19
**Author:** scottybe + claude
**Status:** RFC — Requesting Comments

---

## 1. Problem Statement

### What Exists Today (v4.0)

rg-full-auto v4.0 introduced batch-first processing, per-item state machines, and autonomous decision-making. The architecture is sound but has critical gaps:

1. **Hardcoded to local Mac** — All paths assume `/Users/scottybe/`, all binary ops assume osascript, all Chrome automation assumes local browser. The skill cannot run in Claude Code on the web (Cowork), cloud containers, or Windows.

2. **Tests are broken** — Existing integration tests (`test_rg_full_auto_catalog_fallback.py`) reference the v3.x API (`RGItemProcessor(interactive=False)`, `processor.phase3_catalog()`). No tests exist for the v4.0 state machine, queue manager, or batch orchestrator.

3. **Trigger mechanism is manual** — User must explicitly say "onboard these" or run a CLI command. No automated polling for new photos, no watch-and-start capability.

4. **Claude environment blindness** — The skill doesn't detect which Claude environment it's running in (Code CLI on Mac, Code on web/Cowork, cloud container) and can't adapt its behavior accordingly.

5. **Phases can't degrade gracefully** — If osascript isn't available (Cowork/cloud), ALL Mac-dependent phases fail rather than doing what they can and deferring what they can't.

### What We Want (v5.0)

A single `rg-full-auto` skill that:
- **Detects its runtime environment** and adapts phase execution accordingly
- **Runs everywhere Claude runs** — local Mac, Cowork, cloud, Windows (future)
- **Polls for work** via Photos.app clustering (local) OR user prompt (everywhere)
- **Degrades gracefully** — does API-portable phases in cloud, defers Mac-only phases
- **Has passing tests** for state machine, queue, batch orchestrator, and phase logic
- **Communicates appropriately** — interactive chat in Cowork, structured output in Code CLI

---

## 2. Environments & Capabilities

### 2.1 Environment Matrix

| Environment | Description | Filesystem | osascript | Square API | Chrome MCP | Photos.app | Git Push |
|-------------|------------|-----------|-----------|-----------|-----------|-----------|---------|
| **Code CLI (Mac)** | Terminal on user's Mac | Full | Yes | Yes (via MCP or `~/.env`) | Yes | Yes | Yes |
| **Code CLI (Linux/Win)** | Terminal on non-Mac | Full (local) | No | Yes (if token set) | Possible | No | Yes |
| **Cowork (Web)** | Claude web chat, collaborative | Sandboxed | No | Yes (if MCP configured) | No | No | No (unless git MCP) |
| **Cloud Container** | Headless Claude agent | `/mnt/` only | No | Yes (if token injected) | No | No | Possible via API |

### 2.2 Capability Detection

At skill invocation time, detect available capabilities:

```python
class RuntimeCapabilities:
    has_osascript: bool       # Can run AppleScript (macOS only)
    has_filesystem: bool      # Can read/write user's local files
    has_square_mcp: bool      # Square MCP server connected
    has_square_token: bool    # SQUARE_ACCESS_TOKEN available
    has_chrome_mcp: bool      # Chrome/browser MCP tools available
    has_photos_db: bool       # Photos.app SQLite accessible
    has_git: bool             # Git available for push operations
    has_removebg: bool        # REMOVEBG_API_KEY available
    has_image_api: bool       # Any image processing API available
    environment: str          # "mac_cli" | "linux_cli" | "cowork" | "cloud"
    interaction_mode: str     # "cli" (structured) | "chat" (conversational)
```

**Detection method:** Python probe script (`scripts/detect_env.py`) that tests each capability and outputs JSON. Claude reads the output and adapts.

### 2.3 Phase Portability Classification

| Phase | Portable? | Mac-Only Operations | Cloud Alternative |
|-------|-----------|--------------------|--------------------|
| **0: Image Processing** | Partial | `sips` compression, HEIC conversion, Photos.app cluster | User provides image directly; skip compression if under limit |
| **1: Appraisal** | Yes | None (Claude's own reasoning) | Fully portable |
| **2: Catalog Creation** | Yes | None (Square API) | Fully portable via MCP or direct API |
| **3: Inventory** | Yes | None (Square API) | Fully portable |
| **4: Image Upload** | Partial | osascript script execution | Direct API call with `requests` if token available |
| **5: Payment Link** | Yes | None (Square API) | Fully portable |
| **6: Label** | Partial | Writes to local CSV | Generate CSV content, defer file write |
| **7: Publishing** | Partial | Git push, HTML file write | Generate HTML content, defer git push (or use GitHub API) |
| **8: Whatnot** | No | Chrome automation required | Defer entirely — queue for local execution |
| **9: Photos Archive** | No | Photos.app required | Skip — not applicable outside Mac |

---

## 3. Architecture

### 3.1 Layered Execution Model

```
┌──────────────────────────────────────────────────┐
│  SKILL.md (Claude's Instructions)                │  Layer 1: Skill definition
│  - Phase descriptions, decision matrix           │  (always loaded)
│  - Environment-aware branching rules             │
└──────────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────┐
│  State Machine (item_state.py)                   │  Layer 2: Orchestration
│  - Phase dependencies, transitions               │  (environment-agnostic)
│  - Question queue, decision log                  │
│  Batch Orchestrator (process_batch.py)           │
│  - Multi-item loop, isolation, summary           │
│  Queue Manager (onboarding_queue.py)             │
│  - Centralized status, sync                      │
└──────────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────┐
│  Phase Executors                                 │  Layer 3: Execution
│  ┌─────────────────┐  ┌──────────────────────┐  │  (environment-specific)
│  │ Claude-Executed  │  │ Script-Executed       │  │
│  │ (MCP + osascript │  │ (Python with API     │  │
│  │  when available) │  │  keys when available)│  │
│  └─────────────────┘  └──────────────────────┘  │
│  ┌─────────────────────────────────────────────┐ │
│  │ Deferred Queue (for env-unavailable phases) │ │
│  │ - Captures intent + data                    │ │
│  │ - Executes when capability becomes available│ │
│  └─────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────┘
```

### 3.2 State Architecture (Unchanged from v4.0 — Proven Design)

```
Per-Item State:
  items/RG-XXXX/.state.json
  - Phase statuses, outputs, questions, decisions

Centralized Queue:
  ops/inventory/onboarding-queue.json
  - Dashboard view, batch summaries, blocked items

Deferred Actions (NEW):
  ops/inventory/deferred-actions.json
  - Phase executions that require a different environment
  - Picked up when user returns to a capable environment
```

### 3.3 Deferred Action Model (NEW)

When a phase can't execute in the current environment but the work is well-defined:

```json
{
  "action_id": "def-001",
  "sku": "RG-0015",
  "phase": "phase_8_whatnot",
  "requires": ["chrome_mcp"],
  "payload": {
    "csv_row": "...",
    "category": "Glassware > Vintage",
    "shipping_profile": "Standard"
  },
  "created_at": "2026-02-19T14:30:00Z",
  "created_in": "cowork",
  "status": "pending"
}
```

When user opens Code CLI on Mac: "You have 3 deferred actions from your Cowork session. Run them now?"

---

## 4. Trigger & Intake Mechanisms

### 4.1 Trigger Matrix

| Trigger | Environment | How It Works |
|---------|-------------|-------------|
| **Photos.app polling** | Mac CLI only | `find_product_clusters.py` detects new photo groups in last N days. If new clusters found, prompt: "Found 3 new product photo sets. Onboard?" |
| **User prompt** | All | "onboard these", "new item", "sell this", etc. — existing keyword triggers |
| **Photo dump** | Mac CLI, Cowork | User drops/uploads photos. 1 photo = 1 item. |
| **CLI command** | Mac CLI, Linux CLI | `process_batch.py --photos ...` or `--resume` |
| **Deferred resume** | Mac CLI | On session start, check for deferred actions from cloud/Cowork |

### 4.2 Photos.app Polling (Local Mac Only)

**Concept:** Instead of requiring the user to explicitly drop photos, the agent can proactively discover new product photo clusters.

**Implementation:**

```python
# In SKILL.md startup section:
# "If running on Mac CLI, check for new product photo clusters first"

# Step 1: Run cluster detection
find_product_clusters.py --days 7 --type product --json

# Step 2: Compare against known SKUs (items already onboarded)
# Filter out clusters whose photos are already in RG-XXXX folders

# Step 3: If new clusters found, present to user:
# "I found 3 new product photo sets from the last week:
#   - Cluster A: 4 photos (brass lamp, shot 2 days ago)
#   - Cluster B: 2 photos (ceramic vase, shot yesterday)
#   - Cluster C: 1 photo (vintage book, shot today)
#  Start onboarding? [all / pick / skip]"
```

**Polling is NOT a background daemon.** It runs at conversation start or when the user invokes the skill. "Polling" = checking on each invocation, not a persistent watcher.

### 4.3 Prompt-Based Intake (All Environments)

For Cowork/cloud where Photos.app isn't available:

```
User: "I have 5 new items to onboard"
Claude: "Drop the photos here or describe them. I'll start processing each one."

User: [uploads 5 images]
Claude: Assigns SKUs, starts pipeline for each. Reports progress and questions.
```

For Cowork specifically, the interaction should be **conversational**:
- Progress updates inline with chat
- Questions asked naturally ("This looks like a ceramic vase — am I right?")
- Decisions explained conversationally
- Summary at end with links and deferred actions

---

## 5. Communication Patterns

### 5.1 By Environment

| Environment | Style | Progress | Questions | Summary |
|-------------|-------|----------|-----------|---------|
| **Code CLI** | Structured, phase-by-phase | `[RG-0015] Phase 2 -> DONE` | Batch at end (queue & continue) | Table format |
| **Cowork** | Conversational, inline | "Working on the brass lamp... catalog created, now uploading image..." | Asked inline as they arise | Narrative with links |
| **Cloud** | JSON-structured | Machine-readable events | Queued in state file | JSON summary |

### 5.2 Cowork-Specific Behavior

Cowork is the most interactive environment. The agent should:

1. **Narrate progress** — "I'm looking at your first photo. Looks like a mid-century ceramic planter. Condition seems good — minor glaze crazing but no chips. I'm pricing it at $35 based on comps."
2. **Ask naturally** — "I can't tell from the photo — is this set a matching pair, or two different items?"
3. **Show work** — "Here's what I'm listing on Square: [details]. Sound right?"
4. **Defer gracefully** — "I've done everything I can from here. When you're on your Mac, I'll need to: upload the hero image, push to GitHub Pages, and list on Whatnot. I've saved all the prep work."

### 5.3 Question Priority

Even in autonomous mode, some questions genuinely need human input. Priority levels:

| Priority | Example | Behavior |
|----------|---------|----------|
| **P0: Blocking** | "Can't identify item from photo" | Park immediately, ask user |
| **P1: Important** | "Is this a set or individual items?" | Make best guess, flag for review |
| **P2: Nice-to-have** | "Any provenance or history?" | Skip, proceed with available info |
| **P3: Cosmetic** | "Preferred title wording?" | Agent decides, user reviews post-onboard |

---

## 6. Phase Execution Spec

### 6.0 Environment Probe (NEW — Runs First)

Before any phase executes, detect capabilities:

```
detect_env.py → {
  "environment": "mac_cli",
  "has_osascript": true,
  "has_square_mcp": true,
  "has_chrome_mcp": true,
  "has_photos_db": true,
  "has_git": true,
  "has_removebg": true,
  "interaction_mode": "cli"
}
```

Store result in `.state.json` → `runtime_context`. Phase executors read this to branch.

### 6.1 Phase 0: Image Processing

**Mac CLI:** Full pipeline — Photos.app cluster → copy → compress → remove background
**Cowork:** User uploads image → store in staging → remove background via API (if API key available) → else use raw image
**Cloud:** Image provided via upload → process via API

**Key change:** Background removal uses `image-processor` skill's model routing, which already supports multiple APIs (Nano Banana, Gemini, remove.bg). The portable path uses these APIs directly via `requests`, bypassing osascript.

### 6.2 Phase 1: Appraisal (Fully Portable)

No changes needed. Claude's reasoning works identically in all environments.

### 6.3 Phases 2-3: Catalog + Inventory (Fully Portable)

Square API calls via MCP (`mcp_square_api`) or direct HTTP. Both work in all environments where the token is available.

**Adaptation:** If `has_square_mcp` → use MCP tools. If `has_square_token` but no MCP → use `requests` directly. If neither → defer to state file with full payload for later execution.

### 6.4 Phase 4: Image Upload (Partially Portable)

**Mac CLI:** osascript → `upload_image.py` (current path)
**Other envs:** Direct `requests.post` multipart upload to Square Image API. The `upload_image.py` script's core logic is just a `requests` call — factor it out so it can run without osascript.

### 6.5 Phase 5: Payment Link (Fully Portable)

No changes needed. Square API.

### 6.6 Phase 6: Label (Partially Portable)

**Mac CLI:** Append to local CSV file
**Other envs:** Generate CSV row content, store in `.state.json` outputs. Defer file write.

### 6.7 Phase 7: Publishing (Partially Portable)

**Mac CLI:** Write HTML, update gallery index, git commit & push
**Other envs:**
- Generate HTML content (portable)
- Generate gallery card HTML snippet (portable)
- Store generated content in `.state.json`
- Defer git push (or use GitHub API if available)

**GitHub API alternative:** For Cowork/cloud, could use `gh api` or GitHub's Contents API to commit files directly — no local git needed. This is a stretch goal.

### 6.8 Phase 8: Whatnot (Mac-Only, Defer)

**Mac CLI:** Full Chrome automation via MCP
**Other envs:** Build CSV row + metadata payload, store as deferred action. Execute when Chrome MCP is available.

### 6.9 Phase 9: Photos Archive (Mac-Only, Skip)

**Mac CLI:** Archive to Photos.app albums
**Other envs:** Skip entirely — not applicable. Mark as skipped with reason "Photos.app not available."

---

## 7. Test Strategy

### 7.1 Current State (Broken)

The existing test `test_rg_full_auto_catalog_fallback.py` references the v3.x API:
- `RGItemProcessor(interactive=False)` — `interactive` param removed in v4.0
- `processor.phase3_catalog()` — method renamed to `_phase_2()` in v4.0

These tests must be updated to match the v4.0+ API.

### 7.2 Test Plan

```
testing/
├── unit/
│   ├── test_item_state.py              # State machine transitions
│   ├── test_onboarding_queue.py        # Queue CRUD, sync, question routing
│   ├── test_detect_env.py              # Environment detection
│   └── test_phase_portability.py       # Phase adaptation by environment
├── integration/
│   ├── test_batch_orchestrator.py      # Multi-item processing, isolation
│   ├── test_process_new_item.py        # Single-item pipeline (mocked APIs)
│   ├── test_catalog_fallback.py        # Square API fallback chain (updated)
│   ├── test_deferred_actions.py        # Defer + resume lifecycle
│   └── test_resume_across_sessions.py  # State persistence + resume
└── conftest.py                         # Shared fixtures, mock factories
```

### 7.3 Unit Test Coverage Targets

**item_state.py (State Machine):**
- Phase transitions: pending → in_progress → completed/failed/blocked/skipped
- Dependency resolution: `next_runnable_phase()` respects PHASE_DEPENDENCIES
- Question lifecycle: block → answer → unblock
- Status recalculation: item-level status derived from phase statuses
- Serialization: to_dict() ↔ from_dict() round-trip
- Decision logging: entries accumulate correctly

**onboarding_queue.py (Queue Manager):**
- Upsert: add new, update existing
- Sync: rebuild from .state.json files
- Blocked items report: collects questions across items
- Answer routing: answer reaches correct item + phase

**process_batch.py (Orchestrator):**
- Ingestion: photo list → item states created
- Isolation: one item failure doesn't stop others
- Queue & continue: blocked item parked, others advance
- Resume: previously-blocked items resume when answers provided
- SKU allocation: sequential, no collisions

### 7.4 Integration Test Coverage

**Catalog fallback chain (update existing test):**
- batchInsertObjects fails → upsertCatalogObject succeeds
- Both fail → phase marked FAILED, other phases continue
- ID extraction: from id_mappings, from object traversal

**Deferred actions (new):**
- Phase deferred in Cowork → picked up in Mac CLI
- Multiple deferred actions across items → all executed
- Deferred action fails → error captured, not lost

### 7.5 What We DON'T Test

- Live Square API calls (requires real credentials)
- osascript execution (Mac-only, integration tested manually)
- Chrome MCP automation (requires browser)
- Photos.app access (requires Mac + Full Disk Access)

These are tested via manual E2E runs, not automated tests.

---

## 8. Migration Path

### 8.1 From v4.0 to v5.0

**Non-breaking changes:**
- Add `detect_env.py` script
- Add `deferred_actions.py` module
- Add environment branching in SKILL.md phase instructions
- Update tests to v4.0+ API
- Add new tests

**Breaking changes:**
- `process_new_item.py` phase methods need environment-aware branching
- `process_batch.py` needs to handle deferred phases
- SKILL.md phase instructions need cloud/Cowork paths

### 8.2 Rollout Strategy

1. **Phase A: Fix tests** — Update existing tests to v4.0 API, add unit tests for state machine + queue
2. **Phase B: Add env detection** — `detect_env.py` + runtime_context in state
3. **Phase C: Portable phases** — Add cloud execution paths for phases 1-5
4. **Phase D: Deferred model** — Implement defer/resume for Mac-only phases
5. **Phase E: Cowork communication** — Chat-style interaction for Cowork mode
6. **Phase F: Photos polling** — Auto-detect new photo clusters at skill invocation

Each phase is independently shippable and testable.

---

## 9. File Changes Summary

### New Files
| File | Purpose |
|------|---------|
| `scripts/detect_env.py` | Runtime capability detection |
| `scripts/deferred_actions.py` | Defer/resume module for env-unavailable phases |
| `testing/unit/test_item_state.py` | State machine unit tests |
| `testing/unit/test_onboarding_queue.py` | Queue manager unit tests |
| `testing/unit/test_detect_env.py` | Environment detection tests |
| `testing/integration/test_batch_orchestrator.py` | Batch processing integration tests |
| `testing/integration/test_deferred_actions.py` | Defer/resume integration tests |

### Modified Files
| File | Changes |
|------|---------|
| `SKILL.md` | v5.0 — add environment-aware phase instructions, Cowork communication patterns, Photos polling trigger, deferred actions documentation |
| `scripts/process_new_item.py` | Add env-aware phase branching, portable API paths |
| `scripts/process_batch.py` | Handle deferred phases, env-aware processing |
| `scripts/item_state.py` | Add `runtime_context` field, deferred action tracking |
| `scripts/onboarding_queue.py` | Add deferred actions collection, env field |
| `ARCHITECTURE_AUDIT.md` | Update to v5.0 compliance check |
| `testing/integration/test_rg_full_auto_catalog_fallback.py` | Update to v4.0+ API |

### Unchanged Files
| File | Why |
|------|-----|
| `scripts/remove_background.py` | Already delegates to image-processor |
| `scripts/place_files.py` | Mac-only utility, still needed for Mac path |
| `scripts/sync_to_whatnot.py` | Whatnot-specific, still needed for Mac path |
| `references/*` | Reference material unchanged |

---

## 10. Open Questions

1. **GitHub API for publishing** — Should Phase 7 use the GitHub Contents API as a cloud alternative to git push? This would make publishing fully portable but adds complexity and a new dependency.

2. **Cowork file access** — Can Cowork sessions access uploaded images for Phase 0? Need to verify the `mcp__cowork__request_cowork_directory` capability and its limitations.

3. **API key management in cloud** — How do Square API tokens get to cloud/Cowork environments? MCP server config? Environment variables? Secret injection?

4. **Deferred action notification** — How does the user know there are deferred actions when they open a new Mac CLI session? Hook? Skill startup check? CLAUDE.md instruction?

5. **Windows support** — Is this a real requirement or theoretical? If real, need PowerShell equivalents for osascript patterns and a Windows-native Photos alternative.

6. **Multi-user** — Should state files support multiple users/machines, or is this strictly single-user (scottybe's workflow)?

---

## 11. Success Criteria

| Criteria | Measurement |
|----------|-------------|
| All existing tests pass | `pytest testing/` green |
| New unit tests for state machine + queue | 15+ test cases passing |
| Env detection works in Mac CLI | `detect_env.py` returns correct capabilities |
| Portable phases run in Cowork | Phases 1-5 complete without osascript |
| Deferred actions round-trip | Phase deferred in Cowork, executed on Mac |
| Photos polling discovers clusters | New clusters detected, presented to user |
| Batch isolation maintained | 1 item failure doesn't stop batch of 5 |
| Cowork communication is conversational | Natural language progress, not structured logs |
| Architecture audit score >= 9.0 | Updated ARCHITECTURE_AUDIT.md |

---

## Appendix A: Current v4.0 Test Failures

```python
# test_rg_full_auto_catalog_fallback.py line 38:
processor = RGItemProcessor(interactive=False)
# FAILS: __init__() got unexpected keyword argument 'interactive'
# v4.0 removed interactive param (everything is autonomous now)

# test_rg_full_auto_catalog_fallback.py line 64:
result = processor.phase3_catalog(_item_data())
# FAILS: 'RGItemProcessor' has no attribute 'phase3_catalog'
# v4.0 renamed to _phase_2() with different signature (takes ItemState, not dict)
```

## Appendix B: Environment Detection Pseudocode

```python
def detect_environment() -> dict:
    caps = {}

    # osascript check
    caps["has_osascript"] = shutil.which("osascript") is not None

    # Filesystem check
    caps["has_filesystem"] = os.path.isdir(os.path.expanduser("~/workspace"))

    # Square token
    caps["has_square_token"] = bool(os.environ.get("SQUARE_ACCESS_TOKEN"))

    # Photos.app database
    photos_db = os.path.expanduser(
        "~/Pictures/Photos Library.photoslibrary/database/Photos.sqlite"
    )
    caps["has_photos_db"] = os.path.isfile(photos_db)

    # Git
    caps["has_git"] = shutil.which("git") is not None

    # Image processing APIs
    caps["has_removebg"] = bool(os.environ.get("REMOVEBG_API_KEY"))
    caps["has_image_api"] = caps["has_removebg"] or bool(
        os.environ.get("GEMINI_API_KEY") or os.environ.get("NANO_BANANA_API_KEY")
    )

    # Determine environment
    if caps["has_osascript"] and caps["has_photos_db"]:
        caps["environment"] = "mac_cli"
    elif caps["has_filesystem"] and caps["has_git"]:
        caps["environment"] = "linux_cli"
    elif os.environ.get("CLAUDE_COWORK"):
        caps["environment"] = "cowork"
    else:
        caps["environment"] = "cloud"

    # Interaction mode
    caps["interaction_mode"] = "chat" if caps["environment"] == "cowork" else "cli"

    return caps
```
