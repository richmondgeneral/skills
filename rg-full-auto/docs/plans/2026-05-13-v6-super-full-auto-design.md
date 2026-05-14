# rg-full-auto v6.0 — "Super Full Auto" design

**Date:** 2026-05-13
**Status:** Approved direction, implementation plan pending
**Owner:** @scottybe
**Related branch (preserved, NOT being merged as-is):** `claude/refactor-auto-onboarding-TyZdT`
**Related PRD:** branch's `PRD.md` (560L) — moves into this skill as
`docs/plans/2026-05-13-v5-portability.md`, deferred future-work, NOT shipping in v6.0

## Context

Three sources are being combined:

1. **Current `main`** — `rg-full-auto` v3.7. Interactive, single-item, supervised.
   Includes recent fixes (PR sequence ending 2026-05-13): `description_html`
   field, phase ordering (photography before research), `ROOM_BY_TYPE` map
   with `TOP_LEVEL_ROOMS` handling, sync_to_whatnot literal-`\n` fix,
   remove_background response.text leak fix.
2. **Branch v4.0 (committed Feb 19, 2026)** — batch-first, autonomous,
   fault-isolated, per-item state machine, centralized queue, async
   question queue. Working code: `item_state.py` (394L),
   `onboarding_queue.py` (303L), `process_batch.py` (568L), modified
   `process_new_item.py` (842L), modified `SKILL.md` (1022L).
3. **Branch v5.0 PRD (draft, 560L)** — environment-aware capability
   detection, phase portability classification, deferred-action queue
   for phases that need a different environment. **Deferred to a future
   v6.1+ epic; not part of v6.0 scope.**

v6.0 = v3.7's stable + v4.0's autonomy and infrastructure + audit
trail. v5.0 portability is the next epic after v6.0 stabilizes.

## Decisions taken

| Dimension | Choice | Rejected |
|---|---|---|
| Autonomy level | **A: Full v4.0 autonomy.** Agent decides everything (price, condition, shipping, category, draft copy). User reviews post-onboard. | B (milestone checkpoints), C (preserve v3.7 gates with v4.0 engine) |
| Skill identity | **Major version bump on `rg-full-auto` → v6.0.** "Super" is branding inside the SKILL.md header. Path stays `rg-full-auto/`. | New parallel skill (cross-reference churn), new skill replacing old (same churn) |
| Audit depth | **L1 (passive structured log) + L2 (time-on-review tracking)** in v6.0. L3 (pattern-detection feedback loop) deferred to v6.1+ when ≥30 items' correction data exists to learn from. | L1 only (no time data), L1+L2+L3 (premature without data) |

## Architecture — three layers

```
LAYER 1 — SKILL.md
  Claude's instructions. Phase descriptions, autonomous decision rules,
  audit-and-review review flow. Bumped from v3.7 to v6.0.
                            │
                            ▼
LAYER 2 — Orchestration (Python, env-agnostic)
  item_state.py       — per-item FSM, persisted to .state.json
  onboarding_queue.py — centralized dashboard, ops/inventory/queue.json
  process_batch.py    — multi-item loop, fault isolation, summary
  audit_log.py (NEW)  — writes decisions.jsonl, corrections.jsonl,
                        review_log.jsonl; provides report/review-stats/drift
                            │
                            ▼
LAYER 3 — Phase executors
  process_new_item.py — single-item phase runner. CURRENT MAIN's version
                        (with recent fixes intact) is the base. v4.0's
                        state-machine integration is lifted ONTO it via
                        thin hooks, NOT vice versa. Branch's rewrite of
                        this file is discarded.
  Phase implementations subprocess into sibling skills:
  square-image-upload, photos-library, rg-lot-tracker, book-appraiser, etc.
```

**Key choice rationale:** current main's `process_new_item.py` has 3 months
of bugfixes that the branch's version does not. Re-applying those fixes
onto the branch's rewrite is more work and more risk than wrapping
main's version with state-machine hooks.

## Component inventory — what comes from where

| File | Source | Status |
|---|---|---|
| `SKILL.md` | Branch v4.0 (25 KB) + main's reference structure | Rewrite — ~600L target, down from branch's 1022L by trimming repetition |
| `scripts/process_new_item.py` | **Current main** (recent fixes intact) | Wrap with state-machine hooks; logic unchanged |
| `scripts/process_batch.py` | Branch v4.0 verbatim | Drop in — calls `process_new_item.py` per item |
| `scripts/item_state.py` | Branch v4.0 verbatim | Drop in — adds `corrections[]` field for L1 |
| `scripts/onboarding_queue.py` | Branch v4.0 verbatim | Drop in |
| `scripts/audit_log.py` | **NEW** | Centralized writer for the three JSONL audit files + CLI subcommands |
| `scripts/place_files.py` | Current main verbatim | Keep |
| `scripts/remove_background.py` | Current main verbatim | Keep (already has response.text leak fix) |
| `scripts/sync_to_whatnot.py` | Current main verbatim | Keep (already has literal-`\n` fix + Path.home() default) |
| `references/*.md` | Current main (all 11) | Keep. Branch dropped 5; restore them all |
| `CHANGELOG.md` | Current main + v6.0 entry | Append |
| `ARCHITECTURE_AUDIT.md` | Current main (already has ARCHIVED banner) | No change |
| `docs/plans/2026-05-13-v5-portability.md` | **MOVED from branch's `PRD.md`** | Repositioned as deferred future-work artifact, NOT a runtime skill file |

**Deliberately discarded:** branch's `process_new_item.py` (842L
rewrite). Re-applying main's 3 months of fixes onto it is more work
than the inverse.

**Deliberately removed in v6.0:** v3.7's `prompt()` and `confirm()`
user-checkpoint patterns. Kept callable behind `--interactive` flag for
backward compatibility; default path is autonomous.

## Data flow — single item

```
photo intake → cluster detect (Mac only) → SKU allocate → state.json init
   ↓
phase_0: bg removal (autonomous)
   ↓ [decision: model choice — best result by confidence]      → audit_log
phase_1: appraisal (autonomous; needs Claude visual analysis)
   ↓ [decisions: era, condition, price, shipping_eligible]     → audit_log
phase_2: catalog draft (autonomous)
   ↓ [decisions: type_category_id, tier_category_id]           → audit_log
   ↓ [uses main's description_html + ROOM_BY_TYPE fixes]
phase_3: inventory set
   ↓
phase_4: image upload (autonomous; subprocess square-image-upload)
   ↓ FIRST IRREVERSIBLE WRITE to Square — corrections from here onward
   ↓ matter more; audit_log captures with higher detail
phase_5: payment link
   ↓
phase_6: label CSV row
   ↓
phase_7: GitHub Pages info card draft + push
   ↓
phase_8: Whatnot CSV row
   ↓
phase_9: Photos archive (Mac only; deferred in non-Mac env later via v5.0)
   ↓
state.status = "completed" → queue summary updated → user notified
```

**Failure on any phase:** item state → `BLOCKED`, queue updated with
the question, batch continues with other items. Async question queue
(v4.0 design preserved).

## Audit trail schemas

Four data artifacts, all written by `audit_log.py`. JSONL for streams;
JSON for per-item state.

### Per-item state — `items/RG-XXXX/.state.json`

```json
{
  "sku": "RG-0042",
  "status": "completed",
  "source_image": "/Users/scottybe/Pictures/.../IMG_4231.heic",
  "created_at": "2026-05-13T18:00:00Z",
  "updated_at": "2026-05-13T18:04:22Z",
  "created_in": "mac_cli",
  "phases": {
    "phase_0": {
      "status": "completed",
      "started_at": "...",
      "completed_at": "...",
      "duration_s": 12.3,
      "outputs": {"hero_path": "...", "model_used": "removebg"}
    },
    "phase_1": {
      "status": "completed",
      "outputs": {
        "title": "...",
        "era": "...",
        "price": 18.50,
        "condition": "Very Good"
      }
    }
  },
  "decisions": [
    {
      "id": "dec-001",
      "phase": "phase_1",
      "type": "price",
      "made_at": "2026-05-13T18:01:15Z",
      "inputs_considered": {
        "visible_condition": ["minor edge wear", "yellowing"],
        "era": "1979",
        "comparable_count_consulted": 5,
        "comparable_price_range": [12, 28],
        "lot_allocated_cost": 4.50
      },
      "choice": 18.50,
      "alternatives_seen": [
        {"value": 22.00, "rejected_reason": "above mid-range comps"},
        {"value": 15.00, "rejected_reason": "under 4x markup"}
      ],
      "confidence": 0.78,
      "rationale": "Mid-range comp anchor (~$20). Pulled to $18.50 on condition discount."
    }
  ],
  "questions": [],
  "review": {
    "agent_finished_at": "2026-05-13T18:04:22Z",
    "human_reviewed_at": null,
    "elapsed_review_s": null,
    "outcome": null
  }
}
```

`questions[]` carries the v4.0 async-question payloads (item parked, batch continues).

### Decisions stream — `ops/inventory/decisions.jsonl`

One line per autonomous decision, appended in real time. JSONL not
JSON: append-only, no full-file rewrite, easy to `grep`/`jq`. This is
the file L3 (deferred) will consume for pattern detection.

```jsonl
{"ts":"2026-05-13T18:01:15Z","sku":"RG-0042","phase":"phase_1","type":"price","choice":18.50,"confidence":0.78,...}
{"ts":"2026-05-13T18:01:18Z","sku":"RG-0042","phase":"phase_1","type":"condition","choice":"Very Good","confidence":0.85,...}
{"ts":"2026-05-13T18:02:01Z","sku":"RG-0042","phase":"phase_2","type":"type_category","choice":"CLZCJ62H4TTHDQ3ZBYMZQASQ","choice_name":"Books & Paper","confidence":0.95,...}
```

### Corrections stream — `ops/inventory/corrections.jsonl`

Appended when you (or whoever reviews) edit anything the agent decided.
Two write paths:

- **Manual:** `audit_log.py correct --sku RG-0042 --decision dec-001 --new 22.00 --reason "underpriced for the condition"`
- **Auto-detected:** when `process_new_item.py --review-mode` runs, it
  diffs the current item state (label.json, Square catalog, GitHub
  Pages card) against `decisions.jsonl` for that SKU and writes
  corrections for anything that drifted.

```jsonl
{"ts":"2026-05-13T19:32:00Z","sku":"RG-0042","decision_id":"dec-001","decision_type":"price","agent_choice":18.50,"corrected_to":22.00,"correction_source":"manual","reason":"underpriced for the condition","reviewer":"scottybe"}
{"ts":"2026-05-13T19:32:05Z","sku":"RG-0042","decision_id":"dec-007","decision_type":"shipping_eligible","agent_choice":true,"corrected_to":false,"correction_source":"auto-diff","reason":"label.json shippable=false","reviewer":"scottybe"}
```

This is the input to L3 (deferred). The data we collect now is what
makes L3 worth building later.

### Review timing stream — `ops/inventory/review_log.jsonl`

L2 layer — answers "improve our time with those issues."

```jsonl
{"ts":"2026-05-13T19:32:00Z","sku":"RG-0042","event":"review_started"}
{"ts":"2026-05-13T19:37:24Z","sku":"RG-0042","event":"review_completed","duration_s":324,"corrections_applied":2,"outcome":"accepted_with_corrections"}
```

Three terminal outcomes: `accepted_as_is`, `accepted_with_corrections`,
`rejected_redo`.

Over time, you get data like:

- *"Books take 4min to review, ceramics take 11min"*
- *"Pricing corrections account for 60% of review time on furniture"*
- *"v3.7 phase-by-phase took avg 12min total per item; v6.0 autonomous + review takes avg 7min"*

L2 doesn't analyze any of this. It just collects. The analysis tool
(L3) reads them later.

## Tooling enabled by audit data

Without L3 yet, even L1+L2 give you:

```
audit_log.py report --sku RG-0042
audit_log.py report --since 2026-05-01
audit_log.py review-stats
audit_log.py drift                      # decisions where agent's
                                        # choice doesn't match current
                                        # Square state — auto-correction
                                        # candidates
```

## Size estimate

`decisions.jsonl` accumulates ~8 decisions/item × ~30 items/month ≈ 240
lines/month. ~30 KB/year. Not a concern. JSONL files live in
`ops/inventory/` (private ops repo, not public items repo).

## Migration — 3 PRs, not one

| PR | Scope | Behavior change | Risk |
|---|---|---|---|
| **#1 — Infra only** | Land `item_state.py`, `onboarding_queue.py`, `audit_log.py` + the JSONL log initialization. `process_new_item.py` gains optional state-machine hooks but defaults to v3.7 interactive behavior. | None visible | Low — code paths added, not activated |
| **#2 — Orchestrator + autonomous mode behind a flag** | Land `process_batch.py`. Add `--autonomous` flag to `process_new_item.py`. Run real items through it with the flag on to validate. SKILL.md still says "v3.7 interactive default" but documents the new mode. | Opt-in autonomous via flag | Medium — first real autonomous runs; mistakes captured in audit log + corrections |
| **#3 — Flip the default** | SKILL.md bumps to v6.0, autonomous becomes default, audit-and-review flow becomes documented norm. `--interactive` kept as opt-out. | Default-on autonomous | High — de-risked by data from PR #2 |

**Backward compatibility guarantees:**

- Skill name stays `rg-full-auto` → cross-references in BRAND.md,
  items/CLAUDE.md, brand design docs, Linear issues all keep working.
- Existing items without `.state.json` → treated as "completed in
  legacy mode." v6.0 never re-processes them.
- Other skills that subprocess `process_new_item.py` → CLI surface
  compatible. `--interactive` opt-out preserves v3.7 behavior.

## Test strategy

PRD §7 noted existing tests are broken
(`test_rg_full_auto_catalog_fallback.py` references v3.x API). v6.0
ships with a fresh test layer.

| PR | Required tests (must pass before merge) |
|---|---|
| #1 (infra) | Unit: `item_state.py` state transitions; `onboarding_queue.py` queue add/remove/update; `audit_log.py` JSONL append atomicity (concurrent-write safety) |
| #2 (orchestrator + flag) | Integration: `process_batch.py` on a fixture item (mocked Square API + mocked remove.bg). One real-item smoke run with `--autonomous` flag, hand-verified, audit-log inspected. |
| #3 (default flip) | Regression diff: same input photo → v6.0 autonomous output vs v3.7 interactive output → compare Square catalog payload structurally. Differences must be intentional (e.g., `description_html` now, was `description` in v3.x). |

**New test fixtures:**

- `tests/fixtures/sample-photo.heic` — Photos-clustered candidate
- `tests/fixtures/sample-label.json` — expected output shape
- `tests/fixtures/sample-comps.json` — mock comparable sales data
- Mock Square API responses for `batchInsertObjects`, inventory
  `batchChange`, payment link create
- Mock remove.bg API response

**Deliberately not tested:**

- Actual Square API calls (mock everything; no live test account writes)
- Actual Photos.app integration (mock cluster detection output)
- Visual correctness of generated HTML (Playwright UI tests in items/
  repo already cover the rendered card)

## Open questions / deferred

- L3 pattern-detection layer — needs ≥30 items' correction data before
  it'd produce useful patterns. Build after v6.0 has been live for
  ~1 month.
- The held branch's v5.0 portability PRD (`docs/plans/2026-05-13-v5-portability.md`)
  — environment detection, capability matrix, deferred-action queue
  for cross-environment phases. Next epic after v6.0 stabilizes.
- Behavior on partially-completed items: should v6.0 detect that an
  item has Square catalog entries but no `.state.json` and
  reconstruct partial state? Or treat as completed-in-legacy-mode?
  Lean toward legacy-mode, but worth confirming during PR #1.
- Concurrency model: parallelism within a batch (multiple items
  processed concurrently) is in the v4.0 design but not strictly
  required for v6.0 ship. Could ship sequential first, parallel later.

## Out of scope for v6.0

- **v5.0 portability** — environment detection, capability matrix,
  deferred-action queue. Lives in `docs/plans/2026-05-13-v5-portability.md`
  as the next epic.
- **Multi-machine batches** — running one batch across Mac + cloud +
  cowork in parallel. Tied to v5.0.
- **L3 pattern-detection feedback loop** — deferred until data exists.
- **Visual aesthetic changes** to item cards — that's TVM-196's lane
  (iridescent treatment); orthogonal to this work.

## References

- Held branch: `origin/claude/refactor-auto-onboarding-TyZdT` on
  `richmondgeneral/skills`
- Branch PRD (v5.0): being moved to
  `rg-full-auto/docs/plans/2026-05-13-v5-portability.md`
- Current v3.7 SKILL.md (the base for the rewrite)
- BRAND.md (cross-references rg-full-auto for new-item workflow)
- items/CLAUDE.md (documents the rg-full-auto workflow for the items
  repo's perspective)
