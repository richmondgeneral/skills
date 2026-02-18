# Richmond General Skills

A comprehensive collection of AI assistant skills for managing Richmond General's vintage and antique inventory system. These skills integrate with Square Catalog, Apple ecosystem (iMessage, Contacts, Notes), and external identification databases to streamline operations.

**Repository:** `richmondgeneral/skills`
**Current Version:** v2026.02.15

## Overview

This repository houses specialized workflows ("Skills") that autonomous agents (like Claude) use to perform complex tasks. Instead of prompting for every step, you can trigger these skills with simple natural language.

## Skills Catalog

### 📦 Inventory Management
| Skill | Trigger | Purpose |
|-------|---------|---------|
| **rg-full-auto** | "new item", "sell this", "onboard" | **Main Workflow.** Complete 10-phase process including Whatnot listing and Photos archive cleanup. |
| **rg-item-update** | "update item", "change price" | Quick edits to existing items (price, description, images). |
| **catalog-classifier** | "what category?", "classify" | *(Experimental)* Automatically routes items to the correct Square category. |

### 🔍 Appraisal & Identification
| Skill | Trigger | Purpose |
|-------|---------|---------|
| **book-appraiser** | "old book", "1950 book" | specialized appraisal for pre-1970 books with Library of Congress lookup. |
| **carnival-glass-appraiser** | "carnival glass", "iridescent bowl" | Identification and valuation of pressed glass (1908-1930s). |
| **maker-mark-identifier** | "identify mark", "who made this" | Identifies pottery stamps, silver hallmarks, and furniture labels. |

### 💳 Square Integration
| Skill | Trigger | Purpose |
|-------|---------|---------|
| **square-cache** | "search cache", "catalog changes" | High-speed local cache of the Square catalog. 100x faster than API. |
| **square-crm** | "add customer", "sync contacts" | Syncs Apple Contacts with Square Customer directory. |
| **square-image-upload** | "upload image" | Handles complex multipart image uploads to Square API. |
| **product-labeler** | "make label", "print tag" | Generates thermal printer CSVs and HTML descriptions. |

### 💬 Messaging & CRM
| Skill | Trigger | Purpose |
|-------|---------|---------|
| **imessage-core** | "read texts", "reply to" | Reads and sends iMessage/SMS/RCS directly. |
| **contacts-manager** | "who is this", "lookup number" | Contact profiles, spam filtering, and context. |
| **daily-briefing** | "morning briefing", "status" | Generates a CRM status report in Apple Notes. |
| **imessage-archiver** | "archive chat", "save thread" | Saves text conversations to Notes with inline images. |

### 🖼️ Media & Utility
| Skill | Trigger | Purpose |
|-------|---------|---------|
| **image-processor** | "remove bg", "edit photo" | Unified tool for background removal, generation, and editing. |
| **photos-library** | "recent photos", "find product shots" | Queries the local macOS Photos.app library. |
| **alpaca-market-data** | "stock price", "market data" | Real-time financial market data. |
| **skill-manager** | "update skill", "registry refresh" | Meta-skill for maintaining this repository and skill metadata hygiene. |

## Usage

Skills are **model-invoked**. You do not need to run scripts manually. Simply ask the agent:

> "Process this new photo of a carnival glass bowl."
> "Who is texting me from 847-555-0199?"
> "Update the price of the 'Vintage Radio' to $45."

The agent will automatically select the correct skill and execute the workflow.

For creating new skills or major rewrites, use the canonical creator guidance:
- `/Users/scottybe/.claude/skills/.system/skill-creator/SKILL.md`

## How Skills Are Loaded

Skills work in two environments with **different loading mechanisms**:

### Claude Code (terminal)

- **Auto-discovers** `SKILL.md` files from `~/.claude/skills/*/`
- Parses YAML frontmatter (`name`, `description`, `metadata`)
- Injects matching skills as `<system-reminder>` blocks based on trigger keywords in `description`
- **Hot-reloads** on file changes — no restart needed
- Zero config required

### Claude for Mac (desktop app — chat, cowork, code modes)

- **Does NOT read** the `~/.claude/skills/` filesystem
- Skills must be packaged as `.skill` files (ZIP archives) and **installed through the Mac app UX**
- The UX handles installation and registration under the hood
- MCP servers are separately configured in `~/Library/Application Support/Claude/claude_desktop_config.json`

### Symlink

```
~/.claude/skills/ → ~/workspace/richmondgeneral/skills/
```

The git repo lives at `~/workspace/richmondgeneral/skills/`. Claude Code reads skills through the symlink. Edits to the repo are immediately available in Claude Code.

### Current MCP Servers (Claude for Mac)

These provide tool access in the Mac app independent of skills:

| Server | Type | Purpose |
|--------|------|---------|
| `mcp_square_api` | Remote (SSE) | Official Square API |
| `square_cache_mcp` | Local | MongoDB-backed Square catalog cache |
| `alpaca` | Local | Alpaca trading / market data |

## Building .skill Packages

To install or update skills in Claude for Mac, package them as `.skill` files:

```bash
# Build a single skill
./docs/build-skill.sh contacts-manager

# Build all skills
./docs/build-skill.sh --all

# Custom output directory
./docs/build-skill.sh --all --output-dir ~/Desktop
```

Output: `dist/<skill-name>-v<version>.skill`

Install by dragging the `.skill` file into Claude for Mac or using the app's skill import UX.

### Keeping Mac App Skills in Sync

1. Edit the skill source in this repo (Claude Code picks up changes automatically)
2. Rebuild: `./docs/build-skill.sh <skill-name>`
3. Re-install the `.skill` file through the Mac app UX

## Installation (Claude Code)

Skills auto-load from `~/.claude/skills/`. To update:

```bash
cd ~/workspace/richmondgeneral/skills
git pull
```

The symlink at `~/.claude/skills/` ensures Claude Code sees changes immediately.

## Dual-Target Skill Sync (Claude + Codex)

Canonical source remains this repo:

- `/Users/scottybe/workspace/richmondgeneral/skills`

Sync both local destinations from canonical source:

```bash
./docs/sync-skills.sh
```

Dry run:

```bash
./docs/sync-skills.sh --dry-run
```

Targets:

- `~/.claude/skills`
- `~/.codex/skills`

## Related Repositories

- **Items Site**: [richmondgeneral.github.io/items](https://richmondgeneral.github.io/items/) - Public gallery
- **Main Site**: [richmondgeneral.com](https://richmondgeneral.com) - Square-hosted store

---
© 2024-2026 Richmond General. All rights reserved.
