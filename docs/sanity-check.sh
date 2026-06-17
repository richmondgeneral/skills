#!/bin/bash
# Skills Repository Sanity Check
# Validates documentation, metadata, paths, and Python syntax

set -o pipefail

SKILLS_DIR="$(cd "$(dirname "$0")/../plugins/richmondgeneral/skills" && pwd)"
cd "$SKILLS_DIR" || exit 1

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Counters
CHECKS_PASSED=0
CHECKS_FAILED=0
ERRORS=()

function pass() {
    echo -e "${GREEN}✅${NC} $1"
    ((CHECKS_PASSED++))
}

function fail() {
    echo -e "${RED}❌${NC} $1"
    ERRORS+=("$1")
    ((CHECKS_FAILED++))
}

function warn() {
    echo -e "${YELLOW}⚠️${NC}  $1"
}

function info() {
    echo -e "${BLUE}ℹ️${NC}  $1"
}

echo "🔍 Running Skills Repository Sanity Check..."
echo ""

# ============================================================================
# CHECK 1: Metadata Completeness
# ============================================================================
echo "━━━ Metadata Completeness ━━━"

SKILL_DIRS=$(find "$SKILLS_DIR" -maxdepth 1 -type d -not -name ".*" -not -name "docs" -not -name "archive" | grep -v "^$SKILLS_DIR$")
SKILL_COUNT=$(echo "$SKILL_DIRS" | wc -l | tr -d ' ')

MISSING_METADATA=0
for skill_dir in $SKILL_DIRS; do
    skill_name=$(basename "$skill_dir")
    skill_md="$skill_dir/SKILL.md"
    
    if [ ! -f "$skill_md" ]; then
        # gemini-chat is a stub directory, skip it
        if [ "$skill_name" != "gemini-chat" ]; then
            fail "Missing SKILL.md in $skill_name"
            ((MISSING_METADATA++))
        fi
        continue
    fi
    
    # Check for version metadata
    if ! grep -q "version:" "$skill_md"; then
        fail "Missing version metadata in $skill_name/SKILL.md"
        ((MISSING_METADATA++))
    fi
    
    # Check for author metadata
    if ! grep -q "author:" "$skill_md"; then
        fail "Missing author metadata in $skill_name/SKILL.md"
        ((MISSING_METADATA++))
    fi
done

if [ $MISSING_METADATA -eq 0 ]; then
    pass "Metadata Completeness ($SKILL_COUNT skills checked)"
fi

# ============================================================================
# CHECK 2: Path Validation
# ============================================================================
echo ""
echo "━━━ Path Validation ━━━"

BROKEN_PATHS=0

# Check for references to non-existent directories
DEPRECATED_PATTERNS=(
    "rg-new-item"
    "rg-inventory"
    "imessage-assistant"
    "image-editing-skill"
    "image-generation-skill"
)

for pattern in "${DEPRECATED_PATTERNS[@]}"; do
    matches=$(grep -rn "$pattern" "$SKILLS_DIR" --include="*.md" --exclude-dir=archive 2>/dev/null | grep -v "archive/" | grep -v "WARP_AGENT_GUIDE" | grep -v "skill-manager/SKILL.md" | grep -v "Archived" | grep -v "superseded" | grep -v "Consolidated")
    if [ -n "$matches" ]; then
        fail "Found references to deprecated/non-existent '$pattern':"
        echo "$matches" | while read -r line; do
            info "  $line"
        done
        ((BROKEN_PATHS++))
    fi
done

if [ $BROKEN_PATHS -eq 0 ]; then
    pass "Path Validation (no broken references)"
fi

# ============================================================================
# CHECK 3: Version Consistency
# ============================================================================
echo ""
echo "━━━ Version Consistency ━━━"

VERSION_MISMATCHES=0

# Read skill-manager registry
REGISTRY_FILE="$SKILLS_DIR/skill-manager/SKILL.md"

# Check a few key skills
declare -A EXPECTED_VERSIONS=(
    ["daily-briefing"]="v2.0"
    ["skill-manager"]="v1.3"
    ["rg-full-auto"]="v2.3"
    ["image-processor"]="v1.0"
    ["photos-library"]="v1.0"
)

for skill in "${!EXPECTED_VERSIONS[@]}"; do
    expected="${EXPECTED_VERSIONS[$skill]}"
    
    # Get version from SKILL.md
    actual=$(grep "version:" "$SKILLS_DIR/$skill/SKILL.md" 2>/dev/null | head -1 | awk '{print $2}' | tr -d '"')
    
    # Get version from skill-manager registry
    registry_version=$(grep -A 1 "| \*\*$skill\*\*" "$REGISTRY_FILE" 2>/dev/null | grep -o "v[0-9]\+\.[0-9]\+" | head -1)
    
    if [ "$actual" != "${expected#v}" ]; then
        fail "Version mismatch for $skill: SKILL.md has v$actual, expected $expected"
        ((VERSION_MISMATCHES++))
    elif [ -n "$registry_version" ] && [ "$registry_version" != "$expected" ]; then
        fail "Version mismatch for $skill: registry has $registry_version, SKILL.md has v$actual"
        ((VERSION_MISMATCHES++))
    fi
done

if [ $VERSION_MISMATCHES -eq 0 ]; then
    pass "Version Consistency (checked ${#EXPECTED_VERSIONS[@]} critical skills)"
fi

# ============================================================================
# CHECK 4: Skill Count Accuracy
# ============================================================================
echo ""
echo "━━━ Skill Count Accuracy ━━━"

# Count actual skills (dirs with SKILL.md)
ACTUAL_SKILL_COUNT=$(find "$SKILLS_DIR" -maxdepth 2 -name "SKILL.md" -not -path "*/archive/*" | wc -l | tr -d ' ')

# Check README.md claim
README_CLAIM=$(grep -o "[0-9]\+ AI assistant skills" "$SKILLS_DIR/README.md" | grep -o "[0-9]\+")

if [ "$README_CLAIM" != "$ACTUAL_SKILL_COUNT" ]; then
    fail "Skill count mismatch: README.md claims $README_CLAIM, actual count is $ACTUAL_SKILL_COUNT"
else
    pass "Skill Count Accuracy (README claims $README_CLAIM, actual is $ACTUAL_SKILL_COUNT)"
fi

# ============================================================================
# CHECK 5: Duplicate Headers
# ============================================================================
echo ""
echo "━━━ Duplicate Headers ━━━"

DUPLICATE_HEADERS=0
for skill_md in $(find "$SKILLS_DIR" -maxdepth 2 -name "SKILL.md" -not -path "*/archive/*"); do
    dupes=$(grep "^##" "$skill_md" | sort | uniq -d)
    if [ -n "$dupes" ]; then
        skill_name=$(basename "$(dirname "$skill_md")")
        fail "Duplicate headers in $skill_name/SKILL.md:"
        echo "$dupes" | while read -r line; do
            info "  $line"
        done
        ((DUPLICATE_HEADERS++))
    fi
done

if [ $DUPLICATE_HEADERS -eq 0 ]; then
    pass "Duplicate Headers (none found)"
fi

# ============================================================================
# CHECK 6: Python Syntax
# ============================================================================
echo ""
echo "━━━ Python Syntax ━━━"

PYTHON_ERRORS=0
PY_FILES=$(find "$SKILLS_DIR" -name "*.py" -not -path "*/.venv/*" -not -path "*/archive/*" -type f)
PY_COUNT=$(echo "$PY_FILES" | grep -c "\.py$")

for py_file in $PY_FILES; do
    if ! python3 -m py_compile "$py_file" 2>/dev/null; then
        fail "Python syntax error in: $py_file"
        ((PYTHON_ERRORS++))
    fi
done

if [ $PYTHON_ERRORS -eq 0 ]; then
    pass "Python Syntax ($PY_COUNT files checked)"
else
    fail "Python Syntax Errors ($PYTHON_ERRORS files failed)"
fi

# ============================================================================
# CHECK 7: YAML Frontmatter
# ============================================================================
echo ""
echo "━━━ YAML Frontmatter ━━━"

YAML_ERRORS=0
for skill_md in $(find "$SKILLS_DIR" -maxdepth 2 -name "SKILL.md" -not -path "*/archive/*"); do
    skill_name=$(basename "$(dirname "$skill_md")")
    
    # Basic YAML structure check
    if ! grep -q "^---$" "$skill_md"; then
        fail "Missing YAML frontmatter delimiters in $skill_name/SKILL.md"
        ((YAML_ERRORS++))
        continue
    fi
    
    # Check for required fields
    if ! grep -q "^name:" "$skill_md"; then
        fail "Missing 'name:' field in $skill_name/SKILL.md frontmatter"
        ((YAML_ERRORS++))
    fi
    
    if ! grep -q "^description:" "$skill_md"; then
        fail "Missing 'description:' field in $skill_name/SKILL.md frontmatter"
        ((YAML_ERRORS++))
    fi
done

if [ $YAML_ERRORS -eq 0 ]; then
    pass "YAML Frontmatter (all SKILL.md files valid)"
fi

# ============================================================================
# CHECK 8: Required Files
# ============================================================================
echo ""
echo "━━━ Required Files ━━━"

MISSING_FILES=0
for skill_dir in $SKILL_DIRS; do
    skill_name=$(basename "$skill_dir")
    
    # Skip gemini-chat stub
    if [ "$skill_name" = "gemini-chat" ]; then
        continue
    fi
    
    if [ ! -f "$skill_dir/SKILL.md" ]; then
        fail "Missing SKILL.md in $skill_name/"
        ((MISSING_FILES++))
    fi
done

if [ $MISSING_FILES -eq 0 ]; then
    pass "Required Files (all skills have SKILL.md)"
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

if [ $CHECKS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ ALL CHECKS PASSED${NC}"
    echo ""
    echo "Repository is ready for commit and push."
    exit 0
else
    echo -e "${RED}❌ SANITY CHECK FAILED${NC}"
    echo ""
    echo "Issues found:"
    for error in "${ERRORS[@]}"; do
        echo -e "  ${RED}•${NC} $error"
    done
    echo ""
    echo "Please fix the issues above before pushing to remote."
    exit 1
fi
