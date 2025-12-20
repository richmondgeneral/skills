---
name: skill-manager
description: Meta-skill for managing and updating Claude skills. Use when creating new skills, updating existing skills, or tracking skill versions. Triggers on "update skill", "create skill", "skill changelog", or references to skill management.
metadata:
  version: "1.0"
---

# Skill Manager

Meta-skill for collaboratively developing and maintaining Claude skills with Scotty.

## Quick Reference

**Skills Directory:** `/Users/scottybe/skills/`
**Git Repo:** Yes (skills folder is version controlled)
**Last synced:** 2025-12-19 (testing Save Skill button trigger)

## Workflow: Updating Skills

```
1. Scotty requests change or Claude identifies improvement needed
          ↓
2. Claude reads current skill from ~/.claude/skills/<skill-name>/SKILL.md
          ↓
3. Claude makes edits using Filesystem:write_file
          ↓
4. Claude confirms changes with Scotty
          ↓
5. Scotty clicks "Save Skill" in Claude UI to sync
          ↓
6. (Optional) git commit in ~/.claude/skills/ for version history
```

**Key points:**
- Claude CAN directly write to `/Users/scottybe/skills/` via Filesystem tools
- Claude CANNOT write to `/mnt/skills/user/` (read-only on Claude's side)
- User must click "Save Skill" in UI after Claude updates local files

## Active Skills Registry

| Skill | Path | Purpose | Last Updated |
|-------|------|---------|--------------|
| **rg-inventory** | `~/.claude/skills/rg-inventory/` | Richmond General inventory workflow | 2025-12-20 |
| **carnival-glass-appraiser** | `~/.claude/skills/carnival-glass-appraiser/` | Carnival glass pattern ID & valuation | 2025-12-19 |
| **maker-mark-identifier** | `~/.claude/skills/maker-mark-identifier/` | Pottery, silver, furniture maker's marks | 2025-12-19 |
| **book-appraiser** | `~/.claude/skills/book-appraiser/` | Antiquarian books, LOC cross-reference | - |
| **product-labeler** | `~/.claude/skills/product-labeler/` | Thermal labels, Square descriptions | - |
| **square-cache** | `~/.claude/skills/square-cache/` | MongoDB cache for Square catalog (100x faster) | 2025-12-19 |
| **square-image-upload** | `~/.claude/skills/square-image-upload/` | Image upload via multipart form data | 2025-12-19 |
| **imessage-assistant** | `~/.claude/skills/imessage-assistant/` | iMessage/RCS/SMS automation, CRM briefings | 2025-12-19 |
| **square-crm** | `~/.claude/skills/square-crm/` | Square customer sync from contacts.md | 2025-12-19 |
| **skill-manager** | `~/.claude/skills/skill-manager/` | This meta-skill | 2025-12-19 |

## Creating New Skills

### Directory Structure
```
~/.claude/skills/<skill-name>/
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
- **Zips** (`.zip` archives): Archived/backup versions

Preferred format: **Folder structure** for maintainability.

**Deprecated skills:** vintage-appraiser (replaced by carnival-glass-appraiser + maker-mark-identifier)

## .skill File Format Specification

**Discovery Date:** 2025-12-19

The `.skill` file format is a ZIP archive with a specific internal structure:

```
.skill file = ZIP archive renamed to .skill extension
              └── skill-name/
                  └── SKILL.md
```

### Creating Exportable .skill Files

To trigger Claude's "Copy to your skills" button:

```bash
# 1. Create folder with SKILL.md
mkdir skill-name
cp SKILL.md skill-name/

# 2. ZIP the folder (not just the file)
zip -r skill-name.zip skill-name/

# 3. Rename .zip to .skill
mv skill-name.zip skill-name.skill

# 4. Use present_files tool to offer download
# Claude will show "Copy to your skills" button
```

### Critical Requirements

- ✅ **Must** have folder as top-level in ZIP
- ✅ **Must** contain `SKILL.md` inside folder
- ✅ **Must** use `.skill` extension
- ❌ **Won't work** if SKILL.md is at ZIP root
- ❌ **Won't work** without folder wrapper

### Workflow: Export Updated Skill

When Scotty asks to export a skill:

```
1. Create temporary folder: mkdir <skill-name>
2. Copy SKILL.md: cp ~/.claude/skills/<skill-name>/SKILL.md <skill-name>/
3. ZIP folder: zip -r <skill-name>.zip <skill-name>/
4. Rename: mv <skill-name>.zip <skill-name>.skill
5. Present: Use present_files to trigger download button
6. Cleanup: rm -rf <skill-name>/ (optional)
```

## Commands for Claude

When asked to update a skill:

```
1. Read: Filesystem:read_text_file on ~/.claude/skills/<n>/SKILL.md
2. Edit: Filesystem:write_file with updated content
3. Confirm: Show diff or summary of changes
4. Remind: "Click 'Save Skill' in Claude UI to sync"
```

When asked to create a skill:

```
1. Create: Filesystem:create_directory for ~/.claude/skills/<n>/
2. Write: SKILL.md with frontmatter + content
3. (Optional) Create references/ subdirectory
4. Remind: "Click 'Save Skill' in Claude UI to register"
```

## Version Control

The `~/.claude/skills/` directory has git initialized. After skill updates:

```bash
cd ~/skills
git add .
git commit -m "Update <skill-name>: <brief description>"
```

This provides version history independent of Claude's UI.
