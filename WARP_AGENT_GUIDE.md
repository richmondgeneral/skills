# Warp Agent Documentation Scrub Guide

Instructions for AI agents (Warp, Claude, etc.) to audit and clean up documentation across repositories.

## Quick Start

```bash
# Clone if needed
cd ~/.claude/skills

# Run audit
./scripts/doc-audit.sh  # (or use manual checks below)
```

## Audit Checklist

### 1. YAML Frontmatter Validation

Every SKILL.md must have:

```yaml
---
name: skill-name
description: Clear trigger-based description
metadata:
  version: "X.Y"
  author: scottybe
  updated: "YYYY-MM-DD"  # Optional but recommended
---
```

**Check command:**
```bash
for skill in */SKILL.md; do
  if ! grep -q "^metadata:" "$skill"; then
    echo "MISSING METADATA: $skill"
  fi
  if ! grep -q "version:" "$skill"; then
    echo "MISSING VERSION: $skill"
  fi
done
```

### 2. Stale Reference Detection

Search for deprecated skill names:

| Deprecated | Current |
|------------|---------|
| `imessage-assistant` | `imessage-core` or `contacts-manager` |
| `rg-inventory` | `rg-full-auto` |
| `rg-new-item` | `rg-full-auto` |

**Check command:**
```bash
grep -r "imessage-assistant\|rg-inventory\|rg-new-item" */SKILL.md --include="*.md"
```

### 3. False Limitation Detection

Search for outdated limitation claims:

```bash
# Common false limitation patterns
grep -rn "403.*token lacks\|KNOWN LIMITATION.*403\|Manual upload.*recommended\|token lacks.*scope" */SKILL.md
```

**Known false claims to remove:**
- "MCP token lacks ITEMS_WRITE scope" (image uploads work)
- "Manual upload recommended" (API works)
- "403 Forbidden on image upload" (was timing/ordering issue)

### 4. Duplicate Section Detection

```bash
# Find duplicate headers
for file in */SKILL.md; do
  echo "=== $file ==="
  grep "^##" "$file" | sort | uniq -d
done
```

### 5. Path Consistency

Standardize paths:
- Use `~/.claude/skills/` (not `/Users/scottybe/skills/`)
- Use absolute paths in osascript: `/Users/scottybe/...`

```bash
# Find mixed path styles
grep -rn "/Users/scottybe/skills/" */SKILL.md
```

### 6. Version Bump Protocol

When making fixes:

1. Update `metadata.version` (increment minor: 1.2 → 1.3)
2. Update `metadata.updated` date
3. Commit with descriptive message
4. Push to origin

**Commit message format:**
```
fix: [skill-name] vX.Y - brief description

- Change 1
- Change 2

Verified by [method]
```

## Fix Patterns

### Adding Missing Metadata

```yaml
# Add after description field
metadata:
  version: "1.0"
  author: scottybe
  created: "2024-12-20"
```

### Fixing Stale References

```bash
# sed replacement
sed -i '' 's/imessage-assistant/imessage-core/g' SKILL.md
sed -i '' 's/iMessage-assistant/contacts-manager/g' SKILL.md
```

### Removing False Limitations

Replace:
```markdown
**⚠️ KNOWN LIMITATION:** Direct API image upload returns 403...
```

With:
```markdown
**✅ WORKING:** Use `square-image-upload` skill via osascript (verified YYYY-MM-DD).
```

## Validation Commands

### Full Audit Script

```bash
#!/bin/bash
cd ~/.claude/skills

echo "=== METADATA CHECK ==="
for skill in */SKILL.md; do
  version=$(grep "version:" "$skill" | head -1)
  if [ -z "$version" ]; then
    echo "❌ $skill - NO VERSION"
  else
    echo "✅ $skill - $version"
  fi
done

echo ""
echo "=== STALE REFERENCES ==="
grep -rn "imessage-assistant" */SKILL.md || echo "✅ None found"

echo ""
echo "=== FALSE LIMITATIONS ==="
grep -rn "token lacks\|Manual upload.*recommended" */SKILL.md || echo "✅ None found"

echo ""
echo "=== DUPLICATE HEADERS ==="
for file in */SKILL.md; do
  dups=$(grep "^##" "$file" | sort | uniq -d)
  if [ -n "$dups" ]; then
    echo "❌ $file: $dups"
  fi
done
echo "✅ Check complete"
```

## Cross-Team Patterns

### Linear Issue Updates

After fixing documentation:

1. Find related Linear issues
2. Add comment with changes made
3. Close if fully resolved
4. Link commits in comment

**Search patterns:**
```
Linear:list_issues query="stale references"
Linear:list_issues query="documentation audit"
Linear:list_issues query="skill cleanup"
```

### Git Commit Best Practices

```bash
# Stage only relevant files
git add skill-name/SKILL.md

# Commit with context
git commit -m "fix: skill-name vX.Y - description

- Specific change 1
- Specific change 2

Closes: TVM-XXX"

# Push
git push origin main
```

## Common Gotchas

1. **Don't trust old error messages** - Test before documenting limitations
2. **Check all files** - One skill may reference another incorrectly
3. **Verify with API** - Don't assume what works/doesn't work
4. **Bump versions** - Every change needs version increment
5. **Update Linear** - Close issues when work is done

## Example Session

```bash
# 1. Run audit
cd ~/.claude/skills
grep -rn "imessage-assistant" */SKILL.md

# 2. Fix findings
sed -i '' 's/imessage-assistant/imessage-core/g' square-crm/SKILL.md

# 3. Bump version
# Edit SKILL.md: version: "1.1" → "1.2"

# 4. Commit
git add square-crm/SKILL.md
git commit -m "fix: square-crm v1.2 - update stale reference

- imessage-assistant → imessage-core"
git push

# 5. Update Linear
# Add comment to related issue, close if done
```

## Contact

Questions? Check:
- `skill-manager/SKILL.md` - Meta-skill for managing skills
- `rg-full-auto/references/mcp-connectors.md` - MCP capabilities
- Linear project: Skills Consolidation & Cleanup
