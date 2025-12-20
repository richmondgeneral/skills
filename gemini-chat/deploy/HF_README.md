---
title: Gemini Chat - AI Background Removal
emoji: 🍌
colorFrom: purple
colorTo: blue
sdk: gradio
sdk_version: 4.0.0
app_file: app.py
pinned: false
license: mit
---

# 🍌 Gemini Chat - AI Background Removal

Smart, multi-model background removal with automatic routing across multiple AI models.

## Features

- **Drag & Drop Upload** - Easy image upload interface
- **Auto Model Selection** - Intelligently selects the best model for your image
- **Multiple Models:**
  - 🍌 Nano Banana Pro (Gemini 3): 98% confidence, ~8s, free
  - Gemini 2.5 Flash: 95% confidence, ~8s, free  
  - remove.bg: Premium quality, ~3s, $0.009/image
- **Real-time Processing** - See results instantly
- **Free to Use** - Default models are completely free

## How to Use

1. Upload an image
2. Select a model (or let it auto-select)
3. Choose quality mode (High or Premium)
4. Click "🚀 Remove Background"
5. Download your processed image!

## Technology

- **Framework:** Gradio 4.0
- **Backend:** Python with smart routing logic
- **Models:** Nano Banana Pro (Gemini 3), Gemini 2.5 Flash, remove.bg API

## Repository

**Source Code:** https://github.com/richmondgeneral/skills/tree/main/gemini-chat

**Commits:**
- `e22f381` - CLI implementation
- `fad95c8` - Web UI
- `f704379` - Documentation

## Performance

**Test Results:**
- Model: Nano Banana Pro (auto-selected)
- Confidence: 98%
- Processing Time: ~10s
- Cost: Free

---

Built with ❤️ using Nano Banana Pro (Gemini 3), Gemini 2.5 Flash, and remove.bg
