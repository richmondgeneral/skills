# Design — Pre-publish Hero QA gate

**Date:** 2026-06-20 · **Author:** Claude Code session · **Status:** approved, pre-implementation
**Source spec:** `ops/docs/HANDOFF-hero-qa-gate.md` (commit `12f3efa`)
**Validated prototype:** `ops/reports/2026-06-20-RG0031-deskew-prototype/` (`flat_hero.py`, 23/23 checks)
**Postmortems:** `ops/reports/2026-06-20-RG0031-hero-rootcause-postmortem.md` (§A2), `ops/reports/2026-06-20-atari-batch-hero-orientation-postmortem.md`

## Problem

Three hero/photo defects shipped live to GitHub Pages + Square in three days because **nothing checks a hero before publish**:
- **RG-0030** — de-stickered in-situ hero (tooling down).
- **RG-0031** — crooked (~16°) Apple Vision cutout shipped tilted + corner-clipped.
- **RG-0036–0051** (Atari batch) — all 16 heroes shipped **rotated 90°** (double rotation: `exif_transpose` + a hardcoded 90°).

Common root gap: no blocking pre-publish hero QA gate. Build it once; it would have caught all three.

## Scope of this pass (decided + revised after verifying the tree)

**Full gate.** Deliver all four handoff acceptance criteria:
1. No item reaches `Listed`/publish without `hero_qa.status=="pass"`.
2. The three historical failure modes (90° rotation, ≥1.5° tilt, clipped face) are each caught by a unit test.
3. Orientation baked once at ingest; no post-`exif_transpose` blind rotation.
4. Both skill copies updated; CLI + `--batch` back-fill works.

**⚠️ Revision (verified 2026-06-20):** the auto-deskew remediation I planned to *defer* is **already landed** in skills `3b72236` (a parallel agent), so it is **out of scope by virtue of being done**, not deferred:
- `image-processor/scripts/deskew.py` — the prototype ported verbatim: `residual_tilt_deg(bgr, alpha=None)`, `deskew_to_face(bgr, ...)`, `detect_face_quad`, `_CV2_OK`.
- `standardize.py` — real `--deskew`/`--perspective-correct`/`--crop-to-face` + `_deskew_flat_goods()` (lazy cv2; routes to manual on low-confidence/non-rectangular/no-cv2).
- `process.py` + `process_group.py` — `analyze_mask_quality` emits `residual_tilt_deg` (the dormant `photo-profiles.json` tilt rule now fires).
- `opencv-python-headless` + `numpy` at `plugins/richmondgeneral/pyproject.toml` + `uv.lock`; cv2 verified 4.13.0, `_CV2_OK True`.

**Consequence for this pass:** do **not** port `flat_hero.py` and do **not** touch `analyze_mask_quality` — **reuse** `deskew.residual_tilt_deg` for the level check. The remaining, genuinely-unbuilt work is the **pre-publish gate** (esp. the **upright/OSD** check — a 90°-rotated hero reads tilt ≈ 0°, so the existing tilt gate does NOT catch the Atari mode), its **blocking integration**, and the **orientation bake-once** fix (verified still absent from `standardize.py`).

## Key facts grounding the design

- **cv2/numpy now resolve** via the plugin-root env: `uv run --project skills/plugins/richmondgeneral` (cv2 4.13.0, `deskew._CV2_OK True`). They are declared in `plugins/richmondgeneral/pyproject.toml` + `uv.lock` (added by `3b72236`). → The gate runs via `uv run --project ${CLAUDE_PLUGIN_ROOT}` (the existing image-processor pattern, SKILL.md), **not** PEP 723 inline deps. **tesseract binary is present** (`/opt/homebrew/bin/tesseract`); add **`pytesseract`** to the plugin-root pyproject. OSD is lazy/guarded (mirrors `deskew._CV2_OK`) so a missing binary/wrapper degrades to the deterministic fallback, never a crash.
- **No code sets `label.json → state="Listed"`** — it is hand-edited. → Enforcement is the standalone CLI gate + a pipeline hook + an `item_state.can_list()` guard, not a single state-setter.
- The `residual_tilt_deg` gate rule in `ops/docs/photo-profiles.json` (`op:"gte"`, 1.5) is now **live** — `analyze_mask_quality` emits the value (`3b72236`). The pre-publish gate's level check is a second, independent enforcement at publish time.
- The prototype's `imgs/` fixtures are **not on disk** → tests self-generate fixtures from real `items/` heroes + deterministic transforms.
- `standardize.py` **never calls `exif_transpose`** at ingest (re-verified post-`3b72236`) → the "bake orientation once" fix is a clean add.

## Architecture & module layout

Engine lives in **image-processor** (image-analysis home, already dual-copied; `residual_tilt_deg` belongs beside the mask gate). cv2/pytesseract isolated to the gate path via inline `uv` deps.

| File | Change | Role |
|---|---|---|
| `image-processor/scripts/deskew.py` | **reuse (no change)** | Already-landed engine. Gate imports `residual_tilt_deg` (and `detect_face_quad` if needed) from here. |
| `image-processor/lib/hero_qa.py` | **new** | `hero_qa_gate(hero_path, original_path=None, item_class=None) -> {status, checks, reasons}` — orchestrates the 5 checks; imports the level check from `deskew.py`. |
| `image-processor/scripts/hero_qa.py` | **new** | Standalone CLI (`uv run --project`): single `hero_qa.py items/RG-XXXX` + `--batch items/` back-fill audit; writes `label.json → hero_qa`. |
| `plugins/richmondgeneral/pyproject.toml` | edit | Add `pytesseract` (cv2/numpy already present). |
| `image-processor/scripts/standardize.py` | edit | Add `bake_orientation()` (exif_transpose once + strip tag) at ingest; assert no second blind rotation. |
| `rg-full-auto/scripts/process_new_item.py`, `process_batch.py` | edit | Call the gate before commit / Square-primary / `state=Listed`; on fail → manual queue, no publish. |
| `rg-full-auto/scripts/item_state.py` | edit | `can_list()` guard — phase_7 (Publishing) refuses without `hero_qa.status=="pass"`. |

Class resolution (cutout vs flat-goods) reuses standardize's `resolve_profile`/`infer_material`; overridable via `item_class`.

## The 5 checks

`hero_qa_gate(...)` returns `status: pass|fail`, per-check values, and human-readable `reasons`.

1. **upright** (hard) — tesseract OSD on the hero; `Rotate ∈ {90,180,270}` above a confidence floor → **fail**. Fallback when OSD has too little text / is unavailable: aspect-ratio vs class expectation + (if `original_path`) source EXIF orientation ≠ 1. Only fails on a *positive* sideways signal — never false-fails on "unknown". **Catches Atari.**
2. **level** (hard) — `flat_hero.residual_tilt_deg()`; `tilt_deg > 1.5` with `confidence ≥ 0.5` → **fail**. Reuses the validated low-confidence guard so irregular items (e.g. the RG-0022 brooch) aren't flagged. **Catches RG-0031 tilt.**
3. **full_face** (hard, class-aware) — cutout class: alpha bbox must clear the border ring (floating, not clipped); touching → **fail**. **Catches RG-0031 corner-clip.** Flat-goods full-bleed: lenient (face *should* reach edges) — relies on level + upright + rect_fill.
4. **bg_ok** (hard, class-aware) — cutout → must be transparent & not a suspicious rect mask; flat-goods → must be opaque full-bleed. Catches wrong-profile output.
5. **defects_ok** (soft) — active only with `original_path`: coarse edge-density retention hero-vs-original; **fail only on extreme** detail-wipe (guards RG-0030 hallucinated-clean). No original → `true`, reason `not_compared`. Never false-fails honest cleanups.

`status="fail"` if any hard check fails. Soft check contributes a reason but only fails on the extreme threshold.

## Data model — `label.json → hero_qa`

```json
"hero_qa": {
  "status": "pass",
  "checked_at": "2026-06-20T..",
  "checker": "auto:hero_qa_gate v1",
  "checks": { "upright": true, "level_deg": 0.4, "full_face": true, "bg_ok": true, "defects_ok": true },
  "reasons": []
}
```

## Blocking behavior (chokepoint)

Three coordinated enforcement points (because `state` is hand-set):
- **(a) Pipeline hook** — `process_new_item.py` / `process_batch.py` call the gate before committing the hero to `items/`, before Square `CreateCatalogImage`/primary, and before any `state → Listed`.
- **(b) State guard** — `item_state.can_list()` blocks phase_7 (Publishing) completion without `hero_qa.status=="pass"`.
- **(c) CLI** — manual re-check + `--batch` back-fill/audit.

On **fail**: write `hero_qa.status="fail"` + `reasons`; set `photo_overrides.status="needs_manual"`; append to `ops/reports/photo-manual-queue.jsonl`; print reasons; **do not publish**. On **pass**: write `hero_qa.status="pass"` and proceed.

## Orientation bake-once fix

Add `bake_orientation(img)` to `standardize.py` ingest: `ImageOps.exif_transpose(img)` once, then drop the EXIF orientation tag, and ensure no second blind rotation exists in the standardize path. Regression test: a synthetic orientation-6 source → output upright + tag stripped. (The Atari double-rotation itself lived in a one-off `_atari_intake/build.py`; the systemic fix is bake-once in the canonical ingest + the gate catching any sideways hero regardless of source.)

## Testing (TDD — tests first)

Self-generated, deterministic fixtures (prototype imgs are gone):
- **straight hero** — from `items/RG-0031/hero.png` (live, fixed straight-on cover).
- **90°-rotated** — `np.rot90` of the straight hero (the Atari mode).
- **16°-tilted** — `rotate_on_canvas(straight, 16)` (the RG-0031 mode); or pull the OLD crooked hero from `items/` git history.
- **corner-clipped cutout** — synthesized RGBA whose subject alpha touches the border.

Cases:
- Unit (gate): straight → pass; 90° → fail(upright); 16° tilt → fail(level); corner-clip cutout → fail(full_face).
- Orientation regression: synthetic EXIF-orientation-6 source → standardize output upright + tag stripped.
- Integration: `process_batch` on a bad-hero fixture → never reaches `Listed`, lands in manual queue, reasons printed.
- Reuse guard: a thin test asserting `deskew.residual_tilt_deg` still returns the expected shape on a known-tilt fixture (the engine is `3b72236`'s code; we depend on its API, so pin it).

## Dual-copy & rollout

Implement in source `skills/plugins/richmondgeneral/skills/{image-processor,rg-full-auto}/`, then `rsync -a --exclude=__pycache__` each to `~/.claude/plugins/cache/richmondgeneral/skills/...`. `ops/docs/photo-profiles.json` is single-copy (already carries the tilt rule). Run `hero_qa.py --batch items/` after landing to audit the existing catalog and report any currently-`Listed` items that would fail (back-fill `hero_qa`).
