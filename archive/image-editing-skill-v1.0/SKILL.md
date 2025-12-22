---
name: image-editing
description: Edit existing images using natural language instructions. Change colors, add/remove objects, modify styles, resize, combine multiple images, or add text overlays. Supports iterative refinement. Use when users want to modify, enhance, transform, or combine existing images.
metadata:
  version: "1.0"
  author: scottybe
  created: "2024-12-20"
---

# Image Editing with Gemini Nano Banana

Edit existing images using natural language instructions. Powered by Google's Gemini Nano Banana image models with advanced scene understanding and editing capabilities.

## Quick Start

**Simple edits:**
```bash
python scripts/edit_image.py \
  --input photo.jpg \
  --instruction "remove the background" \
  --output result.png
```

**Style changes:**
```bash
python scripts/edit_image.py \
  --input landscape.jpg \
  --instruction "change to sunset lighting with warm tones" \
  --output sunset.png
```

**Multi-image composition:**
```bash
python scripts/edit_image.py \
  --input subject.jpg \
  --instruction "place this subject in the reference scene" \
  --reference background.jpg \
  --output composite.png
```

## Common Edit Types

### Object Manipulation

**Add objects:**
```bash
python scripts/edit_image.py \
  --input room.jpg \
  --instruction "add a vintage lamp on the side table" \
  --output room-with-lamp.png
```

**Remove objects:**
```bash
python scripts/edit_image.py \
  --input photo.jpg \
  --instruction "remove the person in the background" \
  --output cleaned.png
```

**Replace objects:**
```bash
python scripts/edit_image.py \
  --input kitchen.jpg \
  --instruction "replace the white cabinets with dark wood" \
  --output kitchen-dark.png
```

### Style and Aesthetic Changes

**Lighting:**
```bash
python scripts/edit_image.py \
  --input portrait.jpg \
  --instruction "add dramatic side lighting like a film noir" \
  --output noir-portrait.png
```

**Color grading:**
```bash
python scripts/edit_image.py \
  --input landscape.jpg \
  --instruction "apply vintage 1970s color palette with warm tones" \
  --output vintage-landscape.png
```

**Artistic style:**
```bash
python scripts/edit_image.py \
  --input photo.jpg \
  --instruction "transform to watercolor painting style" \
  --output watercolor.png
```

### Text Overlays

Nano Banana excels at generating legible text within images:

```bash
python scripts/edit_image.py \
  --input poster.jpg \
  --instruction 'add the text "GRAND OPENING" in bold art deco font at the top' \
  --quality pro \
  --output poster-with-text.png
```

### Multi-Image Composition

Combine up to 14 images (input + 13 references):

```bash
python scripts/edit_image.py \
  --input subject.jpg \
  --instruction "place subject in the reference environment with the reference style" \
  --reference environment.jpg \
  --reference style-guide.jpg \
  --output composite.png
```

## Integration with Other Skills

### From rg-full-auto (Product Photography)

```bash
# Edit product photo after background removal
python ~/.claude/skills/image-editing-skill/scripts/edit_image.py \
  --input ~/Workspace/items/RG-XXXX/RG-XXXX-hero.png \
  --instruction "add soft drop shadow and adjust lighting for professional look" \
  --output ~/Workspace/items/RG-XXXX/RG-XXXX-final.png
```

### Chain with image-generation

```bash
# Generate base image
python ~/.claude/skills/image-generation-skill/scripts/generate_image.py \
  --prompt "minimalist logo design" \
  --output base-logo.png

# Then refine it
python scripts/edit_image.py \
  --input base-logo.png \
  --instruction "add gold metallic finish and emboss effect" \
  --output final-logo.png
```

## Iterative Editing

Edit images multiple times for refinement:

```bash
# First edit
python scripts/edit_image.py \
  --input original.jpg \
  --instruction "make the sky more dramatic" \
  --output v1.png

# Second edit
python scripts/edit_image.py \
  --input v1.png \
  --instruction "enhance the colors in the foreground" \
  --output v2.png

# Final touch
python scripts/edit_image.py \
  --input v2.png \
  --instruction "add slight vignette around edges" \
  --output final.png
```

## Effective Instructions

### Be Specific

**Vague:**
```
--instruction "make it better"
```

**Specific:**
```
--instruction "increase brightness by 20%, add warmth to the tones, and soften the shadows"
```

### Describe Desired Result

**What to avoid:**
```
--instruction "change the background"
```

**Better:**
```
--instruction "replace the background with a minimalist grey gradient"
```

### Use Visual Language

**Effective instructions:**
- "Add soft bokeh blur to the background"
- "Adjust to golden hour lighting"
- "Make the subject pop with increased contrast"
- "Apply matte finish aesthetic"

See `EDIT_PATTERNS.md` for comprehensive editing patterns and examples.

## Quality Settings

### Auto (Default)

Automatically selects model based on complexity:
- Complex compositions (8+ refs) → Pro
- Text rendering → Pro
- Simple edits → Fast

### Fast (Nano Banana)

Best for:
- Quick iterations
- Simple color/lighting adjustments
- Single-object edits
- Batch processing

### Pro (Nano Banana Pro)

Best for:
- Multi-image composition (8+ references)
- High-fidelity text rendering
- Complex scene manipulation
- Production/professional work

## API Key Setup

Requires `GEMINI_API_KEY` environment variable.

**Already configured** in `~/.env` (line 22):
```bash
export GEMINI_API_KEY=AIzaSyBU0wxMPqVw97UbTxhyQS187wtiKahHYh0
```

Automatically sourced by `~/.zshrc`.

## Output Format

**Default**: Path to edited image
```
result.png
```

**JSON mode** (`--json` flag):
```json
{
  "model": "gemini-2.5-flash-image",
  "instruction": "remove the background",
  "input_image": "photo.jpg",
  "reference_count": 0,
  "output_path": "/Users/scottybe/result.png"
}
```

## Limitations

- **Rate limits**: Varies by API tier
- **Max references**: 14 images total (input + 13 refs)
- **SynthID watermarking**: All outputs include invisible watermark
- **Character consistency**: Good but not perfect across multiple edits
- **Content policy**: Subject to Google's AI policies

## Troubleshooting

**Edit didn't apply:**
- Make instruction more specific
- Try adding `--quality pro` for complex edits
- Break into smaller, incremental edits

**Poor quality:**
- Use `--quality pro` for important edits
- Provide reference images for style guidance
- Simplify instruction (one change at a time)

**Timeout:**
- Reduce number of reference images
- Try `--quality fast`
- Increase timeout in `lib/gemini_api.py`

## Examples

See `examples/` directory:
- `object_replacement.py` - Swap elements in images
- `style_adaptation.py` - Change image aesthetics
- `text_overlay.py` - Add legible text to images

## Related Skills

- `image-generation-skill` - Generate base images from scratch
- `rg-full-auto` - Richmond General workflow (Phase 2 image processing)
- `gemini-chat` - Interactive text analysis (different use case)

## Technical Details

- **API**: generativelanguage.googleapis.com/v1beta
- **Timeout**: 60 seconds
- **Supported formats**: JPEG, PNG, GIF, WEBP
- **Output format**: PNG (preserves transparency) or JPEG
- **Shared library**: `lib/gemini_api.py` (symlinked from image-generation-skill)
