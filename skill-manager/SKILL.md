---
name: skill-manager
description: Maintain the local skills repository health and registry. Use for version bumps, metadata audits, registry refreshes, packaging checks, and cleanup across skills. For creating or rewriting skill content, delegate to the skill-creator standard first.
metadata:
  version: "1.7"
  author: scottybe
  updated: "2026-02-17"
  changelog: |
    v1.7 - Full registry refresh:
    - Updated rg-lot-tracker to 2.0 (aging, health scoring, enhanced reporting)
    - Added whatnot-create-product 1.0, catalog-classifier 2.1, whatnot-catalog/chrome 1.0
    - Added Whatnot, Appraisal, Messaging, Trading, and Deprecated skill sections
    - Reflects full 25-skill inventory

    v1.6 - Square ops skill expansion:
    - Added `square-catalog-ops` and `square-webhook-monitor` to active snapshot
    - Updated snapshot date to reflect current skill inventory

    v1.5 - Aligned with Anthropic skill-creator conventions:
    - Replaced stale static registry workflow with metadata-driven audit workflow
    - Added explicit delegation to canonical skill-creator guidance
    - Added frontmatter/structure validation checklist for all active skills
---

# Skill Manager

Repository maintenance skill for `~/.claude/skills`.

## Scope

Use this skill for:
- Skills repo hygiene (`metadata`, version drift, stale docs, packaging checks)
- Registry refreshes
- Cross-skill consistency fixes (paths, env vars, shared conventions)

Do not use this skill as the canonical source for how to design a skill from scratch.

## Canonical Skill-Creation Standard

For creating or substantially rewriting skills, follow this first:
- `/Users/scottybe/.claude/skills/.system/skill-creator/SKILL.md`

Use this skill to enforce those standards across the repository after edits.

## Required Skill Contract

Each active skill directory must have:
1. `SKILL.md` with YAML frontmatter
2. `name` and `description` fields in frontmatter
3. `metadata.version`, `metadata.author`, `metadata.updated`
4. Optional `metadata.changelog` when changes are substantive

Preferred structure:
- `references/` for deep documentation (progressive disclosure)
- `scripts/` for deterministic/repeated logic
- `assets/` for reusable output assets
- `agents/openai.yaml` when UI metadata is required

## Repository Paths

- Skills root: `~/.claude/skills/`
- Archive: `~/.claude/skills/archive/`
- Packaging helper: `~/.claude/skills/docs/build-skill.sh`
- Template: `~/.claude/skills/docs/reference/SKILL_TEMPLATE.md`

## Metadata Audit Commands

List active skills and metadata snapshot:

```bash
for d in ~/.claude/skills/*; do
  [ -d "$d" ] || continue
  b=$(basename "$d")
  case "$b" in .git|.venv|archive|docs|testing|.pytest_cache|__pycache__) continue;; esac
  f="$d/SKILL.md"
  [ -f "$f" ] || continue
  ver=$(awk '/^metadata:/{m=1} m && /version:/{gsub(/"/,"",$2); print $2; exit}' "$f")
  upd=$(awk '/^metadata:/{m=1} m && /updated:/{gsub(/"/,"",$2); print $2; exit}' "$f")
  echo "$b|${ver:-?}|${upd:-?}"
done | sort
```

Find missing required frontmatter fields:

```bash
rg -n "^name:|^description:|^metadata:|version:|author:|updated:" ~/.claude/skills/*/SKILL.md
```

## Active Skills Snapshot (2026-02-17)

### Richmond General Workflows

| Skill | Version | Updated |
|-------|---------|---------|
| `rg-full-auto` | 3.6 | 2026-02-16 |
| `rg-item-update` | 1.4 | 2026-02-16 |
| `rg-lot-tracker` | 2.0 | 2026-02-16 |
| `catalog-classifier` | 2.1 | 2026-02-16 |
| `product-labeler` | 1.1 | 2025-12-21 |

### Square Integration

| Skill | Version | Updated |
|-------|---------|---------|
| `square-cache` | 1.4 | 2026-02-17 |
| `square-catalog-ops` | 1.1 | 2026-02-17 |
| `square-chrome-control` | 1.0 | 2026-02-17 |
| `square-image-upload` | 1.5 | 2026-02-17 |
| `square-webhook-monitor` | 1.1 | 2026-02-17 |
| `square-crm` | 1.1 | 2025-12-21 |

### Whatnot

| Skill | Version | Updated |
|-------|---------|---------|
| `whatnot-create-product` | 1.0 | 2026-02-16 |
| `whatnot-chrome` | 1.0 | 2026-02-16 |
| `whatnot-catalog` | 1.0 | 2026-02-16 |

### Image / Intake

| Skill | Version | Updated |
|-------|---------|---------|
| `image-processor` | 1.3 | 2026-02-15 |
| `photos-library` | 1.2 | 2026-01-18 |

### Appraisal

| Skill | Version | Updated |
|-------|---------|---------|
| `book-appraiser` | 1.1 | 2025-12-21 |
| `carnival-glass-appraiser` | 1.1 | 2025-12-21 |
| `maker-mark-identifier` | 1.1 | 2025-12-21 |

### Messaging / CRM

| Skill | Version | Updated |
|-------|---------|---------|
| `imessage-core` | 1.1 | 2025-12-21 |
| `imessage-archiver` | 1.1 | 2025-12-21 |
| `contacts-manager` | 1.1 | 2025-12-21 |
| `daily-briefing` | 2.0 | 2025-12-22 |

### Trading

| Skill | Version | Updated |
|-------|---------|---------|
| `alpha-trader` | 2.0 | — |
| `alpaca-market-data` | 1.0 | 2026-02-14 |

### Deprecated

| Skill | Superseded By |
|-------|--------------|
| `rg-inventory-legacy` | `rg-full-auto` |
| `rg-new-item-legacy` | `rg-full-auto` |

## Maintenance Workflow

1. Run metadata snapshot command.
2. Patch target skills (frontmatter, stale paths, outdated claims).
3. Validate scripts when changed (`python3 -m py_compile` or skill tests).
4. Update this registry snapshot if versions changed.
5. Commit only intended files; avoid sweeping unrelated changes.

## Packaging

Build one skill:

```bash
~/.claude/skills/docs/build-skill.sh <skill-name>
```

Build all:

```bash
~/.claude/skills/docs/build-skill.sh --all
```

## Safety Rules

- Do not delete archived skills unless explicitly asked.
- Do not rewrite unrelated skills in bulk just for style.
- Prefer targeted, reversible changes and keep diffs small.
