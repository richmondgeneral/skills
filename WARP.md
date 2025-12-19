# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Repository Purpose

This is a skills library for AI assistants managing Richmond General's vintage and antique inventory system. Each skill provides specialized workflows for specific aspects of inventory management, from appraisal and cataloging to pricing and publishing.

### Agent Skills Standard Compliance

This repository follows the **Agent Skills open standard** (published Dec 18, 2025) from Anthropic. Skills are portable across Claude and other Agent Skills-compatible platforms including:
- Claude (claude.ai, Claude Code, API)
- VS Code & GitHub (Microsoft)
- Cursor, Goose, Amp, OpenCode
- Any platform implementing the agentskills.io specification

**Key Principle: Progressive Disclosure**  
Skills use a three-tier loading strategy:
1. **Metadata** (name + description) - Loaded at startup (~100 tokens)
2. **Instructions** (SKILL.md body) - Loaded when relevant (~5k tokens)
3. **Resources** (scripts, references) - Loaded on-demand only

This means skills can include comprehensive documentation without context penalty.

## Skills Architecture

### Three-Tier Skill System

Skills are organized by scope and specialization:

**1. Primary Workflow Skills** (root-level directories)
- `rg-inventory/` - Master orchestrator for the complete inventory workflow
- `book-appraiser/` - Antiquarian book appraisal and edition identification  
- `vintage-appraiser.skill` - Maker's mark identification (packaged as .skill archive)

**2. Supporting Skills** (user/ subdirectories)
- `product-labeler/` - Label generation and Square catalog formatting
- Other user-specific skills in development

**3. Skill Loading Pattern**
Skills reference each other through conditional loading:
- `rg-inventory` routes to `book-appraiser` for pre-1970 books
- `rg-inventory` routes to `vintage-appraiser` for maker's marks
- Phase 6 of `rg-inventory` calls `product-labeler` for thermal labels

### Skill Structure

Standard skill structure (e.g., `rg-inventory/`, `book-appraiser/`):
```
skill-name/
├── SKILL.md              # Main skill definition with YAML frontmatter
└── references/           # Supporting documentation
    ├── specific-topic.md
    └── guidelines.md
```

Each SKILL.md includes:
- **YAML frontmatter** (required by Agent Skills standard):
  - `name`: Lowercase, hyphenated, max 64 chars (e.g., `rg-inventory`, `book-appraiser`)
  - `description`: What the skill does AND when to use it (critical for discovery)
  - Include trigger keywords users would naturally mention
- Core workflow with numbered phases/steps
- Integration points with other skills
- Quick reference tables for IDs, categories, formats
- External API/service details where applicable

**Description Best Practices:**
- Include both capabilities and use cases
- Use specific terms, avoid vague descriptions like "helps with" or "manages"
- Good: `"Extract text and tables from PDF files, fill forms. Use when working with PDFs or document extraction."`
- Bad: `"PDF processing tool"` (too vague, won't be discovered)

### Critical Integration Points

**Square API Services:**
- Location ID: `B87BAEZ0NWV34` (Richmond General)
- Merchant ID: `7MM9AFJAD0XHW`
- Required categories: Both `3N3II4W6Q7AA43RWQGEEWELY` (Timeless Treasures) AND `P34KX3L7XRZJJ5RP6W35K4YO` (The New Finds)
- Reporting category: Must be set to `P34KX3L7XRZJJ5RP6W35K4YO` for proper tracking
- Tax ID: `LPKEJF7H27NOPK7EE6A5CA7V` (IL State + Richmond Local)

**GitHub Pages Publishing:**
- Site: https://richmondgeneral.github.io/items/
- Repository: github.com/richmondgeneral/items
- QR codes point to payment links, not product pages
- Template location: `template/rg-item-card-template.html`

**SKU Format:**
- Primary: `RG-XXXX` (Richmond General items)
- Lot-based: `L##-` prefix for estate purchases
- Product categories: `SNACK-`, `BEV-`, `VINT-`, `WELL-`, etc.

## Working with Skills

### Viewing Skills
```bash
# List all primary skills
ls -1 */SKILL.md

# View skill with references
cat rg-inventory/SKILL.md
cat rg-inventory/references/square-catalog.md

# User skills are nested one level deeper
cat user/product-labeler/product-labeler/SKILL.md
```

### .skill Archives
The `vintage-appraiser.skill` file is a Zip archive:
```bash
# Extract to view/edit
unzip vintage-appraiser.skill -d vintage-appraiser-extracted/

# Repackage after editing
cd vintage-appraiser/ && zip -r ../vintage-appraiser.skill .
```

### Editing Skills

When modifying SKILL.md files:
- Preserve YAML frontmatter (between `---` delimiters)
- Maintain numbered phase/step structure for workflows
- Update integration points if IDs or endpoints change
- Keep reference files in sync with main SKILL.md

### Testing Skills

This is a documentation repository with no build/test system. Validation is manual:
1. Check YAML frontmatter parses correctly
2. Verify all referenced IDs match Square/GitHub configuration
3. Test API examples against Square sandbox if available
4. Confirm cross-references between skills are accurate

## Key Workflows

### 7-Phase Inventory Workflow (rg-inventory)
1. **Appraisal** - Route to specialized skills (book/vintage appraiser)
2. **Photography** - Hero shots, detail images, consistent naming
3. **Square Catalog** - API creation with dual categories + reporting category
4. **Fulfillment** - Shipping profile assignment via dashboard
5. **Payment Links** - Generate checkout URLs via API
6. **Labels** - Thermal printer CSV via product-labeler skill
7. **Info Cards** - GitHub Pages publishing with QR codes

### Book Appraisal (book-appraiser)
Focus on pre-1970 books:
- Edition identification (first editions, book club editions)
- Library of Congress cross-reference
- Public domain status checking (pre-1929, 1929-1963 with renewal check)
- Condition grading (Fine → Poor scale)
- Dust jacket valuation (can add 50-100% to value)

### Maker's Mark Research (vintage-appraiser)
- Classify mark type (ceramics, glass, silver, furniture)
- Dating clues: "Made in" vs "England", Nippon vs Japan
- Carnival glass pattern identification (Northwood, Fenton, Imperial)
- Confidence levels: Confirmed → Probable → Uncertain

## Price Research

All skills reference market research best practices:
- **Primary source**: eBay Sold Listings (actual sale prices)
- **Supporting**: Worthpoint, LiveAuctioneers, AbeBooks
- **Avoid**: Current listings on Etsy/Ruby Lane (inflated asking prices)

Pricing tiers (rg-inventory):
- Quick flip ($1-15): 2-3x cost
- Mid-range ($15-75): 2.5-4x cost  
- Showcase ($75+): Research-based

## Repository Maintenance

### Version Control
- No automated versioning; skills evolve organically
- Major API changes should update all affected references
- Consider tagging releases when Square API endpoints change

### File Organization
Do NOT reorganize without updating cross-references:
- Skills reference each other by name in SKILL.md files
- Template paths in rg-inventory point to items repository
- Reference file paths are relative to skill directory

### Documentation Standards
- Use markdown tables for IDs, categories, pricing tiers
- Include examples in code blocks (JSON for API, CSV for labels)
- Keep "Quick Reference" sections at top of long workflows
- Date-sensitive information (e.g., tax IDs) should be clearly marked

### Agent Skills References

For the latest official documentation, see files in this repository:
- `agent-skills-specification.html` - Official open standard specification
- `claude-skills-docs.html` - Complete implementation guide
- `anthropic-skills-README.md` - GitHub repository README
- `CLAUDE-SKILLS-DOCS-INDEX.md` - Summary with links to all resources

Key resources:
- Specification: https://agentskills.io/specification
- Official GitHub: https://github.com/anthropics/skills
- Platform docs: https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview
