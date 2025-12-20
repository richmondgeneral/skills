---
name: carnival-glass-appraiser
description: Complete appraisal workflow for carnival glass (pressed iridescent glass from 1908-1930s). Use when identifying carnival glass patterns, authenticating pieces, attributing makers (Northwood, Fenton, Imperial), or valuing bowls, plates, water sets. Handles pattern recognition, manufacturer attribution, reproduction detection, condition assessment, and valuation.
metadata:
  version: "1.0"
---

# Carnival Glass Appraiser

Complete appraisal workflow for carnival glass—from pattern identification through valuation.

**Current Date Context:** When appraising, consider that pricing data and market trends are most relevant within the past 6-12 months. Older sold listings may not reflect current values.

## When to Use This Skill

**Triggers:**
- "carnival glass"
- "iridescent pressed glass"
- Manufacturer names: Northwood, Fenton, Imperial, Dugan, Millersburg, Westmoreland
- Pattern names: Grape & Cable, Orange Tree, Peacock, Dragon & Lotus, etc.
- Color terms: marigold, amethyst, radium finish, peach opal
- Questions about iridescent bowls, plates, water sets, punch sets, vases from early 1900s

**Route from rg-inventory:** When rg-inventory Phase 1 identifies carnival glass, this skill handles the complete appraisal. Return to rg-inventory Phase 2 (Photography) after appraisal.

## Inputs Needed

Gather the following information before proceeding:

1. **Visual inspection** - Photos of pattern, base, edges, any marks
2. **Form/shape** - Bowl, plate, vase, water set, punch set, etc.
3. **Base color** - The glass color underneath iridescence
4. **Iridescence type** - Marigold, radium, electric, pastel, satin
5. **Size** - Approximate dimensions
6. **Condition notes** - Chips, cracks, wear, iridescence loss

## 5-Phase Appraisal Workflow

### Phase 1: Pattern Identification

Match the pattern to manufacturer using `references/carnival-glass-complete.md`:

1. Examine the main decorative motif (fruits, flowers, birds, geometric)
2. Note border/edge patterns
3. Check interior vs exterior decoration
4. Cross-reference against pattern tables by manufacturer

**Common pattern families:**
- Grape patterns: Northwood Grape & Cable, Fenton Vintage, Imperial Heavy Grape
- Peacock patterns: Northwood Peacock at Fountain, Fenton Peacock & Grape, Millersburg Peacock & Urn
- Fruit patterns: Northwood Three Fruits, Dugan Cherries
- Geometric: Imperial Fashion, Star Medallion

**Output:** Pattern name and confidence level (high/medium/low)

### Phase 2: Manufacturer Attribution

Once pattern is identified, confirm maker through:

1. **Pattern exclusivity** - Many patterns are maker-specific
2. **Base shape** - Collar base (Fenton), dome foot (Northwood), spatula feet (Fenton)
3. **Maker's mark** - Check underside for "N" in circle (Northwood), Iron Cross (Imperial)
4. **Color** - Peach opal edges = Dugan, radium finish = Millersburg
5. **Glass quality** - Weight, clarity, mold sharpness

**Key identifiers by maker:**
| Maker | Distinguishing Features |
|-------|------------------------|
| Northwood | "N" mark, elaborate patterns, ice colors |
| Fenton | Collar base, spatula feet, wide color range |
| Imperial | Heavy glass, excellent purple, geometric patterns |
| Dugan | Peach opal edges, unmarked |
| Millersburg | Radium finish, exceptional quality, rare |
| Westmoreland | Peacock patterns, opalescent |

**Output:** Manufacturer name and confidence level

### Phase 3: Authentication

Determine if piece is original (1908-1930s) or reproduction:

**Check for reproduction red flags:**
- [ ] Colors not made originally (verify color/pattern combo existed)
- [ ] "Too perfect" iridescence (originals have variation)
- [ ] Modern marks on old-style pieces
- [ ] Lighter weight than expected
- [ ] Different base configuration
- [ ] Mold details less sharp

**Known reproduction sources:**
- Fenton (1970s-2000s) - Usually marked "Fenton"
- L.G. Wright (1960s-1990s) - Unmarked, problematic
- Summit Art Glass
- Taiwan/China imports - Lighter weight, odd colors

**Key authentication points:**
- Original carnival glass is heavier, denser
- Original iridescence is more subtle and varied
- Original mold detail is sharper
- Reproduction colors often "off" from originals

**Output:** Authentication status (Original / Reproduction / Uncertain) with reasoning

### Phase 4: Condition Assessment

Grade the piece on these factors:

**Iridescence quality:**
- Excellent: Strong, multicolored, even coverage
- Good: Solid coverage, some variation
- Fair: Faded areas, uneven
- Poor: Significant loss, dull

**Physical condition:**
- Mint: No damage whatsoever
- Excellent: Minimal wear, no chips
- Very Good: Minor wear, possible tiny flakes
- Good: Light chips, scratches, some wear
- Fair: Noticeable chips, cracks, or damage
- Poor: Major damage affecting display

**Specific issues to note:**
- Rim chips (common, reduces value significantly)
- Base chips (less visible, smaller impact)
- Cracks or fractures (major value reduction)
- Scratches in iridescence
- Staining or cloudiness

**Output:** Condition grade with detailed notes

### Phase 5: Valuation

Provide price range based on:

**Value factors:**
1. **Rarity** - Pattern scarcity, color rarity, form rarity
2. **Maker** - Millersburg > Northwood > Fenton/Dugan/Imperial
3. **Color** - Red, aqua opal, ice colors command premiums
4. **Form** - Plates > bowls; rare forms > common forms
5. **Condition** - Mint/excellent = full value; each grade down reduces 20-40%
6. **Size** - Larger pieces often more valuable
7. **Pattern popularity** - Collector demand varies

**Pricing research methodology:**
1. Search eBay "Sold" listings for exact or similar pieces
2. Check recent auction results (LiveAuctioneers, WorthPoint)
3. Reference carnival glass collector price guides
4. Consider current market trends (carnival glass market has softened)

**Value tiers (general guidance for excellent condition):**
| Category | Price Range | Examples |
|----------|-------------|----------|
| Common | $15-50 | Marigold bowls, Imperial Ripple vases |
| Mid-range | $50-150 | Good patterns in common colors |
| Desirable | $150-400 | Northwood marked pieces, unusual colors |
| Rare | $400-1000 | Rare patterns, rare colors, Millersburg |
| Premium | $1000+ | Red, exceptional Millersburg, rarities |

**Condition multipliers:**
- Mint/Excellent: 100% of value
- Very Good: 70-85%
- Good: 50-70%
- Fair: 30-50%
- Poor: 10-30% (decorative only)

**Output:** Price range with comparable sales evidence and reasoning

## Output Format

After completing all 5 phases, provide:

```
## Carnival Glass Appraisal Summary

**Pattern:** [Name] (Confidence: High/Medium/Low)
**Manufacturer:** [Name] (Confidence: High/Medium/Low)
**Era:** [Original 1908-1930s / Reproduction / Uncertain]
**Color:** [Base color + iridescence type]
**Form:** [Bowl/Plate/Vase/etc.]
**Condition:** [Grade] - [Notes]

**Valuation:** $XX - $XX
**Comparable Sales:** [Recent sold examples]
**Notes:** [Authentication details, special features, market factors]

---
Ready to continue with rg-inventory Phase 2 (Photography)
```

## Integration with rg-inventory

This skill handles the complete Phase 1 (Appraisal & Research) for carnival glass items:
- Pattern identification ✓
- Manufacturer attribution ✓
- Authentication ✓
- Condition assessment ✓
- Valuation with comps ✓

After appraisal completes, return to rg-inventory workflow at Phase 2 (Photography).

## References

- `references/carnival-glass-complete.md` - Pattern catalogs, color guides, maker identification
