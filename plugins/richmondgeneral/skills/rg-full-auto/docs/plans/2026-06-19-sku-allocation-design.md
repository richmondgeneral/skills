# RG-XXXX SKU Allocation — Design

**Date:** 2026-06-19
**Status:** Approved (brainstorm) → ready for implementation plan
**Skill:** `rg-full-auto` (Phase 0, SKU minting)

## Problem

SKU "truth" for `RG-XXXX` is split across ≥4 sources that disagree, and the
current allocator has no concurrency control:

- **Filesystem** (`richmondgeneral/items/`) — the old allocator
  (`process_batch.py::_default_next_sku`) globs this dir for `max(RG-*) + 1`.
- **Square cache** (local Mongo) — lags; was observed **2 behind** (knew up to
  RG-0027 while the filesystem had RG-0029).
- **Live Square API** — the declared source of truth, not consulted at mint time.
- **CLAUDE.md notes** — hand-maintained, also behind.

The allocator is a read-then-write with no lock — a classic TOCTOU race.
This was observed **live**: during the session that produced this design, a
concurrent writer minted **RG-0030** between our observation (max was RG-0029)
and our intended use of RG-0030. Writers are **multi-machine and independent**
(Claude Code on the Mac, Cowork via the osascript bridge, and cloud workers),
so no filesystem-local lock can fix it.

A related defect surfaced while investigating: the **installed plugin cache was
stale** relative to the `skills` source repo — the cache's `DEFAULT_ITEMS_DIR`
still pointed at the long-dead `/Users/scottybe/workspace/square/items`, while
source already had the correct `richmondgeneral/items`. The cache was patched to
match source; the durable fix is rebuilding the plugin from source.

## Requirements (decided during brainstorm)

1. **Multi-machine safe** — independent writers that don't share a filesystem
   must never collide. → a single networked allocation authority.
2. **Unique only; gaps are fine** — a reserved-then-abandoned number may be
   burned forever. → the authority can be a monotonic counter with no
   reservation-reclaim logic.
3. **Reuse existing reachable infra; no new services.**
4. **Low volume** — 1–2 items at a time, well under 100/day. Contention is
   effectively nil; the design optimizes for simplicity, not throughput.

## Decision: Square is the allocation authority

Square is already the declared source of truth and is reachable from every
writer. The risk with "Square as authority" is that Square has no native atomic
counter and does **not** enforce SKU uniqueness — naively this forces a flaky
"create-then-search-for-duplicates" emulation over eventually-consistent reads.

**That risk is eliminated by Square's catalog object versioning**, which is a
real compare-and-set primitive. From the Square API type info for
`CatalogObject.version`:

> "The version of the object. When updating an object, the version supplied must
> match the version in the database, otherwise the write will be rejected as
> conflicting."

So a single catalog object can serve as an atomic counter via version-CAS.

### Considered and rejected

- **GitHub ref as authority** (atomic via push compare-and-swap) — viable and
  reachable everywhere, but adds a git dependency on every writer and a second
  source of truth alongside Square.
- **Dedicated atomic-counter service** (serverless + Mongo Atlas `$inc` / Redis
  `INCR`) — textbook-correct but new infrastructure to deploy, secure, monitor,
  and keep up before any intake; no serverless platform exists today.

## Architecture & core mechanism

**One hidden sentinel `CatalogItem`** (`__RG_SKU_COUNTER__`,
`present_at_all_locations=false`, no location IDs → never appears in POS or
storefront) holds the last-allocated integer **N** in its `name` field, encoded
as `RG-SKU-COUNTER:NNNN`. The encoding deliberately does **not** match the
`RG-####` *variation SKU* pattern, so the counter never pollutes a max-scan.

> Chosen over a Square *custom attribute* (semantically cleaner but needs a
> one-time `CustomAttributeDefinition` to bootstrap) for zero ceremony — one
> field to read and CAS-update, visible in the dashboard for debugging.

**Allocation = reconcile-then-CAS-increment** (the same code on every machine):

```
allocate_sku(square_client) -> "RG-XXXX":
  for attempt in 1..MAX_RETRIES:
    obj, V = retrieve(__RG_SKU_COUNTER__)              # read N + its version
    N_eff  = max(parse_name(obj), scan_square_RG_max())# forward-only reconcile
    candidate = N_eff + 1
    try:
      batchUpdateObjects(counter, name=f"RG-SKU-COUNTER:{candidate:04d}",
                         version=V, idempotency_key=fresh())   # CAS
      return f"RG-{candidate:04d}"                     # exactly one winner per N→N+1
    except VersionConflict:
      backoff_jitter(attempt); continue               # lost the race; re-read & retry
  raise SkuAllocationError                             # bounded; never silently proceed
```

Because Square rejects any update whose `version` is stale, **exactly one writer
wins each increment** — no duplicates across concurrent machines, and the claim
does not depend on eventually-consistent SKU *search*. The reconcile step
(`max(N, live-Square RG max)`) runs **just before each allocate** (chosen over a
scheduled sweep) and only ever moves the counter forward, so a rare hand-add in
the Square dashboard can't cause a later collision. Gaps are acceptable, so an
abandoned intake simply burns a number.

The filesystem glob (`_default_next_sku`) is **demoted** from allocator to one
input of `bootstrap()` only.

## Components & data flow

**New module `sku_authority.py`** (in `rg-full-auto/scripts/`, importable by all
scripts). Public API:

- `allocate_sku(square_client) -> "RG-XXXX"` — the only way to mint; returns a
  number already reserved on Square.
- `bootstrap(square_client)` — idempotent; creates the sentinel if missing,
  initializes `N = max(Square RG max, local FS RG max)`.
- `peek(square_client) -> int` — read N without incrementing (status/debug).

**Call-site changes** (removing the old collision sources):

- `process_batch.py::_default_next_sku()` → thin wrapper over `allocate_sku()`;
  the FS glob no longer allocates.
- `process_new_item.py` `Path('.').glob('RG-*')` → removed; routes through the
  authority (also kills its CWD-relative scan bug).
- `SKILL.md` Phase 0 Step 0.1/0.2 ("get next SKU from cache" → "verify not
  taken") → replaced by a single "call `allocate_sku()`; it returns an
  already-reserved SKU." **The Square cache exits the allocation path entirely**
  (it remains a fast read layer elsewhere).

**Data flow for one mint (Phase 0):**

1. Writer (any machine) calls `allocate_sku()`.
2. Retrieve sentinel `(N, V)` + scan Square RG max → `candidate`.
3. CAS-update sentinel to `candidate` at version `V` → win: return `RG-XXXX`;
   conflict: retry.
4. Writer creates `items/RG-XXXX/` locally and proceeds; Phase 2 creates the
   real catalog item with that SKU. The counter increment and item creation are
   decoupled — a crash after step 3 burns the number (gap, acceptable).

## Error handling & edge cases

- **Square unreachable / auth failure** → `allocate_sku()` raises
  `SkuAllocationError`; the intake **hard-stops before creating anything**. No
  silent fallback to a local glob — that fallback *was* the collision bug. Not a
  new dependency: Phase 2 needs Square regardless.
- **Version conflict** → expected under (rare) concurrency; bounded retries with
  jittered backoff. At <100/day this effectively never passes attempt 1.
- **Sentinel missing/deleted** → `allocate_sku()` auto-calls `bootstrap()`
  (recreate from `max(Square, FS)`), then proceeds. Self-healing.
- **Out-of-band dashboard add** (a human types an `RG-####` SKU in Square) → the
  just-before-allocate reconcile catches it on the next mint. **Residual risk:**
  Square search is eventually consistent, so a seconds-old hand-add could be
  missed once → a rare collision. Documented and accepted given hand-adds are
  rare and gaps are fine; if airtightness is ever needed, route hand-adds
  through `allocate_sku()` too.
- **Idempotency** → each CAS update carries a fresh idempotency key, so a network
  retry won't double-increment, while a stale `version` is rejected → double
  safety.
- **FS↔Square divergence** (the original bug class) → eliminated for allocation:
  the FS is no longer authoritative; the Square counter is. The FS glob only
  feeds `bootstrap()`.

## Testing

- **Unit (mock Square client):** clean path returns `N+1`; version-conflict →
  retry → success with the newer N; reconcile picks `square_max+1` when ahead and
  never goes backward; sentinel-missing → bootstrap path; retries exhausted →
  raises (never silently proceeds).
- **Concurrency sim:** in-memory fake Square enforcing version-CAS; fire ~20
  concurrent `allocate_sku()` → assert all SKUs unique.
- **Idempotency:** replaying a CAS update with the same idempotency key does not
  double-increment.
- **Integration (Square sandbox):** two processes allocate in a loop → zero
  duplicates; confirm the sentinel is hidden from all locations.
- **Migration check:** `bootstrap()` against today's state sets `N=30`
  (RG-0030 exists) → first `allocate_sku()` returns **RG-0031**.

## Rollout / migration

1. Land `sku_authority.py` and the call-site changes in the **`skills` source
   repo** (`plugins/richmondgeneral/skills/rg-full-auto/`).
2. Run `bootstrap()` once → sentinel created at `N = 30` (current max).
3. Swap allocator call sites to `allocate_sku()`; update `SKILL.md` Phase 0.
4. **Rebuild/reinstall the plugin from source** so the executing cache matches
   source (this is also the durable fix for the stale-cache `DEFAULT_ITEMS_DIR`
   issue found alongside this work).

## Open / deferred

- Whether to eventually route Square-dashboard hand-adds through the authority to
  close the eventual-consistency residual (only if hand-adds become common).
- Counter encoding could migrate from `name` to a typed custom attribute later
  without changing the allocation contract.
