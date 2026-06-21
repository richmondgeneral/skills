---
name: image-processor
description: Unified image processing with background removal, generation, editing, listing-photo standardization, and Photos.app integration. Auto-routes to optimal model (Nano Banana Pro, Gemini 2.5, remove.bg) based on task. Triggers on "remove background", "generate image", "edit image", "process photo", "standardize listing photos", "make photos professional/catalog-quality", "square crop / center / color-correct photo", "transparent hero", "photos library", "get from photos", or when rg-full-auto needs image processing.
metadata:
  version: "1.12"
  author: scottybe
  updated: "2026-06-21"
  changelog: |
    v1.12 - Local faithful enhance stage (torch/Metal, two-agent handoff):
    - NEW scripts upres.py / sharpen.py / enhance.py — non-generative, faithful
      enhancement on Apple-Silicon MPS for the 896px legacy batch + any soft hero.
      upres.py = Real-ESRGAN x2/x4 (RRDBNet via spandrel, BSD); sharpen.py =
      deterministic PIL unsharp (default) or NAFNet deblur (--deblur, MIT, base
      spandrel); enhance.py = non-destructive one-pass upres->sharpen ->
      hero.enhanced.png (matte stays the separate downstream step). All record
      label.json -> image_pipeline[] for reproducibility.
    - ENV: dedicated venv ~/.cache/rg-enhance (py3.12; torch/torchvision MPS +
      spandrel + pillow/numpy) — torch has no 3.14 wheels, so NOT in the plugin
      env (same isolation as ~/.cache/rg-matte). Invoke by absolute interpreter
      path: `~/.cache/rg-enhance/bin/python .../upres.py --item-dir items/RG-XXXX`.
      spandrel REPLACES realesrgan+basicsr (basicsr imports the removed
      torchvision.transforms.functional_tensor and won't load on MPS torchvision).
    - Two-agent handoff PROVEN: env runs + reaches MPS under a non-interactive
      `osascript do shell script`, so Cowork can drive it over the bridge.
    - GUARD unchanged: these three are non-generative (safe to auto-run, even on
      labeled goods). Generative upres/restore (SUPIR/genai) stays showcase-only +
      clean.py --agentic judge-gated. Verified faithful on RG-0025 (896->1792, ~3s).
    v1.11 - Agentic Image Evaluation Loop (Anti-Hallucination):
    - Added `--agentic` flag to `clean.py` for a Best-of-3 generation loop.
    - Added `AgentJudge` powered by `gemini-2.5-pro` using native Google GenAI SDK (structured output) to validate candidate images.
    - Hallucinations (fake backstamps, altered compositions) are automatically rejected.
    - Auto-escalates to `gemini-3-pro-image-preview` if Flash candidates repeatedly fail the judge.

    v1.10 - Patina-safe WB and Batch Overrides:
    - Patina-safe WB is the new default: samples the backdrop border as the neutral reference,
      so brass/Bakelite keeps its true color (falls back to gray-world if border is unusable).
    - Added `--wb {background,grayworld,none}` CLI flag.
    - Added per-item overrides via `label.json`'s `photo_overrides` block to bypass
      bg-removal/color-correction dynamically per item for batch mode.

    v1.9 - Standardizer premium polish (gallery-tier pipeline):
    - --fill (default 0.85): object's longest side fills a fixed fraction of the
      canvas on every item -> uniform storefront grid (replaced the raw margin).
    - --shadow: subtle, SIZE-PROPORTIONAL soft drop shadow (grounds the cutout so it
      isn't a floating sticker; blur/offset scale with the canvas, not a fixed 10px).
    - --copyright / --sku: embed provenance in PNG text chunks; GPS/EXIF already
      dropped on save (privacy). Framed as attribution/anti-theft, not an SEO boost.
    - --watermark / --watermark-logo: composite the RG logo bottom-right for SOCIAL
      share variants only (NOT the eBay/Square hero — eBay restricts added artwork).
      Canonical logo saved to brand/assets/richmond-general-logo.{png,jpg}.
    - router.py: --model now actually restricts to the requested model (removebg was
      silently ignored by the quality-score sort before).
    - --straighten remains a documented no-op (auto-deskew needs opencv, absent).

    v1.8 - Listing photo standardizer (RG public-photo SOP enforcement):
    - standardize.py turns a raw documentation photo into a catalog-quality PUBLIC
      image per ops/docs/RG-listing-SOP.md: color-correct (gray-world white balance
      + mild auto-contrast, toward real-life vs intake lighting) -> background
      removal (reuses process.py routing) -> square 1:1, object centered on a
      transparent canvas -> resize. Output is a transparent PNG; the HERO is always
      transparent. COLOR + GEOMETRY ONLY — never edits content, so chips/crazing/wear
      stay visible (honesty rule). Raw archive is never touched (input -> --output).
    - Deterministic + offline color & square steps (unit-tested); bg removal is the
      existing AI path. Flags: --no-bg (re-square an already-transparent hero, no API),
      --no-color, --model {removebg|nano-banana|gemini25|auto}, --allow-rect-mask
      (cluttered shots), --margin, --size. bg-removal errors are surfaced (rect-mask /
      credits), not swallowed. --straighten is a documented no-op (reliable auto-deskew
      needs opencv, absent — shoot straight; the square crop never rotates).

    v1.7 - Key bootstrap actually reached + billing-aware 429 (RG-0030 fix):
    - create_default_router() now calls bootstrap_keys() itself. The CLI
      scripts put lib/ on sys.path and import router/models TOP-LEVEL, so
      lib/__init__.py (where v1.6 placed the bootstrap) never ran on that path
      — over the bare mac-bridge shell every model got api_key=None,
      health_check() was False, the fallback chain was empty, and edits died
      with "All models failed" before a single HTTP call. v1.6's env.py was
      correct but UNREACHABLE from the CLI path; this makes it reachable.
    - router.process_with_fallback() now returns a specific "No healthy model
      ... missing API key (GEMINI_API_KEY)" error when the chain is empty,
      instead of the vague "All models failed" that got this misread as a 429.
    - gemini_image._post_with_retry() fails FAST on a depleted-credits 429
      (RESOURCE_EXHAUSTED / "prepayment credits are depleted") with an
      actionable https://ai.studio/projects billing message, instead of 5x
      backoff (~70s) then a vague "Too Many Requests". Transient rate-limit
      429s still retry as before.
    - Tests: testing/unit/test_image_router.py (bootstrap + empty-chain),
      testing/unit/test_image_gemini_retry.py (billing vs transient 429).
    v1.6 - Bridge key resolution + anti-hallucination guard:
    - lib/env.py resolves GEMINI_API_KEY / NANO_BANANA_API_KEY (env -> Keychain
      -> workspace .env) into os.environ on lib import, so clean.py works over
      the bare mac-bridge shell (was "All models failed" because ~/.zshrc never
      ran to export the keys).
    - cleanup_prompts.md base now forbids adding/inventing any text, tags, SKUs,
      labels, or watermarks — a cleanup run had fabricated a fake price tag.

    v1.5 - Safe Photos database access:
    - lib/photos.py now opens Photos.sqlite with mode=ro&immutable=1 (was
      mode=ro only). immutable=1 additionally prevents shared locks and WAL
      reads on the live cloudphotod-managed database, matching photos-library
      v1.3. Avoids any chance of disrupting iCloud Photos sync.

    v1.4 - Catalog-cleanup CLI, model upgrade, reliability:
    - Added `clean.py` — catalog-image cleanup driver. One universal prompt
      produces a clean storefront-ready photo from any source. Replaces the
      old per-task preset scheme (`remove-price-tag`, `remove-sticker`, etc.).
    - Prompt sections live in `lib/cleanup_prompts.md` (`base`,
      `damage-preserve`, `damage-fix`). Cowork-side consumers can read the
      same file to keep phrasing consistent across providers.
    - Damage handling: preserved by default for honest provenance/appraisal.
      `--fix-damage` for restoration. `--both` for the museum preserved+fixed
      pair. `--remove "freeform"` for one-off custom direction.
    - Model upgrade: default endpoint bumped to `gemini-3.1-flash-image-preview`
      (4K output capable, was `gemini-2.5-flash-image` at 1K). `--pro` flag
      forces `gemini-3-pro-image-preview` for hard cases. Old preset-detection auto-escalation removed:
      model choice is now driven only by `GEMINI_IMAGE_MODEL` env, the
      explicit `quality_hint`, and `num_refs >= 8` (no more prompt-content
      heuristic — that produced silent 4× cost surprises).
    - `_post_with_retry()` in `gemini_image.py` — exponential backoff (2s →
      32s) + jitter on Gemini 429/5xx, honors `Retry-After`. Makes
      `--all-images` parallel mode survive rate limits.
    - Pre-Gemini input downscale to ≤ 2048px long edge (configurable via
      `--max-long-edge`, `--no-downscale` to disable). Gemini downsamples
      internally anyway; pre-shrinking cuts upload time ~5× on hi-res sources.
    - Post-Gemini output downscale to ≤ 1800px long edge (configurable via
      `--max-long-edge-output`). Square storefront displays at most ~1500px,
      so we trim before upload to save storage + bandwidth.
    - `router.py` print-to-stderr fix (was polluting stdout JSON output of
      callers like `refresh_item_image.py`).

    v1.3 - Group background-removal workflow:
    - Added `process_group.py` for batch background removal in item folders
    - Added skip logic for QR/label assets and already-transparent images
    - Added strict rectangular-mask QA guard support in batch mode

    v1.2 - QA guard and odd-placement editing:
    - Added strict rectangular-mask guard in `process.py` (with `--allow-rect-mask` bypass)
    - Added `edit.py --odd-placement` mode for playful scene placement composites
    - Updated CLI output behavior so verbose logs stay on stderr

    v1.1 - Background removal reliability improvements:
    - `process.py --model` now enforces preferred model ordering
    - Added remove.bg request profile fallbacks and retry handling
    - Added output mask-quality check with auto-recovery retry via remove.bg

    v1.0 - Initial consolidated release:
    - Merged gemini-chat, image-generation-skill, image-editing-skill
    - Unified model routing with fallback chain
    - Added Photos.app library access via SQLite
    - Eliminated duplicate code and fragile symlinks
---

# Image Processor

Unified image processing skill combining background removal, image generation, image editing, listing-photo standardization, and Photos.app library access.

## Listing Photo Standardizer (public-photo SOP)

`standardize.py` turns a raw documentation photo into a **catalog-quality public image** per
[`ops/docs/RG-listing-SOP.md`](../../../../../ops/docs/RG-listing-SOP.md) — the "thematic thread"
that makes every public photo look cohesive:

- **Color-corrected** toward real-life color (backdrop-referenced white balance preserves
  patina on brass/Bakelite, falls back to gray-world)
- **Background removed**, **hero always transparent** (reuses `process.py` routing/fallbacks)
- **Standardized scale** — `--fill 0.85` makes the object's longest side fill the same fraction of the
  canvas on every item, so the storefront grid looks uniform
- **Grounding** — `--shadow` bakes a subtle, size-proportional soft drop shadow so the cutout isn't a
  "floating sticker" (assumes a light display surface — your card/Square are light)
- **Privacy + provenance** — GPS/EXIF is dropped automatically; `--copyright "Richmond General"` and
  `--sku RG-XXXX` embed provenance in PNG text chunks (attribution/anti-theft, not an SEO boost)
- **Brand watermark** — `--watermark` composites the RG logo (`brand/assets/richmond-general-logo.png`)
  bottom-right for **SOCIAL/share variants only** (FB/Pinterest) — NOT the eBay/Square hero (eBay
  restricts added artwork on the primary image)
- **Honesty preserved** — color + geometry ONLY; never edits content, so chips/crazing/wear stay visible

```bash
# Full public hero (color -> bg-remove -> square 1:1 @85% fill -> grounded -> provenance):
uv run python scripts/standardize.py raw.jpg -o public-hero.png --size 2000 --shadow \
    --copyright "Richmond General" --sku RG-0031
# Social-share variant (adds the watermark):
uv run python scripts/standardize.py raw.jpg -o social.png --shadow --watermark --sku RG-0031
# Re-square an already-transparent hero with no API call:
uv run python scripts/standardize.py items/RG-0028/hero.png -o hero-square.png --no-bg
# Cleaner cutout / cluttered fallback:
uv run python scripts/standardize.py raw.jpg -o out.png --model removebg      # best cutout
uv run python scripts/standardize.py raw.jpg -o out.png --allow-rect-mask     # accept rough mask
```

Apply only to the **curated public subset**; the raw archive (Photos library, tagged by SKU) and the
`items/RG-XXXX/` originals stay untouched (input → `--output`). `--straighten` is a documented no-op
(reliable auto-deskew needs opencv, which isn't installed — shoot straight; the square crop never rotates).
Clean single-object shots cut out best; multi-object layouts produce rough masks. The canonical logo
lives at `brand/assets/richmond-general-logo.{png,jpg}` (transparent PNG + original).

## Local Enhance Stage (Real-ESRGAN / unsharp / NAFNet — torch/MPS)

**Non-generative, faithful** upscale + sharpen for the 896px legacy batch and any soft/low-res hero.
These run on Apple-Silicon **MPS** from a **dedicated venv** `~/.cache/rg-enhance` (py3.12; torch has no
3.14 wheels, so it is NOT in the plugin env — same isolation as `~/.cache/rg-matte`). Invoke by absolute
interpreter path; the env is provisioned once by the code agent and is bridge-safe (runs + reaches MPS
under a non-interactive `osascript do shell script`, so Cowork can drive it).

- **`upres.py`** — Real-ESRGAN x2/x4 (RRDBNet via `spandrel`, BSD) to a target min width. Faithful:
  sharpens/enlarges existing pixels, never invents label text or marks. Records `image_pipeline[]`.
- **`sharpen.py`** — deterministic PIL **unsharp** (default, torch-free) or **NAFNet deblur** (`--deblur`,
  MIT, base-`spandrel`) for genuinely motion/defocus-blurred shots.
- **`enhance.py`** — non-destructive one-pass `upres -> sharpen` → `hero.enhanced.png` (review, then
  promote). `matte.py` stays the separate downstream step (different venv + RGBA alpha).

```bash
# provision once (code agent):
uv venv ~/.cache/rg-enhance --python 3.12
uv pip install --python ~/.cache/rg-enhance torch torchvision pillow numpy spandrel
# weights -> ~/.cache/rg-enhance/weights/{RealESRGAN_x2plus,RealESRGAN_x4plus,NAFNet-deblur}.pth

# upscale the 896px batch to >=1500px (default suffixed output; never clobbers the source):
~/.cache/rg-enhance/bin/python scripts/upres.py --item-dir items/RG-XXXX --target-w 1500
# finishing sharpen, or deblur a genuinely blurry shot:
~/.cache/rg-enhance/bin/python scripts/sharpen.py --item-dir items/RG-XXXX           # unsharp
~/.cache/rg-enhance/bin/python scripts/sharpen.py --item-dir items/RG-XXXX --deblur  # NAFNet
# one-pass review output, then promote + matte:
~/.cache/rg-enhance/bin/python scripts/enhance.py --item-dir items/RG-XXXX           # -> hero.enhanced.png
```

**GUARD:** these three are non-generative and safe to auto-run, even on labeled goods. **Generative**
upres/restore (SUPIR / genai) is a SEPARATE, **showcase-only** path that MUST keep the `clean.py
--agentic` marks/text judge — never auto-run it on items with printed labels.

## Quick Start

### Background Removal

```bash
python scripts/process.py image.jpg
python scripts/process.py image.jpg --output result.png
python scripts/process.py image.jpg --quality premium
python scripts/process_group.py --input-dir /Users/scottybe/workspace/square/items/RG-0015 --quality premium --model auto --json
```

### Image Generation

```bash
python scripts/generate.py --prompt "A vintage typewriter on wooden desk" --output result.png
python scripts/generate.py --prompt "Apply this style" --reference style.jpg --output styled.png
python scripts/generate.py --prompt "Professional product photo" --quality pro --output hero.png
```

### Image Editing

```bash
python scripts/edit.py --input photo.jpg --instruction "remove the background" --output result.png
python scripts/edit.py --input photo.jpg --instruction "change to sunset lighting" --output sunset.png
python scripts/edit.py --input subject.jpg --instruction "place in scene" --reference bg.jpg --output composite.png
python scripts/edit.py --input subject.jpg --odd-placement "the dashboard of a spaceship" --output odd-scene.png --quality pro
```

### Catalog Cleanup (v1.4 — single universal prompt)

```bash
# Preserve damage (honest condition photo — default):
python scripts/clean.py -i photo.jpg -o cleaned.jpg

# Repair damage (restoration look):
python scripts/clean.py -i photo.jpg -o cleaned.jpg --fix-damage

# Produce both variants for museum before/after pairing:
python scripts/clean.py -i photo.jpg -o cleaned.jpg --both
# → cleaned-preserved.jpg + cleaned-fixed.jpg

# Use the heavier Gemini 3 Pro model for complex generations:
python scripts/clean.py -i photo.jpg -o cleaned.jpg --pro

# Use the Agentic Loop (Best-of-3 + AI Judge) to strictly prevent hallucinations:
python scripts/clean.py -i photo.jpg -o cleaned.jpg --agentic

# Freeform additional direction layered onto the universal prompt:
python scripts/clean.py -i photo.jpg -o cleaned.jpg --remove "the dust on the rim"

# Disable pre-Gemini downscale (keep full input resolution):
python scripts/clean.py -i photo.jpg -o cleaned.jpg --no-downscale

# Disable post-Gemini output downscale (keep Gemini's full output):
python scripts/clean.py -i photo.jpg -o cleaned.jpg --no-downscale-output
```

For an end-to-end "fix this item on Square" flow, use [refresh_item_image.py](../square-image-upload/scripts/refresh_item_image.py) in the `square-image-upload` skill — it wraps `clean.py` + Square download/upload in one step.

### Photos.app Access

```bash
python scripts/photos.py --recent 10
python scripts/photos.py --albums
python scripts/photos.py --favorites
python scripts/photos.py --search "IMG_*.jpg"
python scripts/photos.py --since 2025-12-01 --limit 20
python scripts/photos.py --copy UUID --output ~/Desktop/photo.jpg
python scripts/photos.py --stats
```

## Models

| Model | Tasks | Speed | Quality | Cost |
|-------|-------|-------|---------|------|
| Nano Banana Pro | remove-bg, analyze | ~8s | 98% | Free |
| Gemini 2.5 Flash | remove-bg, analyze | ~8s | 95% | Free |
| remove.bg | remove-bg | ~3s | Premium | $0.009/img |
| Gemini Image | generate, edit | ~12s | 96% | Free |

## Smart Routing

The router automatically selects the best model based on:

1. **Task capability** - Model supports the requested task
2. **Quality requirements** - Meets quality threshold
3. **Cost preferences** - Prefers free models by default
4. **Health status** - Model API is available
5. **Fallback chain** - Tries alternatives on failure

### Fallback Chain (remove-bg)

```
Nano Banana Pro (98%, free)
  ↓ if unavailable
Gemini 2.5 Flash (95%, free)
  ↓ if unavailable
remove.bg (premium, paid)
```

### Generation/Edit Model Selection

Auto-selects Flash vs Pro by:
- `GEMINI_IMAGE_MODEL` env var (explicit override; set by `clean.py --pro`)
- `quality_hint` task config field (`fast` → Flash, `pro`/`premium` → Pro)
- Number of reference images (8+ → Pro — legitimate structural complexity signal)
- Otherwise → Flash

Note: prompt-content scanning was removed in v1.4. Earlier versions escalated to Pro when prompts contained "4k", "high quality", "professional", etc. — that produced surprising 4× cost jumps when callers happened to include those words. Use `--pro` (or set `GEMINI_IMAGE_MODEL`) when you want Pro.

## CLI Reference

### process.py

```
python scripts/process.py IMAGE [OPTIONS]

Arguments:
  IMAGE              Input image path

Options:
  -o, --output PATH  Output image path
  -t, --task TASK    Task type: remove-bg, analyze (default: remove-bg)
  -q, --quality LVL  Quality: low, medium, high, premium (default: high)
  -m, --model MODEL  Model preference: nano-banana, gemini25, removebg, auto
  --allow-rect-mask  Do not fail when output appears to be a rectangular/box mask
  --json             Output JSON
  -v, --verbose      Verbose output
```

Notes:
- `--model` is honored as first-choice routing (with fallback chain if it fails).
- `remove-bg` runs a mask-quality check and auto-retries with `removebg` when output looks like a rectangular box mask.
- By default, suspicious rectangular masks fail the command unless recovery succeeds (`--allow-rect-mask` bypasses this guard).

### generate.py

```
python scripts/generate.py --prompt TEXT --output PATH [OPTIONS]

Options:
  -p, --prompt TEXT     Text description (required)
  -o, --output PATH     Output image path (required)
  -r, --reference PATH  Reference image(s) for style
  -q, --quality LVL     Quality: auto, fast, pro (default: auto)
  --json                Output JSON
  -v, --verbose         Verbose output
```

### edit.py

```
python scripts/edit.py --input PATH --instruction TEXT --output PATH [OPTIONS]

Options:
  -i, --input PATH       Input image to edit (required)
  -I, --instruction TEXT Edit instruction
  --odd-placement TEXT   Place item in a playful scene (example: "inside a submarine control room")
  -o, --output PATH      Output image path (required)
  -r, --reference PATH   Reference image(s)
  -q, --quality LVL      Quality: auto, fast, pro (default: auto)
  --json                 Output JSON
  -v, --verbose          Verbose output
```

Notes:
- Pass either `--instruction` or `--odd-placement` (or both).

### process_group.py

```
python scripts/process_group.py --input-dir PATH [OPTIONS]

Options:
  --output-dir PATH       Optional output root (default: same folder as source)
  --recursive             Include subdirectories
  --include GLOB          Include glob pattern (repeatable)
  --exclude GLOB          Exclude glob pattern (repeatable)
  --suffix TEXT           Output suffix before .png (default: -nobg)
  --quality LVL           low, medium, high, premium (default: premium)
  --model MODEL           nano-banana, gemini25, removebg, auto
  --overwrite             Overwrite existing output files
  --process-transparent   Re-process images that already have transparency
  --allow-rect-mask       Do not fail on suspicious rectangular masks
  --max-files N           Process only the first N discovered files
  --fail-fast             Stop after first processing failure
  --json                  Output JSON summary
  -v, --verbose           Verbose progress logs to stderr
```

Notes:
- Defaults exclude `qr-code*`, `*label*`, and existing `*-nobg.png` files.
- Helps enforce full-folder cleanup so detail images are not left with backgrounds.

### photos.py

```
python scripts/photos.py [OPTIONS]

Actions (mutually exclusive):
  --recent N        List N recent photos
  --albums          List albums
  --favorites [N]   List favorite photos
  --search PATTERN  Search by filename (use % as wildcard)
  --copy UUID       Copy photo by UUID
  --info UUID       Get photo info by UUID
  --stats           Show library statistics

Filters:
  --since DATE      Photos since date (YYYY-MM-DD)
  --until DATE      Photos until date (YYYY-MM-DD)
  --limit N         Max results (default: 25)

Options:
  -o, --output PATH  Output path for --copy
  --json             Output JSON
  -v, --verbose      Verbose output
  --library PATH     Custom Photos library path
```

## Photos.app Integration

Access photos directly from the Photos.app library via SQLite database.

**Requires**: Full Disk Access permission (System Settings > Privacy & Security)

### Examples

```bash
# List recent photos
python scripts/photos.py --recent 10

# Get library stats
python scripts/photos.py --stats

# Copy photo to working directory
python scripts/photos.py --copy "ABC123-UUID" --output ~/Desktop/photo.jpg

# Search for product photos
python scripts/photos.py --search "%product%" --limit 20

# Get photos from last week
python scripts/photos.py --since 2025-12-14 --limit 50
```

### Integration with Processing

```bash
# Get recent photo and remove background
UUID=$(python scripts/photos.py --recent 1 --json | jq -r '.[0].uuid')
python scripts/photos.py --copy "$UUID" --output /tmp/input.jpg
python scripts/process.py /tmp/input.jpg --output /tmp/nobg.png
```

## API Keys

Resolution order (used by all scripts in this skill, including `clean.py` when
called via `refresh_item_image.py`):

1. Process env (set by parent process)
2. **macOS Keychain** — `security find-generic-password -a "$USER" -s GEMINI_API_KEY -w`
3. Project `.env` at workspace root

The `~/.zshrc` auto-exports `GEMINI_API_KEY` and `NANO_BANANA_API_KEY` from
Keychain on every interactive shell, so most uses don't need to think about it.

Keys used:

```bash
GEMINI_API_KEY        # Gemini 2.5 Flash + 3.1 Flash + 3 Pro (image gen/edit)
NANO_BANANA_API_KEY   # Alias — same Gemini endpoint, separate var name for back-compat
REMOVE_BG_API_KEY     # remove.bg (optional, paid; REMOVEBG_API_KEY also accepted)
```

Set or rotate in Keychain (token never appears in shell history):

```bash
security add-generic-password -U -a "$USER" -s GEMINI_API_KEY -w '<key>' -A \
    -j "Richmond General Gemini API key"
```

## Python API

```python
from lib import create_default_router, TaskConfig, TaskType

# Create router with all models
router = create_default_router()

# Background removal
config = TaskConfig.for_remove_bg(output_path='output.png')
result = router.process('input.jpg', config)

# Image generation
config = TaskConfig.for_generate(
    prompt='A vintage typewriter',
    output_path='generated.png'
)
result = router.generate(config)

# Image editing
config = TaskConfig.for_edit(
    instruction='Remove the background',
    output_path='edited.png'
)
result = router.process('input.jpg', config)

# Photos access
from lib.photos import PhotosLibrary

library = PhotosLibrary()
photos = library.get_recent_photos(limit=10)
library.copy_photo(photos[0].uuid, '/tmp/photo.jpg')
```

## Directory Structure

```
image-processor/
├── SKILL.md
├── lib/
│   ├── __init__.py
│   ├── router.py           # Smart model routing
│   ├── photos.py           # Photos.app SQLite access
│   └── models/
│       ├── __init__.py
│       ├── base.py         # BaseModel, TaskConfig, TaskType
│       ├── nano_banana.py  # Gemini 3 Pro
│       ├── gemini25.py     # Gemini 2.5 Flash
│       ├── removebg.py     # remove.bg API
│       └── gemini_image.py # Generation/editing
└── scripts/
    ├── process.py          # Background removal CLI
    ├── generate.py         # Generation CLI
    ├── edit.py             # Editing CLI
    ├── photos.py           # Photos.app CLI
    └── status.py           # Model status
```

## Migration from Old Skills

This skill replaces:
- `gemini-chat/` - Use `scripts/process.py`
- `image-generation-skill/` - Use `scripts/generate.py`
- `image-editing-skill/` - Use `scripts/edit.py`

### rg-full-auto Integration

Update Phase 0.6 to use:

```bash
uv run --project ${CLAUDE_PLUGIN_ROOT} python \
  ${CLAUDE_PLUGIN_ROOT}/skills/image-processor/scripts/process.py \
  '/path/to/input.png' --output '/path/to/output.png'
```

## Troubleshooting

**No models available:**
- Check API keys are set: `python scripts/status.py`
- Verify keys haven't expired

**Photos.app access denied:**
- Grant Full Disk Access to Terminal/Claude Code
- System Settings > Privacy & Security > Full Disk Access

**Poor background removal:**
- Try `--quality premium`
- Use `--model removebg` for best results (paid)
- Re-run with `-v` to see mask-quality metrics and auto-recovery behavior

**Generation timeout:**
- Try `--quality fast` for quicker results
- Reduce reference image count

## Running the tests

Unit tests live in the parent `skills/` repo under `testing/unit/`. Relevant files for this skill:

- `test_image_router.py` — model selection logic, fallback chain
- `test_image_clean_downscale.py` — `clean.py` pre-Gemini downscale

Run them:

```bash
cd ~/workspace/richmondgeneral/skills
python3 -m pytest testing/unit/test_image_router.py \
                  testing/unit/test_image_clean_downscale.py -v
```

Or run the full skills test suite: `python3 -m pytest testing/unit/ -v`.
