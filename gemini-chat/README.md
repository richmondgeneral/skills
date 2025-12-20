# Gemini Chat - Multi-Model Auto Image Processor

Smart, unified interface for AI-powered background removal with automatic model routing.

## 🚀 Quick Start

### CLI
```bash
# Check model status
python3 chat.py status

# Process image (auto-selects best model)
python3 chat.py process image.jpg

# Specify output
python3 chat.py process image.jpg --output result.png

# Use specific model
python3 chat.py process image.jpg --model nano-banana
```

### Web UI
```bash
# Start web interface
python3 web_ui.py

# Opens at http://localhost:7860
```

## 📦 Models

| Model | Confidence | Speed | Cost | Status |
|-------|-----------|-------|------|--------|
| 🍌 **Nano Banana Pro** (Gemini 3) | 98% | ~8s | Free | ✅ Default |
| **Gemini 2.5 Flash** | 95% | ~8s | Free | ✅ Fallback |
| **remove.bg** | Premium | ~3s | $0.009 | ⚪ Optional |

## 🔑 Setup

Set API keys in your environment:

```bash
export NANO_BANANA_API_KEY="your-key-here"
export GEMINI_API_KEY="your-key-here"
export REMOVE_BG_API_KEY="your-key-here"  # Optional
```

## ✨ Features

**Smart Routing:**
- Auto-selects optimal model based on quality, cost, availability
- Fallback chain: Nano Banana → Gemini 2.5 → remove.bg
- Quality-aware scoring (low/medium/high/premium)

**CLI:**
- `process` - Process single image
- `status` - Show model health and stats
- Multiple quality modes
- Explicit model selection

**Web UI:**
- Drag & drop image upload
- Real-time processing
- Confidence/time/cost metrics
- Beautiful purple theme
- Mobile-friendly

## 📁 Structure

```
gemini-chat/
├── chat.py          # CLI interface
├── web_ui.py        # Gradio web UI
├── router.py        # Smart routing
├── models/
│   ├── base.py      # Abstract base
│   ├── nano_banana.py
│   ├── gemini25.py
│   └── removebg.py
└── SKILL.md         # Full documentation
```

## 🧪 Testing

```bash
# CLI test
python3 chat.py process /tmp/test-item.jpeg --output /tmp/test.png

# Web UI test
python3 web_ui.py
# Upload image at http://localhost:7860
```

## 📊 Results

**Test Image (Military Trunk):**
- Model: Nano Banana Pro (auto-selected)
- Confidence: 98%
- Time: 10.5s
- Cost: Free

## 🔗 Links

- **Repository:** github.com:richmondgeneral/skills.git
- **Commits:** 
  - `e22f381` - CLI implementation
  - `fad95c8` - Web UI
- **Documentation:** [SKILL.md](SKILL.md)

## 📝 Usage Examples

### Python API
```python
from models import TaskConfig, NanaBananaModel

model = NanaBananaModel()
task = TaskConfig(task_type='remove-bg', quality_mode='high')
result = model.process_image('input.jpg', task)

print(f"Confidence: {result.confidence:.1%}")
print(f"Output: {result.output_path}")
```

### Batch Processing
```bash
for img in *.jpg; do
    python3 chat.py process "$img" --output "processed/${img%.jpg}-nobg.png"
done
```

## 🎯 Next Steps

- [ ] Interactive REPL mode
- [ ] Batch processing in web UI
- [ ] Before/after comparison slider
- [ ] Analytics dashboard
- [ ] Config file support
- [ ] Deploy to Hugging Face Spaces

## 💡 Tips

- **Default:** Auto-mode uses Nano Banana Pro (best free quality)
- **Speed:** Use remove.bg with `--model removebg` for fastest results
- **Quality:** Use `--quality premium` for 98%+ confidence
- **Cost:** Free models preferred by default

---

Built with ❤️ using Nano Banana Pro (Gemini 3), Gemini 2.5 Flash, and remove.bg
