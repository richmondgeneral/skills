---
name: skill-manager
description: Meta-skill for managing and updating Claude skills. Use when creating new skills, updating existing skills, or tracking skill versions. Triggers on "update skill", "create skill", "skill changelog", or references to skill management.
---

# Skill Manager

Meta-skill for collaboratively developing and maintaining Claude skills with Scotty.

## Quick Reference

**Skills Directory:** `/Users/scottybe/skills/`
**Git Repo:** Yes (skills folder is version controlled)

## Workflow: Updating Skills

```
1. Scotty requests change or Claude identifies improvement needed
          ↓
2. Claude reads current skill from ~/skills/<skill-name>/SKILL.md
          ↓
3. Claude makes edits using Filesystem:write_file
          ↓
4. Claude confirms changes with Scotty
          ↓
5. Scotty clicks "Save Skill" in Claude UI to sync
          ↓
6. (Optional) git commit in ~/skills/ for version history
```

**Key points:**
- Claude CAN directly write to `/Users/scottybe/skills/` via Filesystem tools
- Claude CANNOT write to `/mnt/skills/user/` (read-only on Claude's side)
- User must click "Save Skill" in UI after Claude updates local files

## Active Skills Registry

| Skill | Path | Purpose | Last Updated |
|-------|------|---------|--------------|
| **rg-inventory** | `~/skills/rg-inventory/` | Richmond General inventory workflow | 2025-11-27 |
| **vintage-appraiser** | `~/skills/vintage-appraiser/` | Maker's marks, carnival glass, pricing | - |
| **book-appraiser** | `~/skills/book-appraiser/` | Antiquarian books, LOC cross-reference | - |
| **product-labeler** | `~/skills/product-labeler/` | Thermal labels, Square descriptions | - |
| **imessage-assistant** | `~/skills/imessage-assistant/` | iMessage/RCS/SMS automation | - |
| **skill-manager** | `~/skills/skill-manager/` | This meta-skill | 2025-11-27 |

## Creating New Skills

### Directory Structure
```
~/skills/<skill-name>/
├── SKILL.md           ← Main skill file (required)
├── references/        ← Supporting docs (optional)
│   ├── api-reference.md
│   └── examples.md
└── scripts/           ← Helper scripts (optional)
    └── helper.py
```

### SKILL.md Template
```markdown
---
name: skill-name
description: Brief description for Claude to match queries. Include trigger words.
---

# Skill Title

One-line summary.

## Quick Reference

Key IDs, paths, constants.

## Workflow

Step-by-step process.

## API Reference (if applicable)

Endpoints, parameters, examples.

## References

- `references/file.md` - Description
```

### Frontmatter Rules
- `name`: lowercase, hyphenated (must match folder name)
- `description`: 1-2 sentences, include trigger keywords Claude should match on

## Changelog Format

When updating skills, add entry to `references/changelog.md`:

```markdown
## YYYY-MM-DD

### Added
- New feature or section

### Changed  
- Modified behavior or content

### Fixed
- Bug fixes or corrections

### Removed
- Deprecated content
```

## Skill File Formats

The skills directory contains mixed formats:
- **Folders** (`rg-inventory/`): Multi-file skills with SKILL.md + references
- **Single files** (`vintage-appraiser.skill`): Standalone skill files
- **Zips** (`rg-inventory.zip`): Archived/backup versions

Preferred format: **Folder structure** for maintainability.

## Commands for Claude

When asked to update a skill:

```
1. Read: Filesystem:read_text_file on ~/skills/<name>/SKILL.md
2. Edit: Filesystem:write_file with updated content
3. Confirm: Show diff or summary of changes
4. Remind: "Click 'Save Skill' in Claude UI to sync"
```

When asked to create a skill:

```
1. Create: Filesystem:create_directory for ~/skills/<name>/
2. Write: SKILL.md with frontmatter + content
3. (Optional) Create references/ subdirectory
4. Remind: "Click 'Save Skill' in Claude UI to register"
```

## Version Control

The `~/skills/` directory has git initialized. After skill updates:

```bash
cd ~/skills
git add .
git commit -m "Update <skill-name>: <brief description>"
```

This provides version history independent of Claude's UI.
