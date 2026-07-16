#!/usr/bin/env bash
# Skills Repository Sanity Check
# Validates skill discovery, frontmatter, paths, headings, and Python syntax.

set -o pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLUGINS_DIR="$REPO_ROOT/plugins"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

CHECKS_PASSED=0
CHECKS_FAILED=0
ERRORS=()

pass() {
    echo -e "${GREEN}✅${NC} $1"
    ((CHECKS_PASSED+=1))
}

fail() {
    echo -e "${RED}❌${NC} $1"
    ERRORS+=("$1")
    ((CHECKS_FAILED+=1))
}

warn() {
    echo -e "${YELLOW}⚠️${NC}  $1"
}

info() {
    echo -e "${BLUE}ℹ️${NC}  $1"
}

if [ ! -d "$PLUGINS_DIR" ]; then
    echo "Plugins directory not found: $PLUGINS_DIR" >&2
    exit 1
fi

mapfile -d '' SKILL_FILES < <(
    find "$PLUGINS_DIR" -type f -name SKILL.md -not -path '*/archive/*' -print0 | sort -z
)

echo "🔍 Running Skills Repository Sanity Check..."
echo ""

# ============================================================================
# CHECK 1: Skill Inventory
# ============================================================================
echo "━━━ Skill Inventory ━━━"

if [ "${#SKILL_FILES[@]}" -eq 0 ]; then
    fail "No skills discovered under $PLUGINS_DIR"
else
    pass "Skill Inventory (${#SKILL_FILES[@]} skills discovered)"
fi

MANIFEST_ERRORS=0
while IFS= read -r -d '' manifest; do
    plugin_dir=$(dirname "$(dirname "$manifest")")
    if [ ! -d "$plugin_dir/skills" ]; then
        fail "Plugin manifest has no skills directory: ${plugin_dir#"$REPO_ROOT/"}"
        ((MANIFEST_ERRORS+=1))
    fi
done < <(find "$PLUGINS_DIR" -mindepth 2 -maxdepth 2 -type f -path '*/.claude-plugin/plugin.json' -print0)

if [ "$MANIFEST_ERRORS" -eq 0 ]; then
    pass "Plugin Layout (all plugin manifests resolve to skills directories)"
fi

# ============================================================================
# CHECK 2: Frontmatter
# ============================================================================
echo ""
echo "━━━ Frontmatter ━━━"

FRONTMATTER_ERRORS=0
VERSION_ERRORS=0
for skill_md in "${SKILL_FILES[@]}"; do
    relative_path=${skill_md#"$REPO_ROOT/"}

    if [ "$(head -n 1 "$skill_md")" != "---" ]; then
        fail "Missing opening YAML delimiter in $relative_path"
        ((FRONTMATTER_ERRORS+=1))
        continue
    fi

    closing_line=$(grep -n '^---$' "$skill_md" | sed -n '2{s/:.*//;p;q;}')
    if [ -z "$closing_line" ]; then
        fail "Missing closing YAML delimiter in $relative_path"
        ((FRONTMATTER_ERRORS+=1))
        continue
    fi

    frontmatter=$(sed -n "2,$((closing_line-1))p" "$skill_md")
    if ! grep -q '^name:' <<< "$frontmatter"; then
        fail "Missing 'name:' field in $relative_path"
        ((FRONTMATTER_ERRORS+=1))
    fi
    if ! grep -q '^description:' <<< "$frontmatter"; then
        fail "Missing 'description:' field in $relative_path"
        ((FRONTMATTER_ERRORS+=1))
    fi

    version=$(awk -F: '/^[[:space:]]+version:/ { value=$2; gsub(/[[:space:]"\047]/, "", value); print value; exit }' <<< "$frontmatter")
    if [ -n "$version" ] && [[ ! "$version" =~ ^[0-9]+\.[0-9]+(\.[0-9]+)?$ ]]; then
        fail "Invalid version '$version' in $relative_path (expected N.N or N.N.N)"
        ((VERSION_ERRORS+=1))
    fi
done

if [ "$FRONTMATTER_ERRORS" -eq 0 ]; then
    pass "Required Frontmatter (name and description present)"
fi
if [ "$VERSION_ERRORS" -eq 0 ]; then
    pass "Version Metadata (all declared versions are valid)"
fi

# ============================================================================
# CHECK 3: Deprecated Path References
# ============================================================================
echo ""
echo "━━━ Deprecated Path References ━━━"

BROKEN_PATHS=0
DEPRECATED_PATHS=(
    "skills/rg-new-item"
    "skills/imessage-assistant"
    "skills/image-editing-skill"
    "skills/image-generation-skill"
)

for deprecated_path in "${DEPRECATED_PATHS[@]}"; do
    matches=$(grep -rnF "$deprecated_path" "$PLUGINS_DIR" --include='*.md' --exclude-dir=archive 2>/dev/null || true)
    if [ -n "$matches" ]; then
        fail "Found references to deprecated/non-existent path '$deprecated_path':"
        while IFS= read -r line; do
            info "  $line"
        done <<< "$matches"
        ((BROKEN_PATHS+=1))
    fi
done

if [ "$BROKEN_PATHS" -eq 0 ]; then
    pass "Deprecated Path References (none found)"
fi

# ============================================================================
# CHECK 4: Duplicate Headers
# ============================================================================
echo ""
echo "━━━ Duplicate Headers ━━━"

DUPLICATE_HEADERS=0
for skill_md in "${SKILL_FILES[@]}"; do
    dupes=$(grep '^##' "$skill_md" | sort | uniq -d || true)
    if [ -n "$dupes" ]; then
        relative_path=${skill_md#"$REPO_ROOT/"}
        fail "Duplicate headers in $relative_path:"
        while IFS= read -r line; do
            info "  $line"
        done <<< "$dupes"
        ((DUPLICATE_HEADERS+=1))
    fi
done

if [ "$DUPLICATE_HEADERS" -eq 0 ]; then
    pass "Duplicate Headers (none found)"
fi

# ============================================================================
# CHECK 5: Python Syntax
# ============================================================================
echo ""
echo "━━━ Python Syntax ━━━"

PYTHON_CMD=()
if [ -n "${PYTHON:-}" ]; then
    PYTHON_CMD=("$PYTHON")
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD=(python3)
elif command -v python >/dev/null 2>&1; then
    PYTHON_CMD=(python)
elif command -v py >/dev/null 2>&1; then
    PYTHON_CMD=(py -3)
fi

mapfile -d '' PY_FILES < <(
    find "$PLUGINS_DIR" -type f -name '*.py' -not -path '*/.venv/*' -not -path '*/archive/*' -print0 | sort -z
)

PYTHON_ERRORS=0
if [ "${#PYTHON_CMD[@]}" -eq 0 ]; then
    warn "Python interpreter not found; skipped syntax validation for ${#PY_FILES[@]} files"
elif [ "${#PY_FILES[@]}" -eq 0 ]; then
    pass "Python Syntax (no Python files found)"
else
    for py_file in "${PY_FILES[@]}"; do
        if ! "${PYTHON_CMD[@]}" -m py_compile "$py_file" 2>/dev/null; then
            fail "Python syntax error in: ${py_file#"$REPO_ROOT/"}"
            ((PYTHON_ERRORS+=1))
        fi
    done

    if [ "$PYTHON_ERRORS" -eq 0 ]; then
        pass "Python Syntax (${#PY_FILES[@]} files checked)"
    fi
fi

# ============================================================================
# SUMMARY
# ============================================================================
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 SANITY CHECK SUMMARY"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo -e "Checks Passed: ${GREEN}$CHECKS_PASSED${NC}"
echo -e "Checks Failed: ${RED}$CHECKS_FAILED${NC}"
echo ""

if [ "$CHECKS_FAILED" -eq 0 ]; then
    echo -e "${GREEN}✅ ALL CHECKS PASSED${NC}"
    exit 0
fi

echo -e "${RED}❌ SANITY CHECK FAILED${NC}"
echo ""
echo "Issues found:"
for error in "${ERRORS[@]}"; do
    echo -e "  ${RED}•${NC} $error"
done
exit 1
