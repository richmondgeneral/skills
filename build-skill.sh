#!/usr/bin/env bash
#
# build-skill.sh - Package a skill directory as a ZIP file for Claude
#
# Usage:
#   ./build-skill.sh <skill-name>
#   ./build-skill.sh --all
#
# Examples:
#   ./build-skill.sh imessage-assistant
#   ./build-skill.sh --all
#
# Output:
#   Creates ZIP files in archive/ directory
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ARCHIVE_DIR="$SCRIPT_DIR/archive"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Print colored message
log_info() {
    echo -e "${GREEN}✓${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
}

log_error() {
    echo -e "${RED}✗${NC} $1" >&2
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
    local skill_dir="$SCRIPT_DIR/$skill_name"
    
    echo "Building skill: $skill_name"
    
    # Validate skill
    if ! validate_skill "$skill_dir"; then
        return 1
    fi
    
    # Create archive directory if it doesn't exist
    mkdir -p "$ARCHIVE_DIR"
    
    # Output ZIP file
    local zip_file="$ARCHIVE_DIR/${skill_name}.zip"
    
    # Remove old ZIP if it exists
    if [[ -f "$zip_file" ]]; then
        rm "$zip_file"
    fi
    
    # Create ZIP file (exclude hidden files, __pycache__, etc.)
    (cd "$SCRIPT_DIR" && zip -r "$zip_file" "$skill_name" \
        -x "*.pyc" \
        -x "*__pycache__*" \
        -x "*.DS_Store" \
        -x "*/.git*" \
        -x "*/node_modules/*" \
        -x "*/.vscode/*" \
        -x "*/.idea/*" \
        > /dev/null)
    
    # Get file size
    local size=$(du -h "$zip_file" | cut -f1)
    
    log_info "Created $zip_file ($size)"
    
    return 0
}

# Build all skills
build_all() {
    echo "Building all skills..."
    echo
    
    local success_count=0
    local error_count=0
    
    # Find all directories with SKILL.md
    for skill_dir in "$SCRIPT_DIR"/*/; do
        # Skip if not a directory or if it's archive/
        if [[ ! -d "$skill_dir" ]] || [[ "$(basename "$skill_dir")" == "archive" ]]; then
            continue
        fi
        
        # Check if it has SKILL.md
        if [[ -f "$skill_dir/SKILL.md" ]]; then
            local skill_name=$(basename "$skill_dir")
            
            if build_skill "$skill_name"; then
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

# Main script
main() {
    if [[ $# -eq 0 ]]; then
        echo "Usage: $0 <skill-name> | --all"
        echo
        echo "Available skills:"
        for skill_dir in "$SCRIPT_DIR"/*/; do
            if [[ -f "$skill_dir/SKILL.md" ]]; then
                echo "  - $(basename "$skill_dir")"
            fi
        done
        exit 1
    fi
    
    if [[ "$1" == "--all" ]]; then
        build_all
    else
        build_skill "$1"
    fi
}

main "$@"
