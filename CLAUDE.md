# CLAUDE.md

## Project Overview

Richmond General Skills - A collection of 20+ AI assistant skills for managing Richmond General's vintage and antique inventory system. Integrates with Square Catalog API, Apple ecosystem (iMessage, Contacts, Notes), MongoDB, and external services.

**Repository**: `richmondgeneral/skills`
**Python**: 3.11+ managed by `uv`

## Quick Commands

```bash
# Run Python scripts
uv run --project ~/.claude/skills python <script-path>

# Build skill as ZIP
./docs/build-skill.sh <skill-name>
./docs/build-skill.sh --all

# Linting
uv run ruff check .
```

## Directory Structure

| Directory | Purpose |
|-----------|---------|
| **Richmond General Inventory** | |
| `rg-full-auto/` | 8-phase item onboarding workflow (appraisal → Square → labels) |
| `rg-item-update/` | Quick edits to existing catalog items (price, description, images) |
| `catalog-classifier/` | Route items to correct Square category/brand/tier |
| `product-labeler/` | Generate thermal printer labels (CSV for Print Master) |
| **Appraisal & Identification** | |
| `book-appraiser/` | Antiquarian book appraisal, editions, valuation |
| `carnival-glass-appraiser/` | Carnival glass identification 1908-1930s |
| `maker-mark-identifier/` | Pottery, silver, furniture, jewelry marks |
| **Square Integration** | |
| `square-cache/` | MongoDB-cached catalog with change tracking |
| `square-image-upload/` | Image upload via multipart form API |
| `square-crm/` | Sync contacts with Square customers |
| **Apple Ecosystem** | |
| `imessage-core/` | Read/send iMessage, RCS, SMS |
| `imessage-archiver/` | Archive conversations to Apple Notes |
| `contacts-manager/` | Contact lookup, profiles, spam filtering |
| `daily-briefing/` | Morning briefing with CRM status to Notes |
| **Image Processing** | |
| `image-processor/` | Unified processing: bg removal, generation, editing, Photos.app access |
| **Meta** | |
| `skill-manager/` | Create/update skills, track versions |
| `archive/` | Superseded skills (gemini-chat, image-*-skill, rg-new-item, rg-inventory) |
| `docs/` | Build scripts, documentation |

## Skill Structure

Every skill follows this pattern:

```
<skill-name>/
├── SKILL.md              # Required - YAML frontmatter + content
├── references/           # Optional - API docs, style guides
└── scripts/              # Optional - Python helper scripts
```

## SKILL.md Frontmatter

```yaml
---
name: skill-name
description: Trigger-based description with keywords
metadata:
  version: "X.Y"
  author: scottybe
  updated: "YYYY-MM-DD"
  changelog: |
    vX.Y - description
---
```

**Version bumps required for ANY change** - even documentation fixes.

## Environment Architecture

Two environments exist:
- **Claude's container**: `/mnt/user-data/uploads/`, `/mnt/skills/`, Python
- **User's macOS**: `~/.claude/skills/`, `~/.env`, git repos, binary tools

**Rule**: Text files (HTML, CSV, MD) use Filesystem tools; Binary files (PNG, JPEG) use osascript.

## Key Conventions

- **Paths**: Use `~/.claude/skills/` for relative; absolute for osascript
- **SKU format**: RG-XXXX (sequential, zero-padded)
- **Square Location ID**: `B87BAEZ0NWV34`
- **API Version**: Square v2025-10-16
- **Env vars**: `SQUARE_ACCESS_TOKEN`, `REMOVEBG_API_KEY` in `~/.env`

## Git Conventions

```
[skill-name] vX.Y: Short description

# Example:
skill-manager v1.1: Complete registry overhaul
rg-full-auto v2.2: Add image viewing step
```

## Dependencies

Managed in root `pyproject.toml`:
- requests, pymongo, qrcode[pil], pillow, google-generativeai

Lock file: `uv.lock` for reproducible builds.

## Skill Routing

Skills are auto-routed based on trigger keywords in their `description` field. Examples:
- "Square cache" or "catalog changes" → `square-cache`
- "new item" or "onboard" → `rg-full-auto`
- "update item" or "change price" → `rg-item-update`
