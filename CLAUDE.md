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
| `rg-full-auto/` | 8-phase item onboarding workflow |
| `rg-item-update/` | Quick edits to existing catalog items |
| `book-appraiser/` | Antiquarian book appraisal |
| `carnival-glass-appraiser/` | Carnival glass identification 1908-1930s |
| `maker-mark-identifier/` | Pottery, silver, furniture marks |
| `square-cache/` | MongoDB-cached Square catalog |
| `square-image-upload/` | Image upload via multipart form |
| `imessage-core/` | Read/send iMessage, RCS, SMS |
| `contacts-manager/` | Contact lookup and profiles |
| `skill-manager/` | Meta-skill for managing skills |

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
