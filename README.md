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

## Installation

Skills reside in `~/.claude/skills/`. To update or install:

```bash
cd ~/.claude/skills
git pull
```

If your git repo lives elsewhere and you want to deploy into Claude's load path:

```bash
cd /path/to/skills-repo
./docs/sync-to-claude.sh --target ~/.claude/skills
```

Preview without writing files:

```bash
./docs/sync-to-claude.sh --target ~/.claude/skills --dry-run
```

## Related Repositories

- **Items Site**: [richmondgeneral.github.io/items](https://richmondgeneral.github.io/items/) - Public gallery
- **Main Site**: [richmondgeneral.com](https://richmondgeneral.com) - Square-hosted store

---
© 2024-2026 Richmond General. All rights reserved.
