# Refactor vintage-appraiser into Focused Skills
## Problem Statement
The current `vintage-appraiser` skill violates Claude's best practice: "Keep it focused: Create separate Skills for different workflows. Multiple focused Skills compose better than one large Skill."
The monolithic skill combines:
* General maker's mark identification (pottery, silver, furniture)
* Complete carnival glass appraisal workflow
* Pricing research methodology
* Listing/description writing
This makes it harder for Claude to discover the right skill and violates the principle of composability.
## Current State
**vintage-appraiser/** (1,099 total lines)
* SKILL.md (142 lines) - Mixed concerns
* references/carnival-glass.md (214 lines) - Complete domain
* references/pricing-research.md (196 lines) - Cross-domain
* references/listing-descriptions.md (312 lines) - Output formatting
* references/research-sources.md (93 lines) - Mixed
## Proposed Architecture (Simplified)
### Complete Appraisal Skills (Full Workflow)
**carnival-glass-appraiser/**
* Purpose: Complete appraisal from identification through valuation
* Scope: Pattern ID, authentication, condition, valuation
* Sources: carnival-glass.md (consolidated into carnival-glass-complete.md)
**Phases:**
1. Pattern identification (Grape & Cable, Orange Tree, etc.)
2. Manufacturer attribution (Northwood, Fenton, Imperial, etc.)
3. Authentication (original vs reproduction)
4. Color/iridescence quality assessment
5. Condition grading
6. Valuation based on pattern/maker/condition/color (includes pricing comps internally)
**After completion:** Returns to rg-full-auto, resume at Phase 2 (Photography)

**book-appraiser/** (already exists)
* Keep as-is, already follows proper structure
* Full workflow: edition ID, condition, LOC lookup, valuation
**After completion:** Returns to rg-full-auto, resume at Phase 2 (Photography)

### Identification Skills (Narrow Focus)
**maker-mark-identifier/**
* Purpose: Identify maker's marks on pottery, silver, furniture, general antiques
* Scope: Identification only (maker, date, confidence), defer valuation to rg-full-auto
* Sources: Current vintage-appraiser SKILL.md (Steps 1-4), research-sources.md (filtered)
**Characteristics:**
* Input: Image/description of mark
* Output: Maker name, location, date range, confidence level
* Defers: Valuation, condition assessment to rg-full-auto Phase 1 research checklist
**After completion:** Returns to rg-full-auto, continue Phase 1 for valuation

### Demoted to Reference Patterns (Not Separate Skills)
**pricing-validator** → Shared reference pattern
* Domain appraisers include pricing comps internally (carnival-glass, book)
* General items use rg-full-auto Phase 1 research checklist

**listing-writer** → marketplace-templates.md in rg-full-auto/references/
* Keep listing templates in rg-full-auto context
* No separate skill needed
## Implementation Plan
### Phase 1: Extract carnival-glass-appraiser (TVM-24)
**Create new skill:**
```
carnival-glass-appraiser/
├── SKILL.md
└── references/
    └── carnival-glass-complete.md  # Consolidated: all carnival glass knowledge
```
**SKILL.md structure:**
* Frontmatter: name, version 1.0.0, description (focused on carnival glass only)
* Current date context: December 20, 2025
* Complete appraisal workflow (5 phases)
* Pattern identification guidance
* Manufacturer attribution logic
* Authentication checks
* Valuation methodology with pricing comps integrated
* Integration point: Returns to rg-full-auto at Phase 2 (Photography)

**Accept criteria:**
- [x] Full appraisal workflow for carnival glass
- [x] Pattern recognition guide
- [x] Manufacturer attribution
- [x] Reproduction detection
- [x] Valuation based on pattern/maker/color/condition
- [x] Integrates with rg-full-auto Phase 1
- [x] rg-full-auto Phase 1 routing updated
- [x] rg-full-auto Related Skills section updated
- [ ] Skill builds successfully with build-skill.sh
- [ ] Smoke test in Claude validates routing and workflow
### Phase 2: Extract maker-mark-identifier (Future Issue)
**Refactor vintage-appraiser:**
```
maker-mark-identifier/
├── SKILL.md
└── references/
    ├── pottery-marks.md           # Extracted from vintage-appraiser
    ├── silver-hallmarks.md        # Extracted from vintage-appraiser
    ├── furniture-stamps.md        # Extracted from vintage-appraiser
    └── research-sources.md        # Filtered for mark databases
```
**SKILL.md structure:**
* Purpose: Identify maker's marks only (not full appraisal)
* Scope: Pottery, silver, furniture, general antiques (NOT carnival glass)
* Workflow: Examine → Classify → Research → Report findings
* Output: Maker, location, date range, confidence
* Defer: Valuation and listing to other skills
**Accept criteria:**
- [ ] Clear identification workflow
- [ ] Category-specific guidance (pottery, silver, furniture)
- [ ] Research source references
- [ ] Confidence level reporting
- [ ] Explicit deferral to appraisers for valuation
### Phase 3: Update rg-full-auto integration (COMPLETED)
**Updated Phase 1 routing in rg-full-auto/SKILL.md:**
Before:
```markdown
- Books pre-1970 or antiquarian → Load book-appraiser skill
- Maker's marks, pottery, glass, silver → Load vintage-appraiser skill
- General vintage items → Continue with this workflow
```
After:
```markdown
**Route to domain appraiser when applicable:**
- Books pre-1970 or antiquarian → Load book-appraiser skill
- Carnival glass (iridescent pressed glass, marigold, amethyst, Northwood, Fenton) → Load carnival-glass-appraiser skill
- Other maker's marks (pottery, silver, furniture) → Load maker-mark-identifier skill (returns ID only; continue Phase 1 for valuation)
- General vintage items → Continue with this workflow

**When using a domain appraiser:**
- Appraiser handles full research cycle: identification → authentication → condition → valuation
- Resume workflow at Phase 2 (Photography) using appraiser's output
- Skip research checklist below (appraiser covers it)
```

**Updated Related Skills section:**
```markdown
### Related Skills
- **carnival-glass-appraiser**: Complete appraisal for iridescent pressed glass (pattern ID, manufacturer attribution, authentication, valuation)
- **maker-mark-identifier**: Identify pottery, silver, furniture marks (defers valuation to Phase 1)
- **book-appraiser**: Antiquarian books, LOC cross-reference, edition identification
- **product-labeler**: Thermal label generation, Square catalog descriptions
```

**Accept criteria:**
- [x] Phase 1 routing updated with new skills
- [x] Domain appraiser handoff clarified (full vs ID-only)
- [x] Related Skills section updated
- [x] Clear skill selection criteria

### Phase 4: Update README and documentation
**Update README.md:**
* Replace vintage-appraiser entry with new skills
* Document skill composition patterns
* Update integration section
**Accept criteria:**
- [ ] All new skills listed
- [ ] vintage-appraiser removed
- [ ] Composition examples provided
## Workflow Examples
### Example 1: Carnival Glass Bowl (TVM-24 Test Case)
```
User: "I have a purple carnival glass bowl with grapes"
  ↓
rg-full-auto (Phase 1 routing)
  ↓
carnival-glass-appraiser
  ├─ Phase 1: Identifies pattern: Northwood Grape & Cable
  ├─ Phase 2: Attributes maker: Northwood (N mark present)
  ├─ Phase 3: Authenticates: Original (not reproduction)
  ├─ Phase 4: Condition: Excellent (no chips, strong iridescence)
  ├─ Phase 5: Values: $85-125 (amethyst, excellent condition)
  └─ Returns to rg-full-auto with complete appraisal
      ↓
rg-full-auto resumes at Phase 2: Photography
  → Phase 3: Square Catalog Creation
  → Phase 4: Payment Link
  → Phase 5: Shipping Config
  → Phase 6: Label Generation (uses marketplace-templates.md in references)
  → Phase 7: Info Card & Publishing
```
### Example 2: Unknown Pottery Mark
```
User: "What is this mark on the bottom of this vase?"
  ↓
rg-full-auto (Phase 1 routing)
  ↓
maker-mark-identifier
  ├─ Examines: Crown over lion mark
  ├─ Identifies: Royal Doulton (England)
  ├─ Dates: 1902-1922 (based on mark variation)
  ├─ Confidence: High
  └─ Returns: Maker ID only (no valuation)
      ↓
rg-full-auto continues Phase 1 research checklist:
  ├─ Assess condition
  ├─ Research comparable sales (eBay sold, auction records)
  └─ Determine price point
      ↓
rg-full-auto continues at Phase 2: Photography, etc.
```
### Example 3: Antique Book
```
User: "1930s Harold Gray Little Orphan Annie book"
  ↓
rg-full-auto (Phase 1 routing)
  ↓
book-appraiser (unchanged, already complete)
  ├─ Edition: 1979 Dover reprint
  ├─ Condition: Very Good
  ├─ LOC check: Public domain
  ├─ Values: $15-25 (includes AbeBooks comps internally)
  └─ Returns to rg-full-auto with complete appraisal
      ↓
rg-full-auto resumes at Phase 2: Photography, etc.
```
## Testing Strategy
**Test each skill independently:**
1. carnival-glass-appraiser: Test pattern recognition, manufacturer attribution, authentication, valuation
2. maker-mark-identifier: Test pottery, silver, furniture mark identification
3. book-appraiser: Already tested, keep as-is

**Test skill composition:**
* Carnival glass workflow: rg-full-auto → carnival-glass-appraiser → resume Phase 2
* Pottery mark workflow: rg-full-auto → maker-mark-identifier → continue Phase 1 → Phase 2
* Book workflow: rg-full-auto → book-appraiser → resume Phase 2

**Test rg-full-auto routing (TVM-24 test cases):**
1. "I have a purple bowl with grapes" → Should route to carnival-glass-appraiser
2. "What's this marigold glass worth?" → Should route to carnival-glass-appraiser
3. "Is this carnival glass reproduction?" → Should route to carnival-glass-appraiser
4. "I have a purple carnival glass bowl" → Routes to carnival-glass-appraiser
5. Appraisal completes → rg-full-auto resumes at Phase 2 (Photography)
## Migration Notes
**Backward compatibility:**
* Users with vintage-appraiser uploaded can keep it (deprecated)
* New users get focused skills
* Document migration path
**Deprecation timeline