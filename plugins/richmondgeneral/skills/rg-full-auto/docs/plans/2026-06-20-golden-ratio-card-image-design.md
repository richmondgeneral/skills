# Golden-Ratio Transparent Card Image — Design

**Date:** 2026-06-20
**Status:** Approved (brainstorm) — ready for implementation plan
**Author:** Claude (brainstorming skill)
**Related:** [hero-qa-gate](2026-06-20-hero-qa-gate-design.md), RG-0031 hero postmortem, `ops/docs/photo-profiles.json`

## Goal

For any item that has a clean **transparent cutout**, produce a new derived image — `card.png` — showing the item floated, centered, on a **horizontal golden-ratio (φ ≈ 1.618 : 1) transparent canvas**. Display it natively on the GitHub Pages item cards (gallery grid + detail flip-card) and push it to Square as an **additional** catalog image. The existing `hero.png` is never modified.

This is a presentation/branding asset, not a replacement product photo.

## Decisions (locked in brainstorm 2026-06-20)

| Question | Decision |
|---|---|
| Produce how / replace hero? | **New `card.png`**, deterministically composed from the existing transparent cutout. No AI. `hero.png` untouched. |
| Items with no cutout (flat-goods books/paper, keep-bg glass/silver)? | **Skip them.** Only items with a real transparent cutout get a `card.png`. |
| Website card layout? | **Change both cards to golden ratio** (gallery grid, currently 4:3 → 1.618; detail flip-card → 1.618). |
| Square placement? | **Additional image** (omit `--primary`); current hero stays Square primary so the storefront grid thumbnail isn't square-cropped oddly. |

## Background — current state

- `standardize.py` outputs a **2000×2000 square (1:1) transparent PNG** cutout (`square_pad_centered()`, object fills 85% of canvas, transparent RGBA, LANCZOS). No non-square / golden aspect exists anywhere in the pipeline today.
- Photo profiles (`ops/docs/photo-profiles.json`): `standard` / `true-color` → square transparent cutout; `flat-goods` (books/paper/cards) and `keep-bg` (glass/silver/mirror) → **full-bleed opaque, no cutout**; `manual` → human review.
- Hero-QA gate (`hero_qa.py`) deliberately does **NOT** require transparency — opaque heroes always pass `bg_ok`; only a flat-good shipped as a transparent cutout fails. (RG-0031 reversed an "always transparent" rule.) The card feature respects this: it never forces transparency, it only *consumes* a cutout when one already exists.
- Website cards:
  - Detail flip-card: `items/template/rg-item-card-template.html` — `.item-image-container` (cream `#F5F1E8`, `padding`, flex-center) + `.item-image { object-fit: contain }`. No fixed aspect.
  - Gallery grid: `items/index.html` — `.item-image { aspect-ratio: 4 / 3; background: var(--rg-cream) }` + `img { max-width:90%; max-height:90%; object-fit: contain }`.
  - Generator copy: `skills/plugins/richmondgeneral/skills/rg-full-auto/references/info-card-template.html` (must be kept in sync — known dual-copy trap).
- Most existing `hero.png` files are raw portrait JPEGs (≈896×1195), **not** transparent cutouts. So `card.png` only materializes once an item has been run through `standardize.py`. Feature is forward-looking + backfill-as-you-restandardize.

## The image spec

- **Canvas:** `WIDTH × round(WIDTH / PHI)` where `PHI = 1.6180339887`. Default `WIDTH = 2000` → `2000 × 1236` (2000/1236 = 1.6181). RGBA, fully transparent `(0,0,0,0)`. Horizontal (width > height). Width configurable via CLI; height always derived from `PHI` (never hand-set, so the ratio can't drift).
- **Composition algorithm:**
  1. Open source hero as RGBA. If it has **no real transparency** (`min(alpha) ≥ 250`, i.e. effectively opaque), **return `None` and log "no cutout → skipped"**. This is the same alpha heuristic the QA gate uses, and it is what excludes flat-goods / keep-bg automatically.
  2. Tight-crop to the alpha bounding box (`getbbox()` on the alpha channel).
  3. Scale the cropped cutout so it fits within `(FILL × WIDTH, FILL × HEIGHT)` preserving aspect, where `FILL = 0.85` (matches `standardize.py` default). The limiting dimension wins: portrait items are height-constrained (lots of transparent margin left/right — the intended look), wide items are width-constrained.
  4. Paste centered onto the transparent canvas (integer-centered).
  5. Save as PNG (RGBA), carry over the same PNG metadata chunks `standardize.py` writes (copyright/SKU) where available.
- **Output:** `items/RG-XXXX/card.png`. New file; `hero.png` untouched.
- **No drop shadow** (YAGNI — can add later if desired).

## Architecture

**Recommended: new standalone module `scripts/golden_card.py`** (mirrors the `deskew.py` / `hero_qa.py` pattern):

- Pure function `compose_golden_card(hero_path, out_path=None, width=2000, fill=0.85) -> Path | None` (returns the written path, or `None` if skipped because opaque).
- A `__main__` CLI: `golden_card.py <hero.png> [--out card.png] [--width 2000] [--fill 0.85]`, plus a `--batch items/` mode for backfill (walks `items/RG-*/`, composes from each item's standardized transparent hero, skips opaque/non-cutout, logs a summary; non-fatal on skips).
- `standardize.py` calls `compose_golden_card()` after it produces the transparent cutout, gated behind a new `--card / --no-card` flag (**default on**). It writes `card.png` next to the standardized hero and records the result.

*Alternatives considered and rejected:*
- **Inline inside `standardize.py`** — not independently runnable for backfill, harder to unit-test.
- **Only in `rg-full-auto`** — the user explicitly asked to "add to image processing"; it also wouldn't be reusable by `rg-item-update` or ad-hoc runs.

## Integration points (exact files)

1. **New module (×2 copies — dual-copy trap):**
   - Source: `skills/plugins/richmondgeneral/skills/image-processor/scripts/golden_card.py`
   - Cache: `~/.claude/plugins/cache/richmondgeneral/.../image-processor/scripts/golden_card.py`
2. **`standardize.py` (×2 copies):** add `--card/--no-card`, call `compose_golden_card()` after cutout, log outcome.
3. **`label.json`:** record `photos.card: "card.png"` when one is produced (omit when skipped).
4. **Website templates / CSS:**
   - `items/template/rg-item-card-template.html` — `.item-image-container` → `aspect-ratio: 1.618`; render `card.png` when present, else `hero.png` (cream still shows through transparency; keep `object-fit: contain`).
   - `items/index.html` — `.item-image` `aspect-ratio: 4 / 3` → `1.618`; same `card.png`-or-`hero.png` selection.
   - `skills/plugins/richmondgeneral/skills/rg-full-auto/references/info-card-template.html` — same change as the detail template (generator copy).
   - The rg-full-auto page generator + gallery (`index.html`) generator must emit `card.png` as the `<img src>` when `photos.card` exists (exact generator script to be pinned during planning).
5. **Square:** rg-full-auto Square phase uploads `card.png` as an **additional** image (`square-image-upload` / `upload_to_square.py`, omit `--primary`); verify the new `image_id` appears in `image_ids` and primary is unchanged. Backfill existing cutout items the same way.

## Edge cases / skip rules

- Opaque hero (no alpha or alpha all ≥250) → skip, log, no `card.png`, no `photos.card`. Covers flat-goods + keep-bg.
- Hero missing / unreadable → skip with a clear error, do not crash the batch.
- Cutout wider than tall vs taller than wide → handled by the limiting-dimension fit in step 3.
- Cutout larger than canvas → always downscaled to `FILL` envelope; never upscaled beyond its native size unnecessarily (cap scale at 1.0 only if it would degrade — acceptable to upscale a small cutout to fill; decide in plan, default allow upscale to FILL envelope).
- `cv2` not needed here (pure PIL) — no new heavy dependency; Pillow already in `pyproject.toml`.

## Testing strategy

- **Unit (`golden_card.py`, pure PIL — fast, deterministic):**
  - Synthetic transparent cutout (e.g. opaque disc on transparent field) → output is exactly `2000×1236`; ratio within 0.5% of φ.
  - Item is centered (bbox centroid ≈ canvas center within tolerance); padding pixels fully transparent.
  - Portrait synthetic cutout → height-constrained; wide synthetic cutout → width-constrained.
  - Fully-opaque input (alpha all 255 / RGB no alpha) → returns `None`, writes nothing.
  - Custom `--width` derives the matching golden height.
- **Regression (templates):** string-assert that `items/template/rg-item-card-template.html`, `items/index.html`, and the generator copy contain the golden aspect ratio value and reference `card.png`.
- **Visual spot-check:** compose a card for one real cutout item and eyeball it in the detail + gallery card.

## Out of scope (YAGNI)

- Drop shadows / generative backgrounds / re-cutting non-cutout items.
- Responsive multiple-resolution variants.
- Changing Square primary image or storefront crop behavior.

## Risks / notes for the implementer

- **Dual-copy:** every `image-processor` script + every template edit must land in BOTH the source tree and the `~/.claude/plugins/cache/...` copy (Cowork bridge runs source; code-mode runs cache). `rsync -a --exclude=__pycache__ src/ cache/` after script edits.
- **Multi-repo:** this feature spans two git repos — `skills/` (image-processor, rg-full-auto) and `items/` (templates, `index.html`). Commit per-repo, stage **explicit paths only** (never `git add -A`), and follow the workspace concurrency rules (verify branch immediately before each commit; `git log origin/main..main` before any push; clean fast-forward only).
- **Backfill** is opt-in via `golden_card.py --batch items/`; it only affects items that already have a transparent cutout.
