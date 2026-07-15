---
name: maker-mark-identifier
description: Identify maker's marks on pottery, silver, furniture, and jewelry. Use when examining stamps, hallmarks, signatures, labels, or asking "what is this mark" or "who made this" to determine manufacturer, origin, and date range. Returns identification only—defers valuation to calling workflow.
allowed-tools: Read, Grep, Glob, WebFetch, WebSearch
metadata:
  version: "1.1"
  author: scottybe
  updated: "2025-12-21"
  changelog: |
    v1.1 - Anthropic skills update:
    - Added allowed-tools (read + web research)
    - Enhanced triggers: "what is this mark", "who made this"
    - Added author and updated fields
---

# Maker's Mark Identifier

Focused identification skill for maker's marks on antiques and collectibles. This skill identifies the maker, origin, and date range—then returns to rg-full-auto for valuation.

## When to Use This Skill

**Triggers:**
- "maker's mark"
- "pottery mark"
- "silver hallmark"
- "furniture stamp"
- "what is this mark"
- "identify this stamp"
- "who made this"
- Questions about marks on ceramics, silverware, antique furniture, jewelry

**NOT for carnival glass** — Use `carnival-glass-appraiser` instead (pattern-based identification, not marks).

**Route from rg-full-auto:** When rg-full-auto Phase 1 identifies a maker's mark needing identification, this skill provides the ID. Return to rg-full-auto Phase 1 to continue with condition assessment and valuation.

## Inputs Needed

1. **Mark image or description** — Photo of mark, or detailed description
2. **Item type** — What is the mark on? (vase, plate, chair, spoon, etc.)
3. **Mark location** — Bottom, back, inside, edge
4. **Any visible text** — Letters, words, numbers in the mark

## 4-Phase Identification Workflow

### Phase 1: Examine the Mark

Describe what you observe in detail:

| Element | What to Note |
|---------|--------------|
| **Shape** | Circle, oval, shield, diamond, banner, cartouche, freeform |
| **Content** | Letters, numbers, words, symbols, images, animals, crowns |
| **Style** | Impressed/incised, raised/molded, printed/stamped, painted, etched, paper label |
| **Color** | Ink color, underglaze vs overglaze (ceramics) |
| **Condition** | Complete, partial, worn, obscured portions |

If image is unclear, request additional photos with different angles or lighting.

**Output:** Detailed mark description

### Phase 2: Classify the Mark Type

Determine category to guide research approach:

| Category | Common Mark Types | Key Details |
|----------|-------------------|-------------|
| **Ceramics/Pottery** | Printed, impressed, incised | Country of origin text, pattern numbers |
| **Silver/Metalware** | Hallmarks, maker's marks, date letters | Hallmark system varies by country |
| **Furniture** | Stamps, labels, brands, stencils | Style/construction also dates pieces |
| **Jewelry** | Stamps, hallmarks, maker's marks | Karat marks, country marks |
| **Glass** | Molded, etched, acid stamp, paper label | Pontil type indicates age |

**Output:** Category classification

### Phase 3: Research Identification

**Search strategy by mark type:**

**Text-based marks** (words, company names):
- Search exact text + "pottery mark" / "silver mark" / category
- Try partial matches if full name unclear
- Check common abbreviations (Co., Bros., Mfg.)

**Symbol/image marks** (crowns, animals, shapes):
- Describe symbol + category: "crown over shield pottery mark"
- Cross-reference known mark databases
- Common symbol origins: anchor (England), fleur-de-lis (France), eagle (Germany/USA)

**Number marks** (pattern numbers, mold numbers, date codes):
- Note position relative to other marks
- Date codes vary by manufacturer—require maker ID first

**Combination marks:**
- Research most distinctive element first
- Company names trump symbols
- Pattern numbers help narrow date once maker identified

**Reference:** See `references/research-sources.md` for databases by category.

**Output:** Research findings

### Phase 4: Attribution

Provide identification with confidence level:

**High confidence (Confirmed):**
- Manufacturer name and location
- Date range of production
- What the specific mark variation indicates

**Medium confidence (Probable):**
- Most likely attribution with reasoning
- What additional information would confirm
- Alternative possibilities

**Low confidence (Uncertain):**
- What the mark suggests
- Similar marks considered
- Recommended verification steps

**Output:** Attribution with confidence level

## Output Format

After completing all 4 phases, provide:

```
## Maker's Mark Identification

**Mark Description:** [Shape, content, style]
**Category:** [Pottery/Silver/Furniture/Jewelry/Glass]

**Attribution:** [Manufacturer name]
**Location:** [City, Country]
**Date Range:** [Years of production]
**Confidence:** [High/Medium/Low]

**Reasoning:** [How identification was made]
**Verification:** [Additional steps if confidence < High]

---
Identification complete. Return to rg-full-auto Phase 1 for:
- Condition assessment
- Comparable sales research
- Valuation
```

## Quick Reference: Dating Clues

| Indicator | Typical Date Range |
|-----------|-------------------|
| "England" required on exports | 1891+ (McKinley Tariff) |
| "Made in [Country]" | 1914+ (common), 1921+ (required US imports) |
| "Reg. No." or "Rd No." (UK) | 1842-1883 (lozenge), 1884+ (numbers) |
| "Ltd" in company name | 1860s+ (UK incorporation) |
| "Japan" vs "Nippon" | Japan: 1921+, Nippon: 1891-1921 |
| Pontil scars on glass | Pre-1860s (rough), 1860s+ (smooth/polished) |

## British Silver Hallmark System

Read left to right:
1. **Maker's mark** — Initials of silversmith
2. **Standard mark** — Lion passant = sterling (.925)
3. **Assay office** — Leopard (London), Anchor (Birmingham), Rose (Sheffield), Castle (Edinburgh)
4. **Date letter** — Changes yearly; letter style indicates cycle
5. **Duty mark** — Monarch's head (1784-1890, optional)

## Integration with rg-full-auto

This skill handles **identification only**:
- ✅ Who made it (manufacturer)
- ✅ Where (location/country)
- ✅ When (date range)
- ✅ Confidence level

This skill does **NOT** handle:
- ❌ Condition assessment → rg-full-auto Phase 1
- ❌ Comparable sales research → rg-full-auto Phase 1
- ❌ Valuation/pricing → rg-full-auto Phase 1
- ❌ Listing descriptions → product-labeler

After identification, return to rg-full-auto to complete Phase 1 research checklist.

## References

- `references/research-sources.md` — Databases, search strategies, reference books


> **Pricing hand-off:** unsigned / judgment-call / higher-value pieces require a BPO-style
> pricing report at `ops/pricing/RG-XXXX-pricing.md` (template `_TEMPLATE.md`) — comps with
> sources, eBay absorption rate, tested-vs-untested tiers, condition adjustment. A confirmed
> maker's mark can move price 30–100%+ — always check and document it before pricing.
