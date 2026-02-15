# Agent & Developer Guide

**Target Audience:** AI Agents (Claude, Warp) and Developers maintaining the skills.
**Scope:** Architecture, Standards, Maintenance, and Safety.

## Core Mandates

1.  **Conventions:** Adhere to existing project styles (Python/Bash).
2.  **Environment Awareness:** Distinguish between **Container** (Agent runtime) and **Host** (macOS).
3.  **Safety:** Never delete user data without confirmation. Explain destructive actions.
4.  **Metadata:** All skills must have valid YAML frontmatter (v1.1 standard).

## System Architecture

### Dual Environment Model
The skills operate across a boundary between the AI's container and the User's Mac:

*   **Container (`/mnt/skills/`):** Where the agent runs logic. Can read/write text files.
*   **Host Mac (`~/.claude/skills/`):** Where the actual execution happens via `osascript` or `ssh`.
    *   **Rule:** **Binary files** (images, PDFs) cannot be moved easily between environments. Process them *in place* on the Host using `image-processor` or `osascript`.
    *   **Rule:** **Text files** (Code, CSV, HTML, MD) can be read/written directly by the agent using Filesystem tools.

### Directory Structure

```
~/.claude/skills/
├── <skill-name>/
│   ├── SKILL.md           # DEFINITION (Required)
│   ├── references/        # DOCS (Optional)
│   └── scripts/           # CODE (Optional - Python/Bash)
├── docs/                  # Global documentation
├── archive/               # Deprecated skills
└── .venv/                 # Shared Python environment
```

## Skill Definition Standard (Metadata v1.1)

Every `SKILL.md` **MUST** start with this YAML frontmatter:

```yaml
---
name: skill-name-kebab-case
description: Clear, trigger-rich description. Include keywords like "onboard", "price check", "lookup".
allowed-tools: Read, Grep, Glob, Bash, WebFetch  # Optional: Restrict tool access
metadata:
  version: "1.X"
  author: scottybe
  updated: "YYYY-MM-DD"
  changelog: |
    v1.X - Brief change summary
---
```

**Key Fields:**
*   `name`: Directory name, kebab-case.
*   `description`: The **most important field**. Used by the router to select the skill. Be verbose with triggers.
*   `allowed-tools`: Security feature. Use for read-only skills (`contacts-manager`, `book-appraiser`).

## Development Workflow

### Python Environment
All Python scripts run in a shared `uv` environment.
**Execution Pattern:**
```bash
uv run --project ~/.claude/skills python ~/.claude/skills/<skill>/scripts/script.py
```

### Creating a New Skill
1.  Create directory: `mkdir <skill-name>`
2.  Create `SKILL.md` with standard frontmatter.
3.  (Optional) Add scripts/references.
4.  Register in `skill-manager/SKILL.md`.
5.  Git commit.

### Updating Documentation
Run the audit checklist to ensure compliance:

1.  **Metadata Check:** Does `SKILL.md` have `version`, `author`, `updated`?
2.  **Trigger Check:** Are the description keywords accurate?
3.  **Path Check:** Are paths relative (`~/.claude/skills/`) or absolute for Host execution?
4.  **Cleanup:** Remove `__pycache__` and `.DS_Store`.

## Maintenance Guide

### Deprecation Protocol
1.  Move skill folder to `archive/`.
2.  Update `skill-manager/SKILL.md` registry (move to Archived section).
3.  Update `SKILL_UPDATE_PLAN.md` if part of a larger refactor.

### Versioning
*   **Minor (1.1 -> 1.2):** content updates, prompt tweaks.
*   **Major (1.0 -> 2.0):** Breaking changes, new scripts, new dependencies.

### Common Gotchas
*   **Path Case Sensitivity:** The Filesystem tool on Linux is case-sensitive. macOS is usually case-insensitive but can report paths differently (`/Users/` vs `/users/`). Always verify paths.
*   **Apple Notes:** Inline images require sequential attachment with delays (see `imessage-archiver`).
*   **Square API:** Image uploads require multipart form data (use `square-image-upload` script, NOT standard MCP).

## Troubleshooting

*   **"File not found":** Check for `~` expansion. Agent tools might need absolute paths.
*   **"Permission denied":** Check macOS Full Disk Access for the terminal/agent application.
*   **Script fails:** Ensure `uv` is installed and the shared venv is healthy (`uv sync`).
