---
title: System Paths Reference
description: Canonical absolute paths for agent consistency across sessions
updated: 2026-02-15
---

# System Paths Reference

⚠️ **Critical:** All paths must be absolute. DO NOT use `~` tilde expansion.

## Primary Working Directory

```
/Users/scottybe/workspace/square/items/
```

**Purpose:** Richmond General item processing (images, HTML, QR codes)

**Structure:**
```
/Users/scottybe/workspace/square/items/
├── RG-0001/
│   ├── hero.png
│   ├── qr.png
│   └── index.html
├── RG-0002/
│   └── ...
└── template/
    └── rg-item-card-template.html
```

---

## Skills Directory

```
/Users/scottybe/.claude/skills/rg-full-auto/
```

**Structure:**
```
/Users/scottybe/.claude/skills/rg-full-auto/
├── SKILL.md
├── references/
│   ├── mcp-connectors.md
│   ├── system-paths.md
│   ├── square-catalog.md
│   ├── label-format.md
│   └── info-card-template.html
└── scripts/
    ├── remove_background.py
    ├── process_new_item.py
    └── place_files.py
```

---

## Delegated Lot Tracking Skill

```
/Users/scottybe/.claude/skills/rg-lot-tracker/
```

**Purpose:** Lot creation, cost allocation, margin validation, and ROI tracking.

---

## Upload Staging (Claude Desktop)

```
/mnt/user-data/uploads/
```

**Purpose:** Temporary location when user uploads files to Claude

**Usage:** Files must be moved to Mac working directory via Filesystem MCP

---

## Environment Variables Location

```
/Users/scottybe/.env
```

**Contains:**
- `SQUARE_ACCESS_TOKEN`
- `REMOVEBG_API_KEY`
- `LINEAR_API_KEY`
- `GEMINI_API_KEY`

**Access:** Via `osascript` with `source ~/.env` prefix

---

## Path Usage Rules

✅ **DO:**
- Use absolute paths: `/Users/scottybe/workspace/square/items/`
- Reference this file when unsure
- Validate paths exist before operations

❌ **DON'T:**
- Use `~` tilde: `~/workspace/square/items/` ❌
- Use relative paths: `../items/` ❌
- Mix path formats within same workflow
