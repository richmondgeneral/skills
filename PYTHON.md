# Python Environment for Richmond General Skills

All Python scripts in this skills directory share a common virtual environment managed by **uv**.

## Quick Reference

**Run any skill script from anywhere:**
```bash
uv run --project ~/.claude/skills python ~/.claude/skills/<skill>/scripts/<script>.py <args>
```

**Examples:**
```bash
# Upload image to Square
uv run --project ~/.claude/skills python ~/.claude/skills/square-image-upload/scripts/upload_image.py \
  --image ~/path/to/image.jpg --item-id ITEM_ID --primary

# Remove background
uv run --project ~/.claude/skills python ~/.claude/skills/rg-new-item/scripts/remove_background.py \
  input.jpg output.png

# Cache operations
uv run --project ~/.claude/skills python ~/.claude/skills/square-cache/scripts/cache_wrapper.py
```

## For Claude/Agents

When executing Python scripts via osascript, use this pattern:
```applescript
do shell script "source ~/.local/bin/env && uv run --project ~/.claude/skills python ~/.claude/skills/<skill>/scripts/<script>.py <args>"
```

## Dependencies

All shared dependencies are in `pyproject.toml`:
- requests (HTTP client)
- pymongo (MongoDB for square-cache)
- qrcode + pillow (QR code generation)
- google-generativeai (Gemini for image processing)

## Adding Dependencies

```bash
cd ~/.claude/skills
uv add <package-name>
```

## Environment Setup

uv was installed to `~/.local/bin/`. The PATH is configured in `~/.zshrc`:
```bash
source $HOME/.local/bin/env
```

Python version: 3.13+ (managed by uv, not pyenv)
