#!/usr/bin/env bash
#
# sync-to-claude.sh - Sync skill directories from this repo into Claude's skills path.
#
# Default target path is ~/.claude/skills (or $CLAUDE_SKILLS_DIR if set).
# This script syncs only directories that contain SKILL.md.
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd -P)"

SOURCE_DIR="$REPO_ROOT"
TARGET_DIR="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}"
DRY_RUN=0
DELETE_EXTRANEOUS=0

declare -a SKILLS=()

usage() {
    cat <<'EOF'
Usage:
  ./docs/sync-to-claude.sh [options]

Options:
  --source <dir>     Source repo directory (default: this repo root)
  --target <dir>     Target Claude skills directory (default: ~/.claude/skills or $CLAUDE_SKILLS_DIR)
  --skill <name>     Sync one skill (can be passed multiple times)
  --dry-run          Show what would change without writing files
  --delete           Remove files in each target skill dir that are not in source
  -h, --help         Show this help

Examples:
  ./docs/sync-to-claude.sh --dry-run
  ./docs/sync-to-claude.sh --skill rg-full-auto --skill rg-item-update
  ./docs/sync-to-claude.sh --source ~/workspace/skills --target ~/.claude/skills --delete
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --source)
            SOURCE_DIR="$2"
            shift 2
            ;;
        --target)
            TARGET_DIR="$2"
            shift 2
            ;;
        --skill)
            SKILLS+=("$2")
            shift 2
            ;;
        --dry-run)
            DRY_RUN=1
            shift
            ;;
        --delete)
            DELETE_EXTRANEOUS=1
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage
            exit 1
            ;;
    esac
done

if [[ ! -d "$SOURCE_DIR" ]]; then
    echo "Source directory does not exist: $SOURCE_DIR" >&2
    exit 1
fi

if ! command -v rsync >/dev/null 2>&1; then
    echo "rsync is required but not found in PATH." >&2
    exit 1
fi

mkdir -p "$TARGET_DIR"

SOURCE_REAL="$(cd "$SOURCE_DIR" && pwd -P)"
TARGET_REAL="$(cd "$TARGET_DIR" && pwd -P)"

if [[ "$SOURCE_REAL" == "$TARGET_REAL" ]]; then
    echo "Source and target are the same path: $SOURCE_REAL"
    echo "Claude is already reading skills from this location."
    exit 0
fi

if [[ ${#SKILLS[@]} -eq 0 ]]; then
    while IFS= read -r skill_name; do
        SKILLS+=("$skill_name")
    done < <(
        for candidate in "$SOURCE_DIR"/*; do
            [[ -d "$candidate" ]] || continue
            name="$(basename "$candidate")"
            [[ "$name" == "archive" ]] && continue
            [[ -f "$candidate/SKILL.md" ]] || continue
            echo "$name"
        done | sort
    )
fi

if [[ ${#SKILLS[@]} -eq 0 ]]; then
    echo "No skills found to sync from: $SOURCE_DIR" >&2
    exit 1
fi

RSYNC_OPTS=(
    -a
    --human-readable
    --exclude=.DS_Store
    --exclude=__pycache__/
    --exclude=*.pyc
    --exclude=.fuse_hidden*
)

if [[ "$DRY_RUN" -eq 1 ]]; then
    RSYNC_OPTS+=(--dry-run --itemize-changes)
fi

if [[ "$DELETE_EXTRANEOUS" -eq 1 ]]; then
    RSYNC_OPTS+=(--delete)
fi

echo "Sync source: $SOURCE_REAL"
echo "Sync target: $TARGET_REAL"
echo "Skills: ${SKILLS[*]}"
echo

SYNCED_COUNT=0
SKIPPED_COUNT=0

for skill_name in "${SKILLS[@]}"; do
    src="$SOURCE_DIR/$skill_name"
    dst="$TARGET_DIR/$skill_name"

    if [[ ! -f "$src/SKILL.md" ]]; then
        echo "Skipping '$skill_name' (no SKILL.md found at $src)" >&2
        SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
        continue
    fi

    mkdir -p "$dst"
    echo "Syncing $skill_name"
    rsync "${RSYNC_OPTS[@]}" "$src/" "$dst/"
    SYNCED_COUNT=$((SYNCED_COUNT + 1))
done

if [[ "$SYNCED_COUNT" -eq 0 ]]; then
    echo
    echo "No valid skills were synced. Check --skill names or source path." >&2
    exit 1
fi

echo
if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "Dry run complete. No files were changed."
else
    echo "Sync complete."
    echo "If Claude does not pick up changes immediately, restart Claude Desktop."
fi

echo "Summary: synced=$SYNCED_COUNT skipped=$SKIPPED_COUNT"
