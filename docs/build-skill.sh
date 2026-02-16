#!/usr/bin/env bash
#
# build-skill.sh - Package skill directories as .skill files for Claude for Mac
#
# Usage:
#   ./docs/build-skill.sh <skill-name>        # Build one skill
#   ./docs/build-skill.sh --all               # Build all skills
#   ./docs/build-skill.sh --all --output-dir ~/Desktop  # Custom output
#
# Output:
#   Creates .skill files (ZIP archives) in dist/ directory
#   Filename format: <skill-name>-v<version>.skill
#
# Install:
#   Drag the .skill file into Claude for Mac, or use the app's skill import UX.
#   Claude Code (terminal) does NOT need .skill files — it auto-discovers from
#   ~/.claude/skills/ via the filesystem.
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DIST_DIR="${DIST_DIR:-$SKILLS_ROOT/dist}"

# Skip these directories when building --all
SKIP_DIRS=".git|.venv|.claude|archive|dist|docs|testing|.pytest_cache|__pycache__|node_modules"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}✓${NC} $1"; }
log_warn()  { echo -e "${YELLOW}⚠${NC} $1"; }
log_error() { echo -e "${RED}✗${NC} $1" >&2; }

# Extract version from SKILL.md YAML frontmatter
extract_version() {
    local skill_md="$1"
    awk '/^metadata:/{m=1} m && /version:/{gsub(/"/,"",$2); print $2; exit}' "$skill_md"
}

# Validate that a directory is a valid skill
validate_skill() {
    local skill_dir="$1"

    if [[ ! -d "$skill_dir" ]]; then
        log_error "Directory not found: $skill_dir"
        return 1
    fi

    if [[ ! -f "$skill_dir/SKILL.md" ]]; then
        log_error "SKILL.md not found in $skill_dir"
        return 1
    fi

    # Check for YAML frontmatter
    if ! head -n 1 "$skill_dir/SKILL.md" | grep -q "^---$"; then
        log_error "SKILL.md must start with YAML frontmatter (---)"
        return 1
    fi

    return 0
}

# Build a single skill
build_skill() {
    local skill_name="$1"
    local skill_dir="$SKILLS_ROOT/$skill_name"

    echo "Building skill: $skill_name"

    if ! validate_skill "$skill_dir"; then
        return 1
    fi

    # Extract version for filename
    local version
    version=$(extract_version "$skill_dir/SKILL.md")
    if [[ -z "$version" ]]; then
        log_warn "No version found in frontmatter, using 'unknown'"
        version="unknown"
    fi

    mkdir -p "$DIST_DIR"

    local out_file="$DIST_DIR/${skill_name}-v${version}.skill"

    # Remove old file if it exists
    rm -f "$out_file"

    # Create .skill (ZIP) file
    (cd "$SKILLS_ROOT" && zip -r "$out_file" "$skill_name" \
        -x "*.pyc" \
        -x "*__pycache__*" \
        -x "*.DS_Store" \
        -x "*/.git*" \
        -x "*/node_modules/*" \
        -x "*/.vscode/*" \
        -x "*/.idea/*" \
        > /dev/null)

    local size
    size=$(du -h "$out_file" | cut -f1)

    log_info "Created $out_file ($size)"
    return 0
}

# Build all skills
build_all() {
    echo "Building all skills from $SKILLS_ROOT ..."
    echo

    local success_count=0
    local error_count=0

    for skill_dir in "$SKILLS_ROOT"/*/; do
        [[ -d "$skill_dir" ]] || continue

        local dir_name
        dir_name=$(basename "$skill_dir")

        # Skip non-skill directories
        if echo "$dir_name" | grep -qE "^($SKIP_DIRS)$"; then
            continue
        fi

        if [[ -f "$skill_dir/SKILL.md" ]]; then
            if build_skill "$dir_name"; then
                ((success_count++))
            else
                ((error_count++))
            fi
            echo
        fi
    done

    echo "Summary: ${success_count} skills built successfully"
    if [[ $error_count -gt 0 ]]; then
        log_warn "$error_count skills failed"
        return 1
    fi

    return 0
}

# Main
main() {
    # Parse --output-dir flag
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --output-dir)
                DIST_DIR="$2"
                shift 2
                ;;
            --all)
                build_all
                return $?
                ;;
            -h|--help)
                echo "Usage: $0 <skill-name> | --all [--output-dir <path>]"
                echo
                echo "Options:"
                echo "  --all              Build all skills"
                echo "  --output-dir DIR   Output directory (default: dist/)"
                echo "  -h, --help         Show this help"
                echo
                echo "Available skills:"
                for skill_dir in "$SKILLS_ROOT"/*/; do
                    if [[ -f "$skill_dir/SKILL.md" ]]; then
                        local name ver
                        name=$(basename "$skill_dir")
                        ver=$(extract_version "$skill_dir/SKILL.md")
                        echo "  - $name (v${ver:-?})"
                    fi
                done
                exit 0
                ;;
            *)
                build_skill "$1"
                return $?
                ;;
        esac
    done

    echo "Usage: $0 <skill-name> | --all [--output-dir <path>]"
    exit 1
}

main "$@"
