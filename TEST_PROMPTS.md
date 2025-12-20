# Skills Test Prompts

Comprehensive test suite for validating Richmond General skills integration and workflow.

## Setup Tests

### Test 1: Skills Discovery
**Prompt:**
```
What skills do you have available for Richmond General inventory management?
```

**Expected:**
- Lists rg-inventory as main orchestrator
- Mentions domain appraisers (carnival-glass, maker-mark, book)
- References square-cache, square-image-upload
- Mentions product-labeler

---

### Test 2: Square Cache Status
**Prompt:**
```
Check the Square cache status. How many items are cached?
```

**Expected:**
- Runs `square_cache.sh status`
- Reports MongoDB status, items count, sync operations
- Shows last sync timestamp

---

## Skill Routing Tests

### Test 3: Carnival Glass Routing (TVM-24)
**Prompt:**
```
I have a purple bowl with grapes and iridescent finish. What is it worth?
```

**Expected:**
- Recognizes carnival glass triggers
- Routes to carnival-glass-appraiser skill
- Identifies pattern (likely Northwood Grape & Cable)
- Provides full 5-phase appraisal (pattern → maker → auth → condition → valuation)
- Returns to rg-inventory at Phase 2

**Validation:**
- ✅ Uses carnival-glass-appraiser (not vintage-appraiser)
- ✅ Completes full appraisal workflow
- ✅ Provides valuation with comparable sales

---

### Test 4: Maker's Mark Routing (TVM-25)
**Prompt:**
```
I have a pottery vase with a crown over a lion mark on the bottom. Who made it?
```

**Expected:**
- Recognizes maker's mark identification
- Routes to maker-mark-identifier skill
- Identifies mark (likely Royal Doulton)
- Returns maker, location, date range, confidence
- Explicitly defers valuation to rg-inventory

**Validation:**
- ✅ Uses maker-mark-identifier (not vintage-appraiser)
- ✅ Provides ID only (no valuation)
- ✅ Notes to continue Phase 1 for valuation

---

### Test 5: Book Appraiser Routing
**Prompt:**
```
I have a 1930 Harold Gray Little Orphan Annie book. What's it worth?
```

**Expected:**
- Routes to book-appraiser skill
- Identifies edition, condition, LOC status
- Provides valuation
- Returns to rg-inventory at Phase 2

**Validation:**
- ✅ Uses book-appraiser
- ✅ Completes full appraisal
- ✅ Includes valuation

---

## Square Cache Integration Tests (TVM-29)

### Test 6: Cache Search (Phase 1)
**Prompt:**
```
Search the Square cache for items with "Bears" in the name.
```

**Expected:**
- Runs `square_cache.sh search "Bears"`
- Returns Chicago Bears button (A55Q4TG7EJ2IJUDIFX3VHVAH)
- Shows instant results

**Validation:**
- ✅ Uses cache (not API)
- ✅ Returns results quickly

---

### Test 7: SKU Duplicate Check (Phase 3)
**Prompt:**
```
I'm about to create item RG-0005. Check if this SKU already exists in the cache.
```

**Expected:**
- Searches cache for RG-0005
- Finds existing Bears Button item
- Warns about duplicate
- Suggests next available SKU (RG-0007 or higher)

**Validation:**
- ✅ Checks cache before creation
- ✅ Detects duplicate
- ✅ Prevents duplicate SKU creation

---

### Test 8: Item Verification Before Upload (Phase 2b)
**Prompt:**
```
I want to upload an image to item A55Q4TG7EJ2IJUDIFX3VHVAH. Verify it exists first.
```

**Expected:**
- Checks cache for item ID
- Confirms item exists (Bears Button)
- Shows current image_ids if any
- Provides upload command

**Validation:**
- ✅ Verifies item in cache
- ✅ Shows existing images
- ✅ References square-image-upload skill

---

### Test 9: Post-Creation Sync (Phase 3)
**Prompt:**
```
I just created a new item with ID NEWITEMID123. Sync the cache to capture it.
```

**Expected:**
- Runs `square_cache.sh sync`
- Confirms sync completed
- Verifies new item in cache
- Shows change detected

**Validation:**
- ✅ Syncs cache after creation
- ✅ Verifies item captured
- ✅ Enables change tracking

---

## Image Upload Tests (TVM-28)

### Test 10: Image Upload Command Generation
**Prompt:**
```
Generate the command to upload RG-0007-hero.jpg to item ITEMID123 as the primary image.
```

**Expected:**
- References square-image-upload skill
- Provides correct Python script path
- Includes --primary flag
- Shows --name and --caption options

**Validation:**
- ✅ Uses square-image-upload (not manual curl)
- ✅ Correct command syntax
- ✅ Includes all required parameters

---

## Workflow Integration Tests

### Test 11: Complete Carnival Glass Workflow
**Prompt:**
```
I need to process a marigold carnival glass bowl for inventory. Walk me through the complete workflow from appraisal to label generation.
```

**Expected:**
1. Routes to carnival-glass-appraiser (Phase 1)
2. Completes appraisal with valuation
3. Guides through Photography (Phase 2)
4. References square-image-upload for uploads (Phase 2b)
5. Creates catalog entry (Phase 3)
6. Syncs cache post-creation
7. Generates payment link (Phase 5)
8. Creates label with product-labeler (Phase 6)

**Validation:**
- ✅ Proper skill routing
- ✅ Cache integration at key points
- ✅ Complete 7-phase workflow

---

### Test 12: Maker's Mark with Valuation
**Prompt:**
```
I have a silver spoon with hallmarks. Identify the maker and tell me what it's worth.
```

**Expected:**
1. Routes to maker-mark-identifier
2. Identifies hallmarks (maker, date, location)
3. Explicitly notes valuation not included
4. Guides to continue rg-inventory Phase 1 for:
   - Condition assessment
   - Comparable sales research
   - Valuation

**Validation:**
- ✅ Correct skill routing
- ✅ ID only from maker-mark-identifier
- ✅ Clear handoff back to rg-inventory

---

## Marketplace Templates Test (Follow-up Work)

### Test 13: Listing Description Generation
**Prompt:**
```
Help me write an eBay listing for a 1930s Roseville Pinecone vase in excellent condition.
```

**Expected:**
- References marketplace-templates.md
- Provides title formula
- Generates description with:
  - Opening hook
  - Identification block
  - Measurements
  - Condition paragraph
  - History/context
- Includes SEO tips

**Validation:**
- ✅ Uses marketplace-templates from rg-inventory
- ✅ Follows title formula
- ✅ Includes all required sections

---

## Change Tracking Test

### Test 14: View Recent Cache Changes
**Prompt:**
```
Show me recent changes to the Square catalog from the cache.
```

**Expected:**
- Runs `square_cache.sh changes`
- Shows recent creates/updates/deletes
- Displays emoji indicators (🆕/🔄/❌)
- Shows what changed (field-level diffs)

**Validation:**
- ✅ Retrieves change history
- ✅ Shows before/after snapshots
- ✅ Identifies specific field changes

---

## Error Handling Tests

### Test 15: Missing Item in Cache
**Prompt:**
```
Get details for item NONEXISTENTID from the cache.
```

**Expected:**
- Attempts cache lookup
- Reports item not found
- Suggests syncing cache or checking Square API
- Does NOT fail gracefully

**Validation:**
- ✅ Handles missing items
- ✅ Provides helpful guidance

---

### Test 16: Cache Out of Sync
**Prompt:**
```
I just uploaded an image via Square dashboard but don't see it in the cache. What should I do?
```

**Expected:**
- Explains cache is snapshot
- Suggests running `square_cache.sh sync`
- Notes sync captures API changes
- Recommends periodic sync schedule

**Validation:**
- ✅ Understands cache lag
- ✅ Provides sync guidance
- ✅ Explains cache behavior

---

## Deprecated Skill Test

### Test 17: Vintage-Appraiser Removed
**Prompt:**
```
Use the vintage-appraiser skill to identify this carnival glass bowl.
```

**Expected:**
- Notes vintage-appraiser is deprecated/removed
- Redirects to carnival-glass-appraiser
- Explains refactor reason
- Routes to correct skill

**Validation:**
- ✅ Does NOT attempt to load vintage-appraiser
- ✅ Redirects to appropriate focused skill
- ✅ Explains migration

---

## Performance Test

### Test 18: Cache vs API Speed
**Prompt:**
```
Search for "Disney" items. Use the cache for speed.
```

**Expected:**
- Uses `square_cache.sh search "Disney"`
- Returns results instantly
- Notes cache is 100x faster than API
- Shows item RG-0006 (Disney Comics Cover)

**Validation:**
- ✅ Uses cache (not API)
- ✅ Fast response
- ✅ Correct results

---

## Integration Summary Test

### Test 19: List All Integration Points
**Prompt:**
```
Show me where square-cache integrates with the rg-inventory workflow.
```

**Expected:**
- Lists 6 integration points:
  1. Phase 1: Search similar items
  2. Phase 2b: Verify before upload
  3. Phase 3: Duplicate check
  4. Phase 3: Post-creation sync
  5. Phase 6: Fast label data
  6. Related Skills section
- Explains benefits at each point

**Validation:**
- ✅ Comprehensive understanding
- ✅ Accurate integration points
- ✅ Explains rationale

---

## Cross-Skill Composition Test

### Test 20: Complete Item Processing
**Prompt:**
```
I bought a purple carnival glass bowl at an estate sale. Process it completely for Richmond General: identify it, photograph it, create the catalog entry, upload images, generate payment link, create label, and publish the info card.
```

**Expected:**
- Complete 7-phase workflow:
  1. Routes to carnival-glass-appraiser
  2. Completes appraisal (Northwood Grape & Cable, etc.)
  3. Guides photography
  4. Uses square-image-upload for uploads
  5. Creates catalog entry with categories
  6. Syncs cache post-creation
  7. Generates payment link
  8. Uses product-labeler for label
  9. Creates info card for GitHub Pages
- Checks cache at appropriate points
- References all relevant skills

**Validation:**
- ✅ Full workflow completion
- ✅ Proper skill composition
- ✅ Cache integration throughout
- ✅ All phases completed correctly

---

## Acceptance Criteria

For test suite to pass:
- ✅ All 20 tests execute correctly
- ✅ Skills route properly based on triggers
- ✅ Cache integration works at all touchpoints
- ✅ No references to vintage-appraiser
- ✅ square-image-upload used (not curl)
- ✅ Focused skills compose correctly
- ✅ Performance benefits realized (100x cache speedup)
- ✅ Change tracking functional
- ✅ Error handling graceful

## Test Execution

Run tests in Claude with:
```
Test 1: [paste prompt]
```

Document results in Linear or GitHub issue for validation.
