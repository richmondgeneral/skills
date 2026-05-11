# Design Doc: Whatnot Skill Suite

**Author:** Claude (for scottybe)
**Date:** February 16, 2026
**Status:** Draft v2
**Audience:** Future Claude instances executing skill builds
**Input:** [Whatnot DVD Retro 2026-02-16] — process improvement retrospective from RG-0016–RG-0020 batch
**Reader test score:** v1 scored 3/10 — v2 addresses all flagged gaps

---

## 0. How Skills Work (for future Claude)

### File Structure

Each skill is a directory under `~/.claude/skills/` containing a single `SKILL.md`:

```
~/.claude/skills/
├── whatnot-chrome/
│   └── SKILL.md          ← Chrome automation patterns
├── whatnot-catalog/
│   └── SKILL.md          ← Category data & allowed values
├── rg-full-auto/
│   └── SKILL.md          ← Orchestrator (delegates to above)
└── ... (other skills)
```

No other files required. No registry file. No CLI command. Placing `SKILL.md` in the directory IS the registration — the skill system discovers skills by scanning `~/.claude/skills/*/SKILL.md`.

### How "Delegation" Works Between Skills

Skills are **markdown documents that Claude reads**. There is no function call API between skills. "Delegate to `whatnot-chrome`" means:

1. Claude reads `~/.claude/skills/whatnot-chrome/SKILL.md`
2. Claude follows the instructions in that file
3. Claude uses the MCP tools (find, form_input, computer, javascript_tool, navigate) as instructed

"Consult `whatnot-catalog`" means:

1. Claude reads `~/.claude/skills/whatnot-catalog/SKILL.md`
2. Claude looks up the relevant reference table
3. Claude uses the looked-up values when filling fields

There is no runtime, no imports, no function calls. Skills are instructions that Claude reads and follows. The orchestrator skill (`rg-full-auto`) tells Claude *when* to read each sub-skill.

### Tab ID Context

Tab IDs are ephemeral. When `rg-full-auto` Phase 8 says "delegate to whatnot-chrome," Claude already has the tab ID in its working context from the `tabs_context_mcp` call at the start of the session. The tab ID is NOT passed between skills — it's in Claude's conversation context.

---

## 1. Problem Statement

Richmond General's Whatnot onboarding workflow is embedded inside `rg-full-auto` Phase 8, but it has outgrown that container. The Feb 2026 DVD batch exposed three categories of problems:

1. **Data accuracy** — Shipping Profile values were wrong in the skill, costing ~10 min per batch in manual corrections.
2. **Missing workflow** — Post-import metadata editing (category-specific fields like Genre, Type, Edition) had no documentation at all. First-time discovery took ~15 min of trial and error.
3. **No reusable automation patterns** — The Chrome interaction patterns for Whatnot's React comboboxes were learned live and had to be re-discovered each session.

Phase 8 was patched to v3.4 with inline fixes, but the Whatnot-specific knowledge is now ~160 lines buried in a 1100+ line skill. It should be extracted into dedicated, composable skills.

---

## 2. Architecture Decision: Two Skills

After analyzing the problem boundaries, the cleanest split is **two skills** with distinct responsibilities:

### Skill 1: `whatnot-chrome`
**Purpose:** Reusable Chrome automation primitives for Whatnot's dashboard.

This skill owns the *how* — how to interact with Whatnot's React UI, how to navigate pages, how to fill comboboxes, how to batch-edit items. It knows nothing about Richmond General's inventory or categories.

### Skill 2: `whatnot-catalog`
**Purpose:** Whatnot-specific catalog knowledge — categories, metadata fields, allowed values, shipping heuristics.

This skill owns the *what* — what fields exist for each category, what values are valid, what shipping profile to use for a DVD vs a vinyl record. It's a reference data skill with no Chrome automation.

### Why two instead of one?

| Concern | Single skill | Two skills |
|---------|-------------|------------|
| Chrome patterns change (Whatnot redesign) | Edit one big file | Edit `whatnot-chrome` only |
| New category onboarded (Vinyl Records) | Edit one big file | Add to `whatnot-catalog` only |
| Non-Whatnot skill needs shipping data | Can't reuse | Import `whatnot-catalog` reference |
| `rg-full-auto` Phase 8 calls | One dependency | Two explicit dependencies |
| Skill size | ~300 lines | ~120 + ~180 lines |

The two-skill approach also mirrors existing patterns: `square-image-upload` (automation) is separate from `catalog-classifier` (reference data).

---

## 3. Skill 1: `whatnot-chrome` — Chrome Automation Primitives

### 3.1 Frontmatter

```yaml
---
name: whatnot-chrome
description: Chrome automation patterns for Whatnot dashboard — inventory navigation, React combobox interaction, CSV import, batch field editing, and page save workflows. Use when automating any Whatnot dashboard action via Claude in Chrome. Triggers on "whatnot edit", "whatnot fields", "fill whatnot", "whatnot automation", "whatnot chrome", "edit whatnot listing". NOT for category/field reference data — use whatnot-catalog for allowed values and field maps.
metadata:
  version: "1.0"
  author: scottybe
  updated: "2026-02-16"
  changelog: |
    v1.0 - Initial extraction from rg-full-auto Phase 8:
    - Extracted Chrome automation patterns from rg-full-auto v3.4
    - Documented React combobox interaction workflow
    - Added inventory navigation patterns
    - Added CSV import via DataTransfer API
    - Added batch field-editing workflow
    - Added page element discovery patterns
---
```

### 3.2 Core Sections

#### Section A: Prerequisites & Tab Setup

```markdown
# Whatnot Chrome Automation

## Prerequisites

- Claude in Chrome MCP tools must be available
- User must be logged into whatnot.com in the browser
- Tab must be in the MCP tab group (use `tabs_context_mcp` to verify)

## Tab Setup

Always start by getting the current tab context:

1. Call `tabs_context_mcp` to get available tabs
2. If no Whatnot tab exists, call `tabs_create_mcp` then `navigate` to `https://www.whatnot.com/dashboard/inventory`
3. Store the tab ID — all subsequent calls use this ID

**⚠️ Tab IDs change between sessions.** Never cache tab IDs across conversations.
```

#### Section B: Inventory Navigation

```markdown
## Inventory Navigation

### Inventory List
**URL:** `https://www.whatnot.com/dashboard/inventory`
**Drafts tab:** `https://www.whatnot.com/dashboard/inventory?tab=drafts`

### Item Edit Page
**URL pattern:** `https://www.whatnot.com/dashboard/inventory/TGlzdGluZ05vZGU6XXXXXXXXXX==`

The path segment is a Base64-encoded Whatnot node ID. You get these by clicking items from the inventory list — there's no way to construct them from SKU or title.

### Navigation Pattern (List → Edit → List)

1. Navigate to inventory list URL
2. Scroll to find the target item (use `find` tool with item title)
3. Click the item to open edit page
4. Make edits (see Combobox Interaction below)
5. Click **Save** button
6. After save, Whatnot auto-returns to inventory list OR navigate back manually
```

#### Section C: React Combobox Interaction (THE critical pattern)

```markdown
## React Combobox Interaction

Whatnot uses React comboboxes for dropdown fields (Genre, Type, Edition, Shipping Profile, etc.). These are NOT standard HTML `<select>` elements.

**⚠️ IMPORTANT:** There are TWO different "Type" fields on Whatnot. The CSV column "Type" = listing type (Buy it Now / Auction / Giveaway). The edit page "Type" dropdown = content type (Movie / Mini Series / TV Series). Always check `whatnot-catalog` to know which values are valid for which field.

### The Pattern (with exact tool calls)

**Example: Setting Genre to "Horror" on a DVD edit page (tab ID = 1781225804)**

Step 1: FIND — Locate the combobox by label
  Tool: `find(query: "Genre combobox", tabId: 1781225804)`
  Returns: ref_8054 (a combobox input element)

Step 2: TYPE — Filter the dropdown options
  Tool: `form_input(ref: "ref_8054", tabId: 1781225804, value: "Horror")`
  Effect: Opens the dropdown AND filters to show only "Horror"

Step 3: CLICK — Select the dropdown option
  Option A (preferred): Take a screenshot to see exact coordinates of the dropdown option
    Tool: `computer(action: "screenshot", tabId: 1781225804)`
    Then: `computer(action: "left_click", coordinate: [163, 634], tabId: 1781225804)`
  Option B (when coordinates are tricky): Use find to locate the option
    Tool: `find(query: "Horror option in dropdown list", tabId: 1781225804)`
    Then: `computer(action: "left_click", ref: "ref_8055", tabId: 1781225804)`

Step 4: VERIFY — Confirm selection persisted
  Tool: `computer(action: "screenshot", tabId: 1781225804)`
  Check: The Genre field should now display "Horror" as the selected value

### Complete Single-Item Example (all fields for a DVD)

On a Movies > DVDs edit page, fill all 4 metadata fields:

1. find("Movie/TV Show Title" input) → form_input(ref, "Boogeyman 2")
2. find("Genre combobox") → form_input(ref, "Horror") → screenshot → click "Horror" option
3. find("Type combobox") → form_input(ref, "Movie") → screenshot → click "Movie" option
4. find("Edition combobox") → form_input(ref, "Unrated") → screenshot → click "Unrated Edition" option
5. Scroll down to Shipping Profile if needed → find("Shipping Profile combobox") → verify it shows "4-7 oz"
6. find("Save button") → click Save
7. Wait for "Product Updated" toast confirmation

### Known Quirks

| Quirk | Symptom | Workaround |
|-------|---------|------------|
| Invalid value typed | "No options available" shown | Stop — this value doesn't exist. Check `whatnot-catalog` for valid values |
| Dropdown closes on scroll | Selected value disappears | Re-open by clicking the combobox, re-type filter text |
| Value doesn't persist after save | Field reverts to empty | Must CLICK a dropdown option — typing alone doesn't update React state |
| Multiple comboboxes on page | Wrong dropdown opens | Scroll to target field first, verify ref matches the right field label |
| Free text field (Movie/TV Show Title) | No dropdown appears | This is correct — it's a text input, not a combobox. Just form_input the value |

### Error Handling

| Situation | Action |
|-----------|--------|
| "No options available" in dropdown | Value is invalid. Stop. Read `whatnot-catalog` for valid values. Do NOT save. |
| Combobox ref not found by `find` | Page may not have loaded. Screenshot to verify. Try scrolling down. Retry `find`. |
| Save button click doesn't trigger toast | Screenshot to check for validation errors. A required field may be missing. |
| After save, field reverted to empty | You typed but didn't CLICK a dropdown option. Re-open edit page, redo the field. |
| Session expired (login page shown) | Stop. Tell user to log in again. Then `tabs_context_mcp` to re-acquire tab. |
| Category has TODO in whatnot-catalog | Fields are undocumented for this category. Screenshot the edit page. Ask user what values to use. Document in whatnot-catalog for next time. |

### Anti-Patterns (DO NOT DO)

- **DO NOT** use `javascript_tool` to set `element.value` — React won't pick up the change
- **DO NOT** type a value and press Enter without clicking the dropdown option
- **DO NOT** assume typing "DVD" into a "Type" field will work — always check `whatnot-catalog` for valid values first
- **DO NOT** skip the screenshot verify step — silent failures are the #1 time waster
```

#### Section D: CSV Import Automation

```markdown
## CSV Import via Chrome

### DataTransfer API Injection

Whatnot's CSV import uses a native file picker. Bypass it with JavaScript:

```javascript
// Build CSV content as a string (header + data rows)
const csvContent = `Category,Sub Category,Title,Description,Quantity,Type,Price,Shipping Profile,Offerable,Hazmat,Condition,Cost Per Item,SKU,Image URL 1,Image URL 2,Image URL 3,Image URL 4,Image URL 5,Image URL 6,Image URL 7,Image URL 8
"Movies","DVDs","Item Title","Description",1,Buy it Now,7,4-7 oz,TRUE,Not Hazmat,Good,1,RG-XXXX,https://richmondgeneral.github.io/items/RG-XXXX/hero.png,,,,,,,,`;

const blob = new Blob([csvContent], { type: 'text/csv' });
const file = new File([blob], 'whatnot-import.csv', { type: 'text/csv' });
const fileInput = document.querySelector('input[type="file"]');
const dataTransfer = new DataTransfer();
dataTransfer.items.add(file);
fileInput.files = dataTransfer.files;
fileInput.dispatchEvent(new Event('change', { bubbles: true }));
fileInput.dispatchEvent(new Event('input', { bubbles: true }));
```

### Import Flow

1. Navigate to `https://www.whatnot.com/dashboard/inventory`
2. Find the upload/cloud icon:
   - **Preferred:** `find(query: "import CSV button", tabId: TAB_ID)` or `find(query: "upload icon near Create Product", tabId: TAB_ID)`
   - **Fallback:** Screenshot and click approximate coordinate (1122, 110) — this is layout-dependent and may shift
3. Execute the JavaScript above via `javascript_tool`
4. Modal shows "filename.csv — Ready to import" with yellow **Import** button
5. Click **Import** → server-side validation runs
6. On success: "Your products have successfully imported" with "View Drafts" link
7. Items import as **Drafts** — verify at `?tab=drafts`

### Validation Errors

| Error | Cause | Fix |
|-------|-------|-----|
| "Subcategory not provided" | Category requires a sub-category | Check `whatnot-catalog` hierarchy |
| "Subcategory X is not part of Category Y" | Wrong parent/child pairing | Check `whatnot-catalog` hierarchy |
| "Price must be a positive integer" | Decimal price like `6.50` | Use `ceil(price)` |
| No file input found on page | Whatnot changed their import UI | Screenshot → find the new upload element → adapt selector |
| DataTransfer injection fails silently | File input selector changed | Screenshot the modal → inspect for `input[type="file"]` → update selector |

### Manual Fallback

If Chrome automation fails entirely:
1. Save the CSV content to a local file
2. Tell user: "Please upload `whatnot-import.csv` manually through the Whatnot dashboard → Inventory → Import"
3. Continue to Step 8.3 (metadata editing) after user confirms import
```

#### Section E: Batch Field Editing

```markdown
## Batch Field Editing Pattern

When multiple items need the same field set (e.g., Type = "Movie" on 5 DVDs):

### Fast Single-Field Pass

For setting ONE field across N items:

```
For each item in inventory list:
  1. Click item → opens edit page
  2. Scroll down ~7 ticks to reach the field area
  3. Click the target combobox (use known coordinates if field position is consistent)
  4. Click the option value
  5. Click Save
  6. Auto-return to inventory list → repeat
```

**Estimated time:** ~30 seconds per item for a single field.

### Full Metadata Pass

For setting ALL category-specific fields on each item:

```
For each item in inventory list:
  1. Click item → opens edit page
  2. Scroll down to metadata section
  3. For each field (use whatnot-catalog to know which fields + valid values):
     a. find combobox → form_input filter → click option
  4. Verify Shipping Profile matches whatnot-catalog weight heuristic
  5. Click Save
  6. Return to inventory list → repeat
```

**Estimated time:** ~2 minutes per item for 4-5 fields.

### Publish Drafts Pass

After metadata is filled, drafts need to be published:

```
1. Navigate to ?tab=drafts
2. For each draft item:
   a. Click item
   b. Find and click "Publish" or toggle from Draft to Live
   c. Confirm if prompted
   d. Return to drafts list
```
```

### 3.3 Related Skills

```markdown
## Related Skills

| Skill | Relationship |
|-------|-------------|
| `whatnot-catalog` | Provides valid values for fields this skill fills |
| `rg-full-auto` | Phase 8 delegates to this skill for Chrome ops |
| `rg-item-update` | May call this for Whatnot-side edits to existing items |
```

---

## 4. Skill 2: `whatnot-catalog` — Category & Field Reference

### 4.1 Frontmatter

```yaml
---
name: whatnot-catalog
description: Whatnot catalog reference data — category hierarchy, category-specific metadata fields, allowed dropdown values, shipping profile heuristics, and CSV column mapping. Use when building Whatnot CSV rows, filling metadata fields, or looking up valid values for any Whatnot dropdown. Triggers on "whatnot category", "whatnot fields", "shipping profile", "whatnot allowed values", "whatnot CSV", "what category on whatnot". NOT for Chrome automation — use whatnot-chrome for browser interaction.
metadata:
  version: "1.0"
  author: scottybe
  updated: "2026-02-16"
  changelog: |
    v1.0 - Initial extraction from rg-full-auto Phase 8:
    - Extracted category hierarchy, allowed values, and shipping heuristics
    - Added Movies > DVDs category-specific metadata fields
    - Documented CSV column mapping with field sources
    - Added Type field disambiguation (CSV listing type vs edit page content type)
---
```

### 4.2 Core Sections

#### Section A: CSV Column Reference

```markdown
# Whatnot Catalog Reference

## CSV Import Columns

**Exact header names (must match Whatnot template):**

```
Category,Sub Category,Title,Description,Quantity,Type,Price,Shipping Profile,Offerable,Hazmat,Condition,Cost Per Item,SKU,Image URL 1,Image URL 2,Image URL 3,Image URL 4,Image URL 5,Image URL 6,Image URL 7,Image URL 8
```

### CSV-Level Allowed Values

**Condition:**
`Brand New`, `Like New`, `Very Good`, `Good`, `Fair`, `Poor`

**Type (listing type — NOT content type):**
`Auction`, `Buy it Now`, `Giveaway`

**Shipping Profile (must match dropdown exactly):**
`1-3 oz`, `4-7 oz`, `8-11 oz`, `12-15 oz`, `1 lb`, `1-2 lbs`

**Hazmat:**
`Not Hazmat`

### Price Conversion Rule

Square prices use cents (e.g., `650` = $6.50). Whatnot requires **positive whole-dollar integers**.

**Formula:** `ceil(square_price_cents / 100)`

| Square Price (cents) | Whatnot Price |
|---------------------|---------------|
| 650 | 7 |
| 1050 | 11 |
| 4000 | 40 |
| 1999 | 20 |
```

#### Section B: Category Hierarchy

```markdown
## Category Hierarchy

**⚠️ CRITICAL:** Some items that seem like categories are actually sub-categories. Always verify parent/child relationships.

### Common Richmond General Mappings

| Item Type | Category (parent) | Sub Category | Notes |
|-----------|-------------------|--------------|-------|
| DVDs | `Movies` | `DVDs` | NOT `DVDs` as top-level! |
| VHS tapes | `Movies` | `VHS` | |
| Blu-ray | `Movies` | `Blu-ray` | |
| Movie memorabilia | `Movies` | `Movie Memorabilia` | |
| Rare/vintage books | `Rare & Vintage Books` | _(empty)_ | Top-level, no sub required |
| Vintage toys | `Vintage Toys` | _(varies)_ | Check Values tab |
| Vinyl records | `Vinyl Records` | _(varies)_ | |
| Art | `Art` | _(varies)_ | |

**Full category/sub-category list:** See Values tab (columns E & F) of the [Whatnot CSV template](https://docs.google.com/spreadsheets/d/1UNxbyQoXjpjuqYcCE_Ie94OTCEB7lXR7Yz84aynILW4/edit#gid=0)
```

#### Section C: Category-Specific Metadata Fields

```markdown
## Category-Specific Metadata Fields

These fields appear on the Whatnot **edit page** after CSV import. They CANNOT be set via CSV — they must be filled via Chrome automation (see `whatnot-chrome` skill).

**⚠️ TWO DIFFERENT "TYPE" FIELDS:**

| Field | Where | Values | Meaning |
|-------|-------|--------|---------|
| CSV "Type" column | CSV import | `Buy it Now`, `Auction`, `Giveaway` | Listing format |
| Edit page "Type" dropdown | Edit page only | Varies by category (see below) | Content classification |

These are completely unrelated. The CSV "Type" sets the listing format. The edit page "Type" classifies the content.

---

### Movies > DVDs

| Field | Required | Type | Valid Values | Notes |
|-------|----------|------|-------------|-------|
| Movie/TV Show Title | Yes | Free text | _(any)_ | Use actual film title, not listing title |
| Genre | Yes | Combobox | `Action`, `Comedy`, `Drama`, `Horror`, `Sci-Fi`, `Thriller`, `Romance`, `Documentary`, `Animation`, `Family`, `Western`, `Musical`, `Mystery`, `Adventure`, `Fantasy`, `War`, `Crime` | Typeahead filtering |
| Type (content) | Yes | Combobox | `Movie`, `Mini Series`, `TV Series` | NOT the CSV "Type" |
| Edition | No | Combobox | `Standard Edition`, `Collector's Edition`, `Unrated Edition`, `Special Edition`, `Director's Cut`, `Widescreen Edition`, `Limited Edition`, `Anniversary Edition` | Typeahead filtering |

### Movies > VHS

> **TODO:** Document after first VHS batch onboarding. Expected to share most fields with DVDs.

### Movies > Blu-ray

> **TODO:** Document after first Blu-ray batch. Likely identical to DVDs.

### Vinyl Records

> **TODO:** Document after first vinyl batch. Expected fields: Artist, Album Title, Genre, Speed (33/45/78), Format (LP/EP/Single).

### Rare & Vintage Books

> **TODO:** Document after first book batch. Expected fields: Author, Title, Year, Publisher, Condition Notes.

### Vintage Toys

> **TODO:** Document after first toy batch.
```

#### Section D: Shipping Profile Weight Heuristic

```markdown
## Shipping Profile Weight Heuristic

Use this table to select the correct Shipping Profile value during CSV generation or post-import correction.

### By Item Type

| Item Type | Weight Estimate | Shipping Profile |
|-----------|----------------|-----------------|
| Single DVD (standard case) | ~4-5 oz | `4-7 oz` |
| DVD multi-pack (2-4 discs) | ~5-6 oz | `4-7 oz` |
| DVD box set (5-8 discs) | ~6-7 oz | `4-7 oz` |
| DVD large box set (9+ discs) | ~8-10 oz | `8-11 oz` |
| Single Blu-ray | ~4-5 oz | `4-7 oz` |
| VHS tape (single) | ~8-10 oz | `8-11 oz` |
| Paperback book (under 300 pages) | ~4-7 oz | `4-7 oz` |
| Hardcover book (small) | ~8-12 oz | `8-11 oz` |
| Hardcover book (large/coffee table) | ~1-2 lbs | `1-2 lbs` |
| Vinyl record (single LP in sleeve) | ~8-10 oz | `8-11 oz` |
| Vinyl record (gatefold/double LP) | ~12-14 oz | `12-15 oz` |
| Small collectible / figurine | ~4-6 oz | `4-7 oz` |
| VHS box set (2-3 tapes) | ~14-16 oz | `1 lb` |
| Board game (standard) | ~1-2 lbs | `1-2 lbs` |

### Quick Lookup by Weight

| Actual Weight | Shipping Profile |
|--------------|-----------------|
| Under 3 oz | `1-3 oz` |
| 4-7 oz | `4-7 oz` |
| 8-11 oz | `8-11 oz` |
| 12-15 oz | `12-15 oz` |
| ~1 lb (16 oz) | `1 lb` |
| Over 1 lb | `1-2 lbs` |

> When in doubt, weigh the item. Underestimating loses money on shipping; overestimating deters buyers.
```

### 4.3 Related Skills

```markdown
## Related Skills

| Skill | Relationship |
|-------|-------------|
| `whatnot-chrome` | Uses this skill's values when filling fields via Chrome |
| `rg-full-auto` | Phase 8 uses this for CSV generation and field reference |
| `catalog-classifier` | Square-side classification; this skill handles Whatnot-side |
| `rg-item-update` | May reference this when updating Whatnot listings |
```

---

## 5. Integration: Updating `rg-full-auto` Phase 8

Once both skills exist, Phase 8 of `rg-full-auto` should be refactored to delegate rather than inline.

### 5.1 Current State (v3.4)

Phase 8 is ~160 lines containing:
- CSV column mapping and field sources (→ moves to `whatnot-catalog`)
- Allowed values reference (→ moves to `whatnot-catalog`)
- Category hierarchy (→ moves to `whatnot-catalog`)
- Chrome upload automation (→ moves to `whatnot-chrome`)
- Post-import metadata editing (→ moves to `whatnot-chrome`)
- Shipping heuristic (→ moves to `whatnot-catalog`)
- Price conversion rule (→ moves to `whatnot-catalog`)

### 5.2 Target State (v3.5)

Phase 8 becomes a **thin orchestrator** that delegates to the two Whatnot skills. The word "delegate" means: **read the sub-skill's SKILL.md and follow its instructions using the MCP tools.** See Section 0 for details.

```markdown
## Phase 8: Whatnot Item Library Listing

Run this phase only if the item should be listed on Whatnot.

**Dependencies:** Read these skills before starting:
- `~/.claude/skills/whatnot-catalog/SKILL.md` (field values, category hierarchy, shipping heuristic)
- `~/.claude/skills/whatnot-chrome/SKILL.md` (Chrome automation patterns)

**Account:** richmondgeneral on whatnot.com
**Image hosting:** GitHub Pages — images must be pushed (Step 7.6) before Whatnot can fetch them.

### Step 8.1: Build CSV Row

Read `whatnot-catalog` and look up:
- **Category/Sub Category** from the Category Hierarchy table (e.g., DVDs → Category=`Movies`, Sub Category=`DVDs`)
- **Shipping Profile** from the Weight Heuristic table (e.g., single DVD → `4-7 oz`)
- **Price** converted via `ceil(square_price_cents / 100)`
- **Condition**, **Hazmat** from the CSV-Level Allowed Values section

Append row to batch CSV:
**Batch file:** `/Users/scottybe/workspace/square/items/rg-inventory/whatnot-import.csv`

**CSV must have headers on first row.** If the file doesn't exist yet, create it:
```bash
echo 'Category,Sub Category,Title,Description,Quantity,Type,Price,Shipping Profile,Offerable,Hazmat,Condition,Cost Per Item,SKU,Image URL 1,Image URL 2,Image URL 3,Image URL 4,Image URL 5,Image URL 6,Image URL 7,Image URL 8' > /Users/scottybe/workspace/square/items/rg-inventory/whatnot-import.csv
```

**Append command (example for a DVD):**
```bash
echo '"Movies","DVDs","Item Title","Plain text description",1,Buy it Now,7,4-7 oz,TRUE,Not Hazmat,Good,1,RG-XXXX,https://richmondgeneral.github.io/items/RG-XXXX/hero.png,,,,,,,,' >> /Users/scottybe/workspace/square/items/rg-inventory/whatnot-import.csv
```

### Step 8.2: Upload CSV to Whatnot

Read `whatnot-chrome` section "CSV Import via Chrome" and follow those steps:
1. Get tab context (`tabs_context_mcp`)
2. Navigate to inventory dashboard
3. Find and click the import button
4. Inject CSV via DataTransfer API JavaScript
5. Click Import, wait for success message
6. Verify drafts appear at `?tab=drafts`

**If import fails:** See whatnot-chrome "Validation Errors" and "Manual Fallback" sections.

### Step 8.3: Fill Category-Specific Metadata

Read `whatnot-catalog` section "Category-Specific Metadata Fields" to find which fields exist and their valid values for this item's category.

Read `whatnot-chrome` section "React Combobox Interaction" and follow the pattern for each field.

1. For each imported item:
   a. Click item from inventory/drafts list to open edit page
   b. Fill each metadata field using the combobox pattern (find → form_input → click option → verify)
   c. Check Shipping Profile matches the `whatnot-catalog` weight heuristic — if CSV imported a wrong default, correct it now
   d. Click Save, wait for "Product Updated" toast

**If `whatnot-catalog` has a TODO for this category's fields:**
- Screenshot the edit page to discover what fields exist
- Ask user what values to use
- Fill them manually this time
- After completion, update `whatnot-catalog` SKILL.md with the discovered fields for next time

### Step 8.4: Publish Drafts

Read `whatnot-chrome` section "Publish Drafts Pass" and follow those steps:
1. Navigate to drafts tab
2. For each draft: open → publish → confirm
3. Verify all items show as live on the main inventory tab
```

### 5.3 What Gets Deleted from rg-full-auto

| Section | Lines (approx) | Moves To |
|---------|----------------|----------|
| CSV column mapping table | 845-861 | `whatnot-catalog` |
| Critical gotchas block | 863-867 | `whatnot-catalog` (absorbed into reference) |
| CSV append command | 870-872 | Stays (RG-specific path) |
| Chrome upload steps 1-7 | 880-906 | `whatnot-chrome` |
| Validation error table | 910-914 | `whatnot-chrome` |
| Post-import metadata workflow | 918-951 | `whatnot-chrome` |
| Category-specific fields table | 953-964 | `whatnot-catalog` |
| Shipping weight heuristic | 966-979 | `whatnot-catalog` |
| Category hierarchy reference | 976-994 | `whatnot-catalog` |
| Allowed values reference | 996-1010 | `whatnot-catalog` |
| Price conversion rule | 1012-1022 | `whatnot-catalog` |

**Net result:** Phase 8 goes from ~160 lines to ~40 lines (orchestration only).

---

## 6. Implementation Plan

### Phase 1: Create `whatnot-catalog` (no dependencies)

1. Create skill directory: `~/.claude/skills/whatnot-catalog/`
2. Write `SKILL.md` using Section 4 content above
3. Verify it renders correctly as a standalone reference
4. Register in skill registry

**Estimated effort:** ~15 minutes

### Phase 2: Create `whatnot-chrome` (depends on `whatnot-catalog` existing)

1. Create skill directory: `~/.claude/skills/whatnot-chrome/`
2. Write `SKILL.md` using Section 3 content above
3. Add cross-references to `whatnot-catalog`
4. Register in skill registry

**Estimated effort:** ~15 minutes

### Phase 3: Refactor `rg-full-auto` Phase 8 (depends on both skills)

1. Replace inline content with delegation pattern from Section 5.2
2. Keep the CSV append command (RG-specific file path)
3. Update Related Skills table to include both new skills
4. Bump version to 3.5
5. Update changelog
6. **Test:** Run through a single-item Whatnot onboard to verify the delegation chain works

**Estimated effort:** ~20 minutes

### Phase 4: Update `rg-item-update` (optional)

1. Add Whatnot-side edit capability that delegates to `whatnot-chrome` + `whatnot-catalog`
2. Trigger: "update whatnot listing", "fix whatnot fields"

**Estimated effort:** ~10 minutes

### Rollback Plan

If Phase 3 breaks `rg-full-auto`:
1. `rg-full-auto` is in git at `~/.claude/skills/` — run `git log` to find the v3.4 commit
2. `git checkout <v3.4-commit-hash> -- rg-full-auto/SKILL.md` to restore
3. The two new skills (`whatnot-chrome`, `whatnot-catalog`) can remain — they don't affect anything unless read

---

## 7. Verified Assumptions

These were observed during the Feb 2026 DVD batch (RG-0016–RG-0020):

| Assumption | Status | Evidence |
|------------|--------|----------|
| Base64 node IDs are stable across sessions | ✅ Verified | Same URLs worked across two conversation windows |
| DataTransfer API injection works | ✅ Verified | 5 DVDs imported successfully in one batch |
| All combobox fields use same interaction pattern | ✅ Verified | Genre, Type, Edition, Shipping Profile all worked with find → form_input → click |
| Free text fields (Movie/TV Show Title) accept direct form_input | ✅ Verified | No dropdown needed |
| Save auto-returns to inventory list | ⚠️ Mostly | Worked 9/10 times. Sometimes stays on edit page. Fallback: navigate manually |
| Whatnot category hierarchy is stable | ⚠️ Assumed | Only tested Movies > DVDs. Other categories untested |
| Upload icon is at (1122, 110) | ⚠️ Fragile | Layout-dependent. Use `find` tool first, coordinates as fallback only |

## 8. Testing Strategy

### Smoke Test (after Phase 3)

Onboard one new item through `rg-full-auto` Phase 8 and verify:

1. ✅ CSV row uses correct Shipping Profile from `whatnot-catalog` heuristic
2. ✅ CSV import succeeds via `whatnot-chrome` DataTransfer injection
3. ✅ Post-import metadata fields are filled correctly per `whatnot-catalog` field map
4. ✅ All combobox interactions work per `whatnot-chrome` patterns
5. ✅ Item saves and publishes successfully

### Regression Test

Run `rg-full-auto` Phases 1-9 on a test item to verify no breakage in the non-Whatnot phases.

### Edge Cases to Verify

| Case | Expected Behavior |
|------|------------------|
| Category with no sub-category (Rare & Vintage Books) | Sub Category left empty in CSV |
| Item heavier than 2 lbs | Use `1-2 lbs` (max profile), warn user |
| Unknown category (first Vinyl record) | `whatnot-catalog` TODO section flagged, user prompted for values |
| Chrome not available | `whatnot-chrome` prerequisites section catches this, falls back to manual |
| Whatnot UI redesign | `whatnot-chrome` quirks section needs updating; `whatnot-catalog` unaffected |

---

## 9. Future Enhancements

### 8.1 JavaScript Batch Field Setter

Instead of filling fields one-at-a-time via Chrome MCP tools, build a JavaScript function that sets all category metadata fields in a single `javascript_tool` call. This requires solving the React synthetic event problem:

```javascript
// Conceptual approach — needs testing against Whatnot's React version
function setReactCombobox(labelText, value) {
  const label = [...document.querySelectorAll('label')].find(l => l.textContent.includes(labelText));
  const input = label?.closest('[class*="combobox"]')?.querySelector('input');
  if (!input) return false;

  // Trigger React-compatible events
  const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
  nativeInputValueSetter.call(input, value);
  input.dispatchEvent(new Event('input', { bubbles: true }));
  input.dispatchEvent(new Event('change', { bubbles: true }));

  // Wait for dropdown, then click matching option
  return new Promise(resolve => {
    setTimeout(() => {
      const option = [...document.querySelectorAll('[role="option"]')].find(o => o.textContent.includes(value));
      if (option) { option.click(); resolve(true); }
      else resolve(false);
    }, 300);
  });
}
```

**Priority:** Medium — worth pursuing after the basic two-skill setup is proven.

### 8.2 Whatnot Inventory Scraper

Build a read-only scraper that extracts current Whatnot inventory state into a local JSON/CSV for reconciliation against Square catalog. Could detect:
- Items on Whatnot but not Square (orphans)
- Price mismatches between platforms
- Missing metadata fields

**Priority:** Low — useful for hygiene but not blocking any workflow.

### 8.3 Auto-Publish Workflow

Currently items import as Drafts and need manual publishing. Add a `whatnot-chrome` section for batch-publishing all drafts.

**Priority:** High — should be included in v1.0 of `whatnot-chrome` (added to Section 3 above as Batch Field Editing → Publish Drafts Pass).

---

## 10. Decision Log

| Decision | Rationale | Alternatives Considered |
|----------|-----------|------------------------|
| Two skills instead of one | Clean separation of concerns; Chrome patterns change independently of catalog data | Single `whatnot` skill (rejected: too monolithic) |
| Extract from rg-full-auto instead of duplicate | Single source of truth; rg-full-auto becomes thinner and more maintainable | Keep inline in rg-full-auto (rejected: already 1100+ lines) |
| Reference data in SKILL.md instead of external JSON | Skills are markdown-first; Claude reads them naturally; no parsing needed | JSON data files (rejected: adds complexity, Claude reads markdown better) |
| Defer JavaScript batch setter to future | React event dispatching is fragile and untested against Whatnot's specific React setup | Build now (rejected: risk of brittle code without testing) |
| Keep CSV append command in rg-full-auto | The file path is RG-specific, not Whatnot-generic | Move to whatnot-chrome (rejected: path is inventory-specific) |
