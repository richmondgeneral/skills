# Phase 2a — Instance-config seam + secret-resolver + public/private boundary spec

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Introduce the **instance-config seam** (the framework-vs-instance boundary, per the monorepo design) without any disruptive repo reorg or touching actively-edited intake code. Centralize the Square token resolution (env→Keychain→.env — also closes follow-up #32) and the per-instance constants (location/merchant/pages/items_dir) into one self-contained module the `item_model` system adopts as the proving ground. Write the public/private boundary spec (concept-first).

**Architecture:** A small, self-contained `item_model/instance.py` — no cross-skill runtime deps. `resolve_square_token()` mirrors the `image-processor/lib/env.py` order (existing env → macOS Keychain → workspace `.env`) so the write-path `--apply` works even over the osascript bridge (bare non-login shell). `load_instance_config()` reads per-instance constants from env with RG defaults, so the framework is genericizable (another Square merchant overrides via env) while RG works out of the box. The item_model system (already seam-ready — reads env) adopts both. NO physical repo move, NO older-skill migration (deferred — they overlap active intake).

**Tech Stack:** Python 3.11+ via `uv`; pytest. Self-contained in `item-model-core/lib/item_model/`.
**Working dir:** `/Users/scottybe/workspace/richmondgeneral/skills` (execution in a worktree).
**Test runner:** `uv run --project plugins/richmondgeneral --extra dev pytest <path> -q`

---

## Task P2-T1: `instance.py` — secret resolver + instance config

**Files:** Create `item_model/instance.py`; Test `testing/unit/test_item_model_instance.py`.

**Behavior:**
- `resolve_square_token() -> str | None`: order = `os.environ["SQUARE_ACCESS_TOKEN"]` → `os.environ["SQUARE_TOKEN"]` → macOS Keychain generic password `SQUARE_ACCESS_TOKEN` → workspace `.env` (`/Users/scottybe/workspace/richmondgeneral/.env`, parse `KEY=VALUE`). Returns the first hit, else None. Keychain + .env reads must be isolated so tests can monkeypatch them (factor `_from_keychain(name)` and `_from_dotenv(name)` helpers like `image-processor/lib/env.py`).
- `@dataclass(frozen=True) InstanceConfig`: `location_id: str`, `merchant_id: str`, `pages_base: str`, `items_dir: str`.
- `load_instance_config() -> InstanceConfig`: read from env with RG defaults — `SQUARE_LOCATION_ID` (default `"B87BAEZ0NWV34"`), `SQUARE_MERCHANT_ID` (default `"7MM9AFJAD0XHW"`), `RG_PAGES_BASE` (default `"https://richmondgeneral.github.io/items"`), `RG_ITEMS_DIR` (default `str(Path.home()/"workspace"/"richmondgeneral"/"items")`).

**Tests (monkeypatch-based, no real Keychain/network):**
- `resolve_square_token`: env SQUARE_ACCESS_TOKEN wins; falls back to SQUARE_TOKEN; with both unset, falls through to a monkeypatched `_from_keychain`; then to a monkeypatched `_from_dotenv`; returns None when all empty.
- `load_instance_config`: defaults when env unset (assert RG values); env overrides win (set SQUARE_LOCATION_ID/RG_ITEMS_DIR → reflected). Use monkeypatch.setenv/delenv.

Commit.

---

## Task P2-T2: adopt the seam in the item_model system (+ close #32)

Make the item_model write/read edges resolve token + location through `instance.py`. This is low-collision (item_model system is mine, already env-based).

**Files:** modify `item_model/channels/square_reader.py`, `rg-reconcile/scripts/set_price.py`, `rg-reconcile/scripts/reconcile.py`. Tests: extend where pure.

- `square_reader.build_square_index`: replace the inline `os.environ.get("SQUARE_ACCESS_TOKEN") or ...` with `resolve_square_token()`, and default `location_id` from `load_instance_config().location_id` (keep the explicit-arg override). Lazy-import `instance` so the pure `observe_square` path stays import-light.
- `set_price.py` `apply_set_price` (the `--apply` branch): build the Square client from `resolve_square_token()` instead of bare env — **this closes #32** (token now resolves over the bridge). Keep the live-edge gating (only under `apply=True`); the resolver import stays inside the `apply` branch.
- `reconcile.py` + `set_price.py`: `--items-dir` default uses `load_instance_config().items_dir`.

**Tests:** keep the existing dry-run safety test green (set_price apply=False still does no Square/import). Add a unit test that `resolve_square_token()` is what `--apply` would use (e.g., monkeypatch env → assert the resolver returns it) — without calling live Square. Verify the full suite stays green.

Commit. (Mark follow-up #32 resolved.)

---

## Task P2-T3: public/private boundary spec + verify

**Files:** Create `docs/plans/2026-06-19-public-private-boundary.md`; modify the monorepo design doc §2/§5 to point at it.

**Spec content (concept-first — NO files moved):**
- **Framework (public, open-by-default):** the `item_model` core, reconcile/write-path, channel adapters, the generic skills, templates, docs, architecture. No real data, no secrets. Genericizable via `instance_config` (env overrides) + `resolve_square_token()`.
- **Instance (private):** real item data/content, `ops/` finances + ROI, contacts/CRM, real-estate & personal, secrets (`.env`/Keychain). The eventual `.instance/` home.
- **The seam:** `instance.py` is the single point where the framework reads per-instance config + secrets; everything else stays instance-agnostic. Lists the remaining hardcoded touchpoints to migrate later (the 28× `B87BAEZ0NWV34`, pages-base, paths in the older skills — deferred, they overlap active intake).
- **Licensing posture:** open-by-default; MIT/Apache-2.0 on the genuinely-reusable pieces; `CONTRIBUTING.md` "not accepting contributions until released + stable." Progress = résumé. NOT a turnkey product.
- **Deferred:** physical repo reorg (core/domains/capabilities/.instance), older-skill instance-config migration, the `.instance` private split, actual LICENSE/CONTRIBUTING files.

**Verify:** full unit suite green; live read-only smoke still 0 findings (confirm the resolver/config adoption didn't change behavior). Commit.

---

## Done criteria
- `resolve_square_token()` (env→Keychain→.env) + `load_instance_config()` exist, tested.
- item_model system (square_reader, set_price `--apply`, reconcile/set_price items_dir) routes token + instance constants through the seam; **#32 closed**.
- Public/private boundary spec written; design doc points to it.
- Full suite green; live smoke still 0 findings; no repo reorg, no intake-code changes.

## Deferred (later Phase 2)
- Physical reorg into core/domains/capabilities/.instance (§6); migrate the older skills' 28× hardcoded `B87BAEZ0NWV34` / pages-base / paths onto the seam (overlaps active intake — time it carefully); create `.instance` + LICENSE + CONTRIBUTING.
