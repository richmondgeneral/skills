# Skills Update Plan

Based on Anthropic's latest Claude Code documentation (November 2025), this plan outlines updates needed to align with current best practices.

---

## Summary of Key Changes from Anthropic

| Change | Impact | Priority |
|--------|--------|----------|
| `allowed-tools` frontmatter field | New security feature to restrict tool access | Medium |
| Progressive disclosure architecture | Skills should separate metadata/instructions/resources | Low (already doing this) |
| Model-invoked discovery emphasis | Descriptions must include trigger keywords | High (audit needed) |
| Plugin distribution format | Skills can be bundled as plugins | Optional |
| MCP SSE deprecated → HTTP | Remote MCP servers should use HTTP transport | Low |
| Agent SDK package renamed | `claude-code-sdk` → `claude-agent-sdk` | N/A (not using SDK) |

---

## Current Skill Audit

### Format Compliance

| Skill | Has Frontmatter | Has `name` | Has `description` | Has `version` | Needs Update |
|-------|-----------------|------------|-------------------|---------------|--------------|
| rg-full-auto | ✅ | ✅ | ✅ | ✅ v2.2 | Minor |
| skill-manager | ✅ | ✅ | ✅ | ✅ v1.1 | Minor |
| contacts-manager | ✅ | ✅ | ✅ | ✅ v1.0 | Minor |
| imessage-core | ✅ | ✅ | ✅ | ✅ v1.0 | Minor |
| book-appraiser | ✅ | ✅ | ✅ | ✅ v1.0 | Minor |
| carnival-glass-appraiser | ✅ | ✅ | ✅ | ✅ | Minor |
| maker-mark-identifier | ✅ | ✅ | ✅ | ✅ | Minor |
| square-cache | ✅ | ✅ | ✅ | ✅ | Minor |
| square-image-upload | ✅ | ✅ | ✅ | ✅ | Minor |
| square-crm | ✅ | ✅ | ✅ | ✅ | Minor |
| product-labeler | ✅ | ✅ | ✅ | ✅ | Minor |
| daily-briefing | ✅ | ✅ | ✅ | ✅ | Minor |
| imessage-archiver | ✅ | ✅ | ✅ | ✅ | Minor |
| rg-new-item | ✅ | ✅ | ✅ | ✅ | Consider deprecation |
| rg-item-update | ✅ | ✅ | ✅ | ✅ | Minor |
| rg-inventory | ✅ | ✅ | ✅ | ✅ | Consider deprecation |
| catalog-classifier | ✅ | ✅ | ✅ | ✅ | Experimental |
| gemini-chat | ✅ | ✅ | ✅ | ✅ | Experimental |
| image-editing-skill | ✅ | ✅ | ✅ | ✅ | Inactive |
| image-generation-skill | ✅ | ✅ | ✅ | ✅ | Inactive |

**Finding:** All skills already have proper YAML frontmatter. Good foundation.

---

## Required Updates

### 1. Add `allowed-tools` to Security-Sensitive Skills

**Priority: Medium**

Skills that should NOT have write access:

```yaml
# contacts-manager - READ ONLY
allowed-tools: Read, Grep, Glob, Bash

# book-appraiser - READ + WEB
allowed-tools: Read, Grep, Glob, WebFetch, WebSearch

# carnival-glass-appraiser - READ + WEB
allowed-tools: Read, Grep, Glob, WebFetch, WebSearch

# maker-mark-identifier - READ + WEB
allowed-tools: Read, Grep, Glob, WebFetch, WebSearch
```

Skills that need write access (don't restrict):
- rg-full-auto (creates files, runs scripts)
- square-image-upload (uploads images)
- imessage-core (sends messages)
- product-labeler (generates labels)

### 2. Update `metadata.author` Field

**Priority: Low**

Add missing `author` field to skills that lack it:

```yaml
metadata:
  version: "1.0"
  author: scottybe
  updated: "2025-12-21"
```

Skills missing author:
- contacts-manager
- imessage-core
- book-appraiser
- (audit all others)

### 3. Add `metadata.updated` Field

**Priority: Low**

Several skills have version but no `updated` date. Add for tracking:

```yaml
metadata:
  version: "1.0"
  author: scottybe
  updated: "2025-12-21"
```

### 4. Description Trigger Keyword Audit

**Priority: High**

Review and enhance descriptions to improve discovery:

| Skill | Current Triggers | Suggested Additions |
|-------|------------------|---------------------|
| rg-full-auto | "new item", "full workflow", "onboard" | "list item", "sell this", "add to store" |
| book-appraiser | "old/antique/vintage books" | "rare book", "first edition", "signed copy" |
| carnival-glass-appraiser | "carnival glass" | "iridescent glass", "antique glass bowl", "Fenton", "Northwood" |
| contacts-manager | "phone number", "contact info" | "who is this", "lookup number", "unknown caller" |
| imessage-core | "check messages", "send text" | "text back", "reply to", "message from" |

### 5. Deprecation Cleanup

**Priority: Medium**

Skills marked for deprecation in skill-manager:
- `rg-new-item` → consolidated into `rg-full-auto`
- `rg-inventory` → legacy, replaced by `rg-full-auto`
- `imessage-assistant` → replaced by `imessage-core` + `contacts-manager`

**Action:** Move to `archive/` folder or delete entirely.

### 6. Experimental Skills Review

**Priority: Low**

| Skill | Status | Recommendation |
|-------|--------|----------------|
| catalog-classifier | Experimental | Test and promote or remove |
| gemini-chat | Experimental | Test and promote or remove |
| image-editing-skill | Inactive | Archive or delete |
| image-generation-skill | Inactive | Archive or delete |

---

## Optional Enhancements

### A. Plugin Packaging

Convert skill collection to a Claude Code plugin for easier distribution:

```
richmond-general-plugin/
├── manifest.json
├── skills/
│   ├── rg-full-auto/
│   ├── square-cache/
│   └── ...
├── commands/
│   └── rg-status.md
└── .mcp.json
```

**Benefits:**
- Single install for team members
- Version-controlled distribution
- Namespace isolation (`/richmond-general:rg-full-auto`)

### B. Memory Tool Integration

Skills that could benefit from Memory tool (beta):
- `daily-briefing` - Remember past promises and follow-ups
- `contacts-manager` - Store learned preferences
- `rg-full-auto` - Track workflow state across sessions

### C. Extended Thinking for Complex Decisions

Skills that could benefit from extended thinking:
- `book-appraiser` - Complex first edition identification
- `carnival-glass-appraiser` - Pattern matching and attribution
- `rg-full-auto` Phase 1 - Pricing decisions

---

## Implementation Order

### Phase 1: Quick Wins (1-2 hours)
1. Add `allowed-tools` to read-only skills
2. Add missing `author` and `updated` fields
3. Update trigger keywords in descriptions

### Phase 2: Cleanup (1 hour)
1. Move deprecated skills to `archive/`
2. Update skill-manager registry
3. Delete unused experimental skills

### Phase 3: Enhancements (optional)
1. Plugin packaging
2. Memory tool integration research
3. Extended thinking testing

---

## Specific File Changes

### contacts-manager/SKILL.md
```yaml
---
name: contacts-manager
description: Contact lookup, quick reference, and spam filtering. Use when user asks who a phone number belongs to, needs contact info, wants to lookup or add a contact, identify unknown numbers, check if a number is spam, or asks "who is this". Contains detailed profiles with communication style notes for composing personalized replies.
allowed-tools: Read, Grep, Glob, Bash
metadata:
  version: "1.1"
  author: scottybe
  updated: "2025-12-21"
---
```

### book-appraiser/SKILL.md
```yaml
---
name: book-appraiser
description: Antiquarian and antique book appraisal, identification, and valuation. Use when the user presents a book that appears to be from before 1970, asks about old/antique/vintage books, rare books, first editions, signed copies, needs help identifying publisher/edition/printing, wants to research book value, or asks about Library of Congress holdings or public domain status.
allowed-tools: Read, Grep, Glob, WebFetch, WebSearch
metadata:
  version: "1.1"
  author: scottybe
  updated: "2025-12-21"
---
```

### imessage-core/SKILL.md
```yaml
---
name: imessage-core
description: Read and send iMessage/RCS/SMS messages. Use when user asks to check messages, read texts, send a text, text back, respond to someone, reply to a message, check delivery status, or list group chats. Queries chat.db directly for full sent+received history. Supports 1:1 conversations, group chats, and smart service detection (iMessage vs RCS vs SMS).
metadata:
  version: "1.1"
  author: scottybe
  updated: "2025-12-21"
---
```

---

## Verification Checklist

After updates, verify:
- [ ] All skills have valid YAML frontmatter (no syntax errors)
- [ ] All skills have `name`, `description`, `metadata.version`
- [ ] Security-sensitive skills have `allowed-tools` restrictions
- [ ] Deprecated skills moved to `archive/`
- [ ] skill-manager registry updated
- [ ] Git commit with version bump
- [ ] Test discovery by asking Claude about each skill's triggers

---

## References

- [Claude Code Skills Documentation](https://code.claude.com/docs/en/skills.md)
- [Agent Skills Overview](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview.md)
- [Claude Code Plugins Guide](https://code.claude.com/docs/en/plugins.md)
