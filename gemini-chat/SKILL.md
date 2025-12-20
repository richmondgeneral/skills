---
name: gemini-chat
description: Multi-model image processing router. Auto-selects optimal model (Gemini 3 Nano Banana Pro, Gemini 2.5 Flash, remove.bg) based on task, quality, and cost. Use for background removal, image analysis, and enhancement. Triggers on "remove background", "process image", "image enhancement", or when rg-full-auto needs background removal.
metadata:
  version: "1.0"
  author: scottybe
---

# Gemini Chat - Multi-Model Auto Image Processor

Smart, unified interface for image processing that automatically routes tasks to optimal models based on quality, cost, and availability.

## Models

### 🍌 Nano Banana Pro (Gemini 3)
- **Confidence:** 98%
- **Speed:** ~8s
- **Cost:** Free
- **Tasks:** remove-bg, analyze, enhance
- **API Key:** `NANO_BANANA_API_KEY`

### Gemini 2.5 Flash  
- **Confidence:** 95%
- **Speed:** ~8.4s
- **Cost:** Free
- **Tasks:** remove-bg, analyze
- **API Key:** `GEMINI_API_KEY`

### remove.bg
- **Confidence:** Premium
- **Speed:** ~2.8s
- **Cost:** $0.009/image
- **Tasks:** remove-bg
- **API Key:** `REMOVE_BG_API_KEY`

## Usage

### Basic (Auto-mode)

```bash
# Auto-selects best model (default: Nano Banana Pro)
python3 chat.py process image.jpg

# With custom output path
python3 chat.py process image.jpg --output processed.png

# High quality mode
python3 chat.py process image.jpg --quality high
```

### Explicit Model Selection

```bash
# Use Nano Banana Pro
python3 chat.py process image.jpg --model nano-banana

# Use Gemini 2.5 Flash
python3 chat.py process image.jpg --model gemini25

# Use remove.bg (paid)
python3 chat.py process image.jpg --model removebg
```

### Tasks

```bash
# Background removal (default)
python3 chat.py process image.jpg --task remove-bg

# Image analysis (future)
python3 chat.py process image.jpg --task analyze

# Enhancement (future)
python3 chat.py process image.jpg --task enhance
```

### Status

```bash
# Check model health and stats
python3 chat.py status
```

**Output:**
```
Model Health:
  ✓ NanaBananaModel
     Quality: 98.0% | Avg Time: 7.9s | Cost: free
  ✓ Gemini25FlashModel
     Quality: 95.0% | Avg Time: 8.4s | Cost: free
```

## Smart Routing

The router automatically selects the best model based on:

1. **Task capability** - Model supports the requested task
2. **Quality requirements** - Meets quality threshold
3. **Cost preferences** - Prefers free models by default
4. **Health status** - Model API is available
5. **Performance score** - Quality + speed + cost optimization

### Fallback Chain

If primary model fails, automatically falls back:
```
Nano Banana Pro (98%, free, 7.9s)
  ↓ if unavailable
Gemini 2.5 Flash (95%, free, 8.4s)
  ↓ if unavailable
remove.bg (premium, paid, 2.8s)
```

## Quality Modes

| Mode | Threshold | Use Case |
|------|-----------|----------|
| **low** | 85% | Quick previews |
| **medium** | 90% | Standard processing |
| **high** | 95% | Production quality (default) |
| **premium** | 98% | Premium results |

## Integration Examples

### Python

```python
from models import TaskConfig, NanaBananaModel

# Initialize model
model = NanaBananaModel()

# Create task
task = TaskConfig(
    task_type='remove-bg',
    quality_mode='high',
    output_path='output.png'
)

# Process
result = model.process_image('input.jpg', task)

if result.success:
    print(f"Confidence: {result.confidence:.1%}")
    print(f"Output: {result.output_path}")
```

### Shell Script

```bash
#!/bin/bash
# Batch process all JPEGs

for img in *.jpg; do
    python3 ~/.claude/skills/gemini-chat/chat.py process "$img" \
        --output "processed/${img%.jpg}-nobg.png"
done
```

### rg-full-auto Integration

```bash
# Replace Phase 0b manual remove.bg call
python3 ~/.claude/skills/gemini-chat/chat.py process \
    assets/working-images/item.jpeg \
    --output assets/working-images/item-nobg.png \
    --quality high
```

## API Keys Setup

```bash
# Add to ~/.zshrc
export NANO_BANANA_API_KEY="your-key-here"
export GEMINI_API_KEY="your-key-here"
export REMOVE_BG_API_KEY="your-key-here"  # Optional

# Reload
source ~/.zshrc
```

## Architecture

```
chat.py (CLI)
  ├── router.py (Smart routing)
  ├── models/
  │   ├── base.py (Abstract base)
  │   ├── nano_banana.py (Gemini 3)
  │   ├── gemini25.py (Gemini 2.5 Flash)
  │   └── removebg.py (remove.bg API)
  └── commands/ (Future: REPL, batch)
```

## Future Enhancements

- [ ] Interactive REPL mode
- [ ] Batch processing with parallel execution
- [ ] Config file support (~/.gemini-chat-config.yaml)
- [ ] Rate limit tracking
- [ ] Cost budgets and alerts
- [ ] Image enhancement tasks
- [ ] Analysis and tagging
- [ ] Local rembg integration

## Performance

| Model | Avg Time | Quality | Cost | Best For |
|-------|----------|---------|------|----------|
| Nano Banana Pro | 7.9s | 98% | Free | Default choice |
| Gemini 2.5 Flash | 8.4s | 95% | Free | Fallback |
| remove.bg | 2.8s | Premium | Paid | Speed priority |

## Testing

```bash
# Test with sample image
python3 chat.py process /tmp/test-item.jpeg --output /tmp/test-auto.png

# Check status
python3 chat.py status

# Verify output
ls -lh /tmp/test-auto.png
```

## Troubleshooting

**No models available:**
- Check API keys are set in environment
- Verify keys have not been revoked
- Test API access manually

**Poor quality results:**
- Increase quality mode: `--quality premium`
- Try specific model: `--model removebg`
- Check input image resolution

**Slow processing:**
- Use `--prefer fast` for speed priority
- Consider remove.bg for fastest results
- Check network connection

## Support

For issues or questions, check:
- Model status: `python3 chat.py status`
- API key validity
- Network connectivity
- Image file format (JPEG/PNG supported)
