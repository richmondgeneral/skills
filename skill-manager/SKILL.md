---
name: skill-manager
description: Meta-skill for managing and updating Claude skills. Use when creating new skills, updating existing skills, or tracking skill versions. Triggers on "update skill", "create skill", "skill changelog", or references to skill management.
metadata:
  version: "1.1"
  updated: "2025-12-21"
  changelog: |
    v1.1 - Registry overhaul:
    - Added all RG workflow skills (rg-full-auto, rg-new-item, rg-item-update)
    - Added messaging skills (imessage-core, contacts-manager, daily-briefing)
    - Organized registry by category
    - Added experimental/archive section
    - Note about Filesystem path case sensitivity
---

# Skill Manager

Meta-skill for collaboratively developing and maintaining Claude skills with Scotty.

## Quick Reference

**Skills Directory:** `~/.claude/skills/`
**Git Repo:** github.com/richmondgeneral/skills (version controlled)
**Last synced:** 2025-12-21

## Workflow: Updating Skills

```
1. Scotty requests change or Claude identifies improvement needed
          ↓
2. Claude reads current skill from ~/.claude/skills/<skill-name>/SKILL.md
          ↓
3. Claude makes edits using Filesystem:write_file (or osascript if path issues)
          ↓
4. Claude confirms changes with Scotty
          ↓
5. Git commit and push to preserve version history
          ↓
6. (Optional) Scotty clicks "Save Skill" in Claude UI to sync to /mnt/skills/user/
```

**Key points:**
- Claude CAN directly write to `~/.claude/skills/` via Filesystem tools
- Claude CANNOT write to `/mnt/skills/user/` (read-only on Claude's side)
- **⚠️ Path case sensitivity:** Filesystem tools may fail with "file not found" due to case mismatch. Fallback: use osascript with python/sed for reliable edits.

---

## Active Skills Registry

### Richmond General Workflows

| Skill | Version | Purpose | Last Updated |
|-------|---------|---------|--------------|
| **rg-full-auto** | v2.2 | End-to-end item onboarding (8 phases) | 2025-12-21 |
| **rg-new-item** | - | Simplified new item flow | 2025-12-20 |
| **rg-item-update** | - | Quick edits to existing items | 2025-12-20 |
| **rg-inventory** | - | Inventory management (legacy) | 2025-12-20 |

### Appraisal & Identification

| Skill | Version | Purpose | Last Updated |
|-------|---------|---------|--------------|
| **book-appraiser** | - | Antiquarian books, LOC cross-reference | 2025-12-19 |
| **carnival-glass-appraiser** | - | Pressed iridescent glass 1908-1930s | 2025-12-19 |
| **maker-mark-identifier** | - | Pottery, silver, furniture marks | 2025-12-19 |

### Square Integration

| Skill | Version | Purpose | Last Updated |
|-------|---------|---------|--------------|
| **square-cache** | - | MongoDB cache for catalog (100x faster) | 2025-12-19 |
| **square-image-upload** | - | Image upload via multipart form data | 2025-12-19 |
| **square-crm** | - | Square customer sync from contacts | 2025-12-19 |
| **product-labeler** | - | Thermal labels, Square descriptions | 2025-12-19 |

### Messaging & CRM

| Skill | Version | Purpose | Last Updated |
|-------|---------|---------|--------------|
| **imessage-core** | - | Read/send iMessage, RCS, SMS | 2025-12-20 |
| **contacts-manager** | - | Contact lookup, spam filtering, profiles | 2025-12-20 |
| **daily-briefing** | - | Morning CRM briefing to Apple Notes | 2025-12-20 |

### Meta / Utility

| Skill | Version | Purpose | Last Updated |
|-------|---------|---------|--------------|
| **skill-manager** | v1.1 | This skill - registry & management | 2025-12-21 |

### Experimental / Inactive

| Skill | Status | Notes |
|-------|--------|-------|
| **catalog-classifier** | Experimental | Auto-categorization |
| **gemini-chat** | Experimental | Gemini API integration |
| **image-editing-skill** | Inactive | Image manipulation |
| **image-generation-skill** | Inactive | AI image generation |
| **imessage-archiver** | Inactive | Message export/backup |

**Archived:** `archive/` folder contains deprecated skills

---

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
metadata:
  version: "1.0"
  author: scottybe
  updated: "YYYY-MM-DD"
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
- `metadata.version`: Semver-ish (v1.0, v1.1, v2.0)
- `metadata.changelog`: Inline changelog for quick reference

---

## Changelog Format

For complex skills, maintain `references/changelog.md`:

```markdown
## YYYY-MM-DD - vX.X

### Added
- New feature or section

### Changed  
- Modified behavior or content

### Fixed
- Bug fixes or corrections

### Removed
- Deprecated content
```

For simpler skills, inline changelog in frontmatter metadata is sufficient.

---

## .skill File Format Specification

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

---

## Commands for Claude

### When asked to update a skill:

```
1. Read: Filesystem:read_file on ~/.claude/skills/<skill>/SKILL.md
2. Edit: Filesystem:write_file with updated content
   - If "file not found" due to path case: use osascript + python/sed
3. Confirm: Show summary of changes
4. Commit: git add, commit, push in ~/.claude/skills/
5. Update: Bump version in this registry if significant change
```

### When asked to create a skill:

```
1. Create: Filesystem:create_directory for ~/.claude/skills/<skill>/
2. Write: SKILL.md with frontmatter + content
3. (Optional) Create references/ and scripts/ subdirectories
4. Commit: git add, commit, push
5. Register: Add to Active Skills Registry in this file
```

### When doing postmortem on workflow:

```
1. Identify issues from the run
2. Propose skill updates
3. Get user approval
4. Update skill(s)
5. Update this registry with new version/date
6. Git commit all changes
```

---

## Version Control

The `~/.claude/skills/` directory is git-controlled:

```bash
cd ~/.claude/skills
git add .
git commit -m "<skill-name> vX.X: <brief description>"
git push origin main
```

Remote: `github.com/richmondgeneral/skills`
