---
name: skill-name-kebab-case
description: What this skill does, when it should trigger, and key user phrases that should route here.
metadata:
  version: "1.0"
  author: scottybe
  updated: "YYYY-MM-DD"
  changelog: |
    v1.0 - Initial version.
---

# Skill Title

One-sentence purpose.

## Scope

Use this skill for:
- Trigger/use case 1
- Trigger/use case 2

Do not use this skill for:
- Out-of-scope case 1

## Quick Reference

- Path(s): `~/.claude/skills/<skill-name>/`
- Critical IDs/constants/env vars

## Workflow

1. Step 1 with required inputs.
2. Step 2 with concrete command/tool pattern.
3. Step 3 with expected output and validation.

## Validation

Run quick checks before returning:

```bash
# Example
python3 -m py_compile ~/.claude/skills/<skill-name>/scripts/*.py
```

## References

- `references/topic.md` - Load only when needed for deep details.
