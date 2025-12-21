---
name: image-generation
description: Generate images from text prompts, create artwork, visualize concepts, or produce variations of existing images. Automatically routes to Nano Banana (fast) or Nano Banana Pro (high-quality) based on complexity. Use when users want to create new images, generate logos, artwork, diagrams, or visualize ideas.
---

# Image Generation with Gemini Nano Banana

Generate high-quality images from text descriptions using Google's Gemini image generation models (Nano Banana). Supports automatic model selection, style transfer, and multi-variation generation.

## Quick Start

**Simple generation:**
```bash
python scripts/generate_image.py \
  --prompt "A vintage typewriter on a wooden desk" \
  --output result.png
```

**With style reference:**
```bash
python scripts/generate_image.py \
  --prompt "Apply this aesthetic to a mountain landscape" \
  --reference examples/vintage-style.jpg \
  --output styled-mountains.png
```

**Force high quality:**
```bash
python scripts/generate_image.py \
  --prompt "Professional product photography of ceramic mug" \
  --quality pro \
  --output product-hero.png
```

## Models

### Nano Banana (gemini-2.5-flash-image)
- **Speed**: Fast (~10-15 seconds)
- **Use for**: Quick iterations, casual creativity, batch generation
- **Quality**: High quality, suitable for most use cases

### Nano Banana Pro (gemini-3-pro-image)
- **Speed**: Slower (~20-30 seconds)
- **Use for**: Professional work, complex compositions, 4K output
- **Quality**: State-of-the-art, production-ready

### Auto Selection

The `--quality auto` flag (default) uses heuristics to choose the best model:

**Uses Pro when:**
- 8+ reference images
- Prompt contains "4k", "high quality", "professional"
- Long, detailed prompts (>200 chars with "detailed")

**Uses Fast otherwise** for speed and efficiency.

## Common Patterns

### Text-to-Image Generation

```bash
# Simple objects
python scripts/generate_image.py \
  --prompt "A blue ceramic vase with gold trim" \
  --output vase.png

# Complex scenes
python scripts/generate_image.py \
  --prompt "Cozy bookshop interior, warm lighting, overstuffed armchairs, floor-to-ceiling shelves" \
  --output bookshop.png

# Logos and graphics
python scripts/generate_image.py \
  --prompt "Minimalist logo for vintage store, art deco style, cream and gold colors" \
  --quality pro \
  --output logo.png
```

### Style Transfer

Use reference images to apply visual aesthetics:

```bash
python scripts/generate_image.py \
  --prompt "Reinterpret this subject in the reference style" \
  --reference vintage-photo.jpg \
  --reference subject.jpg \
  --output styled-result.png
```

### Multi-Variation Generation

Generate multiple versions by running script multiple times with slight prompt variations or use a loop:

```bash
for style in "vintage" "modern" "rustic"; do
  python scripts/generate_image.py \
    --prompt "Product photo of ceramic bowl, $style aesthetic" \
    --output "bowl-$style.png"
done
```

## Integration with Other Skills

### From rg-full-auto (Phase 0)

```bash
# Generate hero image for Richmond General item
python ~/.claude/skills/image-generation-skill/scripts/generate_image.py \
  --prompt "Professional product photography of ${ITEM_DESCRIPTION}, clean white background" \
  --quality pro \
  --output ~/Workspace/items/RG-XXXX/RG-XXXX-generated.png
```

### From Custom Workflows

```python
import sys
sys.path.append('~/.claude/skills/image-generation-skill/lib')

from gemini_api import GeminiAPI, save_image

api = GeminiAPI()
image_data, metadata = api.generate_image(
    prompt="Your description",
    model=GeminiAPI.MODEL_FLASH
)
save_image(image_data, "output.png")
```

## API Key Setup

The script requires `GEMINI_API_KEY` environment variable.

**Already configured** in `~/.env` (line 22):
```bash
export GEMINI_API_KEY=AIzaSyBU0wxMPqVw97UbTxhyQS187wtiKahHYh0
```

Sourced automatically by `~/.zshrc`.

## Prompting Tips

### Effective Prompts

**Be specific:**
- ❌ "a chair"
- ✅ "mid-century modern wooden chair with teal upholstery"

**Include context:**
- ❌ "book"
- ✅ "leather-bound antique book on mahogany table, soft lighting"

**Specify style:**
- ❌ "portrait"
- ✅ "portrait in 1960s Polaroid style with warm tones"

### Quality Keywords

Add these to guide Nano Banana Pro selection:
- "professional photography"
- "high detail", "detailed"
- "4K resolution"
- "production quality"

See `ADVANCED_PROMPTING.md` for comprehensive prompt engineering guide.

## Output Format

**Default**: Path to generated image
```
result.png
```

**JSON mode** (`--json` flag):
```json
{
  "model": "gemini-2.5-flash-image",
  "prompt": "A vintage typewriter on a wooden desk",
  "reference_count": 0,
  "output_path": "/Users/scottybe/result.png"
}
```

## Limitations

- **Rate limits**: Varies by API tier (free tier has lower quotas)
- **Image size**: Output varies by model (~1MP for Flash, up to 4K for Pro)
- **SynthID watermarking**: All images include invisible watermark
- **Content policy**: Subject to Google's AI content policies

## Troubleshooting

**API Key Error:**
```bash
# Verify key is set
echo $GEMINI_API_KEY

# Test with verbose output
python scripts/generate_image.py --prompt "test" --output test.png --verbose
```

**Timeout:**
- Increase timeout in `lib/gemini_api.py` (line 45)
- Try `--quality fast` for quicker generation

**Poor Results:**
- Refine prompt with more detail
- Add reference images for style guidance
- Try `--quality pro` for higher fidelity

## Examples

See `examples/` directory for working code samples:
- `text_to_image.py` - Basic generation
- `style_transfer.py` - Apply reference styles
- `multi_variation.py` - Batch generation with variations

## Related Skills

- `image-editing-skill` - Edit generated images with natural language
- `rg-full-auto` - Richmond General item workflow (uses this skill)
- `gemini-chat` - Interactive Gemini text chat (different use case)

## Technical Details

- **API**: generativelanguage.googleapis.com/v1beta
- **Timeout**: 60 seconds
- **Supported input formats**: JPEG, PNG, GIF, WEBP
- **Output format**: PNG (recommended) or JPEG
- **Max reference images**: 14 (Pro model)
