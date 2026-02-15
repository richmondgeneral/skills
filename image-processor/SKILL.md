---
name: image-processor
description: Unified image processing with background removal, generation, editing, and Photos.app integration. Auto-routes to optimal model (Nano Banana Pro, Gemini 2.5, remove.bg) based on task. Triggers on "remove background", "generate image", "edit image", "process photo", "photos library", "get from photos", or when rg-full-auto needs image processing.
metadata:
  version: "1.2"
  author: scottybe
  updated: "2026-02-15"
  changelog: |
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

Unified image processing skill combining background removal, image generation, image editing, and Photos.app library access.

## Quick Start

### Background Removal

```bash
python scripts/process.py image.jpg
python scripts/process.py image.jpg --output result.png
python scripts/process.py image.jpg --quality premium
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

### Generation Model Selection

Auto-selects Nano Banana vs Nano Banana Pro based on:
- Number of reference images (8+ = Pro)
- Keywords: "4k", "high quality", "professional"
- Prompt length and detail

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

Set in `~/.env` (sourced by `~/.zshrc`):

```bash
export GEMINI_API_KEY="your-key"        # Gemini 2.5 Flash + image gen/edit
export NANO_BANANA_API_KEY="your-key"   # Nano Banana Pro (Gemini 3)
export REMOVE_BG_API_KEY="your-key"     # remove.bg (optional, paid; REMOVEBG_API_KEY also accepted)
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
uv run --project ~/.claude/skills python \
  ~/.claude/skills/image-processor/scripts/process.py \
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
