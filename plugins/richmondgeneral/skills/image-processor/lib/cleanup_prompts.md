# Catalog Image Cleanup — universal prompt

Shared prompt library for AI-driven catalog-image cleanup.

**Consumers:**
- `skills/image-processor/scripts/clean.py` — Mac / Gemini path, run from Claude Code
- (future) `square-image-upload-cowork` — Cowork / Cloudinary path

**Composition:**
- Default cleanup = `base` + `damage-preserve`
- `--fix-damage` mode = `base` + `damage-fix`
- `--remove "text"` appends a freeform `Additional direction:` block to either

**File format:** each section is an H2 (`## name`). Body = everything between
the heading and the next H2. Block comments (lines starting with `<!--`) are
ignored. Both consumers parse this file the same way and concatenate the
sections themselves — no logic lives here.

---

## base

Prepare this image as a Richmond General storefront catalog photo:

- Clean, neutral background (preferably white or very light grey); remove
  any background clutter, other inventory items, or shop fixtures.
- Item centered and well-framed; do not crop tightly to the edges.
- Sharp focus throughout. Crisp, legible text on any packaging, labels,
  tags that belong to the product (Hallmark text, year stamps, series
  numbers, stock numbers, maker's marks, etc.).
- Remove price tags, store stickers, inventory labels, "AS IS" / "FINAL
  SALE" / estate-sale tags, watermarks, vendor branding (Faire, Etsy,
  eBay, supplier logos), human hands/fingers/thumbs, photographer
  reflections, hot specular glare on glass/varnish/lacquer that obscures
  detail.
- Preserve faithful colors. Keep authentic warm tones of brass, copper,
  gold, mahogany, amber glass, oxidized bronze, aged paper, sepia
  photographs, terracotta, shellac. Keep authentic cool tones of silver,
  pewter, blued steel, jadeite, ceramic. Do not flatten material sheen
  — natural diffuse highlights give the item dimension and should
  remain.
- Match daylight white balance (~5500–6500K); neutralize warm tungsten /
  yellow-incandescent shop-lighting casts on whites, papers, and
  ceramics, but keep colors that legitimately belong to the item.

## damage-preserve

PRESERVE all visible damage, wear, scratches, chips, cracks, dings,
chips in paint, fading, foxing on paper, oxidation, tarnish, surface
abrasions, and any other condition issues exactly as they appear in the
source photo. These are documentary evidence of the item's actual
physical state and are critical for honest appraisal, provenance, and
customer trust. The customer must see what they are buying.

Do not retouch out, hide, soften, or repair any condition flaws.

## damage-fix

Repair visible damage as part of the cleanup pass — scratches, chips in
paint, cracks, smudges, tears, surface dings, paper foxing, light
oxidation. Render the item as it would appear in good restored
condition.

Important: keep authentic age patina that gives the item character —
do not over-restore. Subtle wear, mellow aging of finishes, soft edges
on metal, and similar natural aging cues that signal authenticity to a
collector should remain. The goal is "professionally restored" looking,
not "factory new."
