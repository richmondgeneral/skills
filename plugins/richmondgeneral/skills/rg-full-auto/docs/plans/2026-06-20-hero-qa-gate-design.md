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

## Scope of this pass (decided)

**Full gate, defer auto-deskew remediation.** Deliver all four handoff acceptance criteria:
1. No item reaches `Listed`/publish without `hero_qa.status=="pass"`.
2. The three historical failure modes (90° rotation, ≥1.5° tilt, clipped face) are each caught by a unit test.
3. Orientation baked once at ingest; no post-`exif_transpose` blind rotation.
4. Both skill copies updated; CLI + `--batch` back-fill works.

**Deferred** (separate task per handoff): the auto-deskew *remediation* — implementing `--deskew`/`--perspective-correct`/`--crop-to-face` so `standardize.py` actually transforms a tilted hero — and wiring `residual_tilt_deg` into `analyze_mask_quality`. The gate's level-check covers tilt at the publish chokepoint in the meantime. (The validated geometry is ported in `flat_hero.py` regardless, so the remediation is a small follow-on.)

## Key facts grounding the design

- **cv2 is not installed** in any local env, but `uv run --with opencv-python-headless` resolves it on demand (4.13.0 confirmed). **tesseract binary is present** (`/opt/homebrew/bin/tesseract`); `pytesseract` is not (addable via uv). → cv2/pytesseract come from **PEP 723 inline deps** on the gate scripts; the Pillow-only env that `process.py` runs in is untouched.
- **No code sets `label.json → state="Listed"`** — it is hand-edited. → Enforcement is the standalone CLI gate + a pipeline hook + an `item_state.can_list()` guard, not a single state-setter.
- The `residual_tilt_deg` gate rule is **already** present in `ops/docs/photo-profiles.json` (`op:"gte"`, value 1.5), dormant until a checker emits the value.
- The prototype's `imgs/` fixtures are **not on disk** → tests self-generate fixtures from real `items/` heroes + deterministic transforms.
- `standardize.py` **never calls `exif_transpose`** at ingest → the "bake orientation once" fix is a clean add.

## Architecture & module layout

Engine lives in **image-processor** (image-analysis home, already dual-copied; `residual_tilt_deg` belongs beside the mask gate). cv2/pytesseract isolated to the gate path via inline `uv` deps.

| File | Change | Role |
|---|---|---|
| `image-processor/lib/flat_hero.py` | **new** (verbatim port of prototype) | Tilt measurement + deskew geometry (cv2/numpy). 23/23 validated. Gate reuses `residual_tilt_deg`. |
| `image-processor/lib/hero_qa.py` | **new** | `hero_qa_gate(hero_path, original_path=None, item_class=None) -> {status, checks, reasons}` — orchestrates the 5 checks. |
| `image-processor/scripts/hero_qa.py` | **new** | Standalone CLI (PEP 723 deps): single `hero_qa.py items/RG-XXXX` + `--batch items/` back-fill audit; writes `label.json → hero_qa`. |
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
- Regression guard: port the prototype's 23 tilt/deskew checks (keeps `flat_hero.py` validated).

## Dual-copy & rollout

Implement in source `skills/plugins/richmondgeneral/skills/{image-processor,rg-full-auto}/`, then `rsync -a --exclude=__pycache__` each to `~/.claude/plugins/cache/richmondgeneral/skills/...`. `ops/docs/photo-profiles.json` is single-copy (already carries the tilt rule). Run `hero_qa.py --batch items/` after landing to audit the existing catalog and report any currently-`Listed` items that would fail (back-fill `hero_qa`).
