---
name: vintage-appraiser
description: ⚠️ DEPRECATED - This skill has been replaced by focused skills. Use carnival-glass-appraiser for carnival glass, maker-mark-identifier for pottery/silver/furniture marks. This skill remains for reference but should not be used for new work.
---

# ⚠️ Vintage Appraiser (DEPRECATED)

**This skill has been replaced by focused, composable skills:**

- **carnival-glass-appraiser** → Full carnival glass appraisal (pattern ID, authentication, condition, valuation)
- **maker-mark-identifier** → Pottery, silver, furniture mark identification (ID only, defer valuation to rg-inventory)
- **book-appraiser** → Antiquarian books (unchanged)

**Why deprecated:** This skill mixed multiple responsibilities (carnival glass, general marks, pricing, listing copy), violating Claude's best practice: "Keep it focused: Create separate Skills for different workflows."

**Do not use this skill for new work.** The content below is kept for reference only.

---

## Original Content (Reference Only)

**Original Date:** December 19, 2025

## Core Workflow

Identifying a maker's mark involves these steps:

1. **Examine the mark** - Describe what you observe in detail
2. **Classify the mark type** - Determine category (see below)
3. **Research identification** - Use appropriate resources
4. **Provide findings** - Share identification with confidence level
5. **Suggest verification** - Recommend next steps if uncertain

## Step 1: Examine the Mark

When examining a mark, note and describe:

- **Shape**: Circle, oval, shield, diamond, banner, cartouche, or freeform
- **Content**: Letters, numbers, words, symbols, images, animals, crowns
- **Style**: Impressed/incised, raised/molded, printed/stamped, painted, etched, paper label
- **Color**: Ink color, underglaze vs overglaze (ceramics)
- **Location**: Bottom, back, inside, edge—location can indicate era
- **Condition**: Partial, worn, obscured portions

If the image is unclear, ask for additional photos—different angles or lighting often reveal more.

## Step 2: Classify the Mark Type

Different categories have different research approaches:

| Category | Common Mark Types | Key Details to Note |
|----------|-------------------|---------------------|
| **Ceramics/Pottery** | Printed, impressed, incised | Country of origin text, pattern numbers |
| **Glass** | Molded, etched, pontil, acid stamp, paper label | Pontil type indicates age |
| **Silver/Metalware** | Hallmarks, maker's marks, date letters | Hallmark system varies by country |
| **Furniture** | Stamps, labels, brands, stencils | Style/construction also dates pieces |
| **Jewelry** | Stamps, hallmarks, maker's marks | Karat marks, country marks |

See `references/research-sources.md` for category-specific resources.

## Step 3: Research Identification

**Search strategy by mark type:**

**Text-based marks** (words, company names):
- Search the exact text plus "pottery mark" / "glass mark" / category
- Try partial matches if full name unclear
- Check for common abbreviations (Co., Bros., Mfg.)

**Symbol/image marks** (crowns, animals, shapes):
- Describe the symbol + category: "crown over shield pottery mark"
- Cross-reference with known mark databases
- Note that symbols often indicate country: anchor (England), fleur-de-lis (France)

**Number marks** (pattern numbers, mold numbers, date codes):
- Note position relative to other marks
- Research as part of complete mark system
- Date codes vary by manufacturer—require maker ID first

**Combination marks** (multiple elements):
- Research the most distinctive element first
- Company names trump symbols
- Pattern numbers help narrow date once maker identified

## Step 4: Provide Findings

Structure identification results as:

**Confirmed identification:**
- Manufacturer name and location
- Date range of production (when determinable)
- What the specific mark variation indicates
- Any notable information about the maker/piece

**Probable identification (medium confidence):**
- Most likely attribution with reasoning
- What additional information would confirm
- Alternative possibilities if any

**Uncertain (low confidence):**
- Describe what the mark suggests
- List similar marks that were considered
- Recommend verification steps

## Step 5: Verification Recommendations

When confidence is not high, suggest:

- Additional photos (mark detail, full piece, construction details)
- Physical examination points (weight, construction, materials)
- Specialist consultation for valuable pieces
- Auction house archives for comparable examples

## Quick Reference: Dating Clues

| Indicator | Typical Date Range |
|-----------|-------------------|
| "England" required on exports | 1891+ (McKinley Tariff) |
| "Made in [Country]" | 1914+ (common), 1921+ (required US imports) |
| "Reg. No." or "Rd No." (UK) | 1842-1883 (lozenge), 1884+ (numbers) |
| "Ltd" in company name | 1860s+ (UK incorporation) |
| "Japan" vs "Nippon" | Japan: 1921+, Nippon: 1891-1921 |
| Pontil scars on glass | Pre-1860s (rough), 1860s+ (smooth/polished) |

## Migration Guide

### For Carnival Glass
**Use:** `carnival-glass-appraiser` skill
- Complete appraisal workflow (pattern ID → authentication → condition → valuation)
- Handles full Phase 1 for rg-inventory
- Resume at Phase 2 (Photography) after appraisal

### For Maker's Marks (Pottery, Silver, Furniture)
**Use:** `maker-mark-identifier` skill
- Identification only (maker, location, date range, confidence)
- Returns to rg-inventory Phase 1 for valuation
- Continue with condition assessment and pricing research

### For Pricing/Valuation
**Use:** rg-inventory Phase 1 research checklist
- Comparable sales research (eBay sold, auction records)
- Pricing tiers by category
- Margin targets

### For Listing Descriptions
**Use:** marketplace-templates.md in rg-inventory (future)
- Title formulas by category
- Description templates
- Condition language standards

---

## Additional Resources (Deprecated)

- **Research databases and sources:** See `references/research-sources.md` → Now in maker-mark-identifier
- **Carnival glass patterns:** See `references/carnival-glass.md` → Now in carnival-glass-appraiser
- **Pricing research:** See `references/pricing-research.md` → Now in rg-inventory Phase 1
- **Listing descriptions:** See `references/listing-descriptions.md` → Future: rg-inventory/references/marketplace-templates.md
