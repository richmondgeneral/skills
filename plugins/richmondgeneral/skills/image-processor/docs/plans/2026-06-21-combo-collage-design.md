# Combo collage image — design

Date: 2026-06-21
Status: Approved (design); implementation plan to follow.
Owner: image-processor skill (new `combo.py`).

## Problem

Every RG item carries a rich set of detail shots (`detail-maker-mark`, `detail-lid`,
`detail-bottom`, …) but a buyer on a marketplace listing rarely scrolls all of them —
and most channels cap how many photos show before a "see more" fold. The single hero
answers "what is it" but never shows the *proof* (maker's mark, the defining feature,
honest condition). We want one supplementary image that distills an item's **most
interesting views** into a single frame that a buyer can't miss.

## Decisions (from the 2026-06-21 brainstorm)

1. **Destination = marketplace extra photo.** An added slot on eBay / Facebook /
   Whatnot. Not the primary listing image (that stays the clean full hero), not a
   social post, not the site card. Highest-value use: channels cap photo count and our
   detail shots otherwise go unseen.
2. **Frame = 1:1 square @ 1600px.** Native ratio for all three target channels, so it
   drops into any photo slot without re-cropping.
3. **Layout = hero-dominant "magazine".** Hero panel ~62% width × full height; a rail
   of **3 detail crops** at ~38%. ~5px warm-cream gutters; every panel on white.
   Chosen over equal 2×2 quad (no focal point), big-top filmstrip (better only for very
   wide items), and hero+corner-insets (dramatic but holds the fewest views and covers
   the item).
4. **Captions = subtle micro-captions + faint wordmark.** Each rail crop gets a small
   lower-corner caption; a faint "Richmond General · RG-XXXX" wordmark sits in the hero
   corner. Standard for seller "detail montage" photos; adds provenance + honesty value.
   (This is an *extra* photo, so light text is acceptable — the primary stays text-free.)

## Slot semantics + automatic selection

Key realization: **our detail filenames are already semantic**, so the builder maps
files → slots by a priority table — no manual picking required. First present wins;
operator can override any slot by naming a file.

| Slot   | Role                    | Picks first present of…                                              |
|--------|-------------------------|---------------------------------------------------------------------|
| Hero   | "What is it"            | the approved `hero` (post `hero_qa` pass)                            |
| Rail 1 | Provenance              | `detail-maker-mark` → `detail-stamp` → `detail-ext-mark` → `detail-signature` → `detail-label` |
| Rail 2 | Defining feature        | type-aware: `detail-lid`/`detail-interior` (vessels), mechanism/control (tech), `detail-spine`/`detail-title` (books), `detail-face` (figures) → else best remaining detail |
| Rail 3 | Condition / orientation | `detail-bottom` → `detail-back` → `detail-condition` → `detail-profile` → `detail-side` |

Worked examples (both rendered from live photos in the brainstorm mockup):

- **RG-0055** (Kreamer covered pail): hero = full pail · Rail 1 = Kreamer mark ·
  Rail 2 = lid & bail fit · Rail 3 = honest patina (base).
- **RG-0054** (Avon "Hip Hop Harry" bunny): hero = full bunny · Rail 1 = Avon ©2002 tag ·
  Rail 2 = "Hip Hop" knit · Rail 3 = back view.

## The real work: tight crops

The rail is only as good as its crops. Our shelf-walk frames are cluttered, rotated,
single-angle (the stray Fargo 45rpm record that swept into RG-0054's photo cluster is
the cautionary tale — see the intake segmentation SOP). Each rail crop is
**auto-tightened to its subject** using the alpha-bbox from the matte / BiRefNet tooling
we already run, with **center-cover as fallback** and an **operator crop-box override**
for when saliency picks wrong. Hero uses cover with a slight upward bias to retain
top features (handles, caps); minor edge crop is acceptable because the *primary*
listing photo carries the full uncropped item.

## Guardrails (inherited)

- **Non-generative.** Only crops, scales, composites existing pixels and draws caption
  text. Cannot fabricate a mark or feature — same safety class as `matte.py` / `upres.py`.
  Safe to auto-run even on labeled goods.
- **Honest.** The condition slot shows real wear; never edits out a defect.
- **Factual captions.** Drawn from `label.json` — never invented.
- **Supplementary.** Output is an *added* photo; the clean full hero remains primary.

## Open knobs — chosen defaults

1. **Caption text** → pull specifics from `label.json` when present
   ("Kreamer · Size 50"); fall back to the generic role label ("Maker's mark").
2. **Coverage** → build a combo only for items with **≥3 quality detail shots**; skip
   thin ones (an empty/weak slot looks worse than no combo). `combo.py` exits with a
   skip notice, not an error.
3. **Rail size** → default **3**; allow **4** when an item has ≥5 quality details.

## Production shape

- New script: `image-processor/scripts/combo.py`
  `--item-dir items/RG-XXXX [--layout magazine] [--slots mark=…,feature=…,cond=…]
   [--rail 3|4] [--caption-mode specific|generic]`.
- Output: `items/RG-XXXX/combo.png` (1600×1600). Records to
  `label.json → image_pipeline[]` like the other tools.
- Composition is deterministic PIL (crop / resize / paste / draw caption text) — no
  torch required for the compositor itself; subject-bbox crops reuse the existing matte
  alpha (or center-cover fallback) so `combo.py` stays torch-free and runs inline over
  the Cowork bridge.
- Slots into the existing flow: matte → (combo) → `build_gallery.py`. Dual-copy synced
  to the plugin cache (source + `~/.claude/plugins/cache/.../image-processor/`).
- Channel use is manual at first: operator adds `combo.png` as an extra marketplace
  photo. (Auto-attach to eBay/FB/Whatnot is a later, separate step.)

## Out of scope (YAGNI)

- Auto-attaching the combo to channels (manual add first).
- Social / 4:5 variants, site-card montages, internal QA contact sheets (the other three
  destinations considered and deferred).
- Generative enhancement of crops (SUPIR/genai) — stays showcase-only, never here.
- Animated / multi-frame combos.

## Next

Implementation plan via the writing-plans skill →
`docs/plans/2026-06-21-combo-collage-implementation.md`.
