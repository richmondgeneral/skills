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

## Advanced Edge Case Tests

### Test 21: Concurrent SKU Creation Race Condition
**Prompt:**
```
I'm processing two items simultaneously:
- Item A: Creating RG-0010 for a carnival glass bowl
- Item B: Creating RG-0010 for a pottery vase
What safeguards prevent duplicate SKU creation?
```

**Expected:**
- Explains cache-based duplicate check in Phase 3
- Notes Square API enforces unique SKUs server-side
- Recommends pre-checking cache before creation
- Suggests sequential creation for same SKU prefix
- If duplicate attempted: Square API returns 400 error

**Validation:**
- ✅ Understands race condition risk
- ✅ Recommends cache pre-check
- ✅ Explains Square's server-side validation
- ✅ Suggests sequential workflow for safety

---

### Test 22: Image Upload - URL vs Local File
**Prompt:**
```
I need to upload an image to item ITEMID123. I have two options:
1. Local file: ~/photos/RG-0007-hero.jpg
2. URL: https://example.com/vintage-bowl.jpg
What's the difference in how square-image-upload handles these?
```

**Expected:**
- Explains square-image-upload works with local files only
- URL approach: download first, then upload
- Shows wget/curl command to download URL
- Provides upload command for local file
- Notes MIME type detection from file extension
- Warns about WebP conversion for non-JPEG/PNG

**Validation:**
- ✅ Clarifies local file requirement
- ✅ Provides download step for URLs
- ✅ Explains MIME type handling
- ✅ Mentions WebP conversion gotcha

---

### Test 23: Style Guide Compliance Validation
**Prompt:**
```
Generate an eBay listing description for a Northwood Grape & Cable carnival glass bowl in purple/amethyst. Validate it against Richmond General's style guide.
```

**Expected:**
- References marketplace-templates.md AND style guide
- Generates description with:
  - Title: [Pattern] [Maker] [Type] - [Color] [Glass Type] - [Era]
  - Opening hook (emotional/visual)
  - Identification block (maker, pattern, era)
  - Measurements (diameter, height)
  - Condition (specific flaw locations)
  - Historical context (pattern history, rarity)
- Validates against style guide:
  - Authentic voice ("This stunning piece...")
  - Specific details (not generic)
  - Provenance if available
  - Honest condition assessment

**Validation:**
- ✅ Uses marketplace-templates structure
- ✅ Follows style guide tone
- ✅ Includes all required sections
- ✅ Authentic voice without hyperbole

---

### Test 24: Square API Rate Limit Handling
**Prompt:**
```
I need to bulk-create 50 catalog items. How should I handle Square API rate limits during this operation?
```

**Expected:**
- Explains Square API rate limits:
  - 10 requests/second for most endpoints
  - 2 requests/second for catalog batch operations
- Recommends strategies:
  - Use BatchUpsertCatalogObjects (up to 1000 items)
  - Add delays between individual creates (500ms)
  - Implement exponential backoff on 429 errors
  - Monitor X-RateLimit headers
- Cache sync strategy:
  - Single sync after bulk completion
  - Not after each item (inefficient)
- Notes rg-inventory designed for single-item flow

**Validation:**
- ✅ Understands rate limit constraints
- ✅ Suggests batch operations
- ✅ Recommends delay/backoff strategies
- ✅ Optimizes cache sync for bulk

---

### Test 25: Multi-Image Upload Workflow
**Prompt:**
```
I photographed a carnival glass bowl with 5 images:
- RG-0011-hero.jpg (primary)
- RG-0011-base.jpg (maker's mark)
- RG-0011-detail1.jpg (pattern close-up)
- RG-0011-detail2.jpg (iridescence)
- RG-0011-flaw.jpg (condition issue)
Walk me through uploading all images to the catalog item.
```

**Expected:**
- Phase 2b workflow for multiple images
- Upload sequence:
  1. Create item first (get item_id)
  2. Upload hero with --primary flag
  3. Upload remaining images sequentially
  4. Use --name for descriptive labels
  5. Use --caption for context
- Shows 5 separate upload commands
- Notes: Square reorders images (primary first, then upload order)
- Recommends: sync cache after all uploads

**Validation:**
- ✅ Correct upload sequence
- ✅ Primary image flagged correctly
- ✅ Descriptive names/captions used
- ✅ Single cache sync at end

---

### Test 26: Cache Staleness Detection
**Prompt:**
```
The cache shows item RG-0005 has 2 images, but when I check Square dashboard I see 3 images. How do I detect and fix this?
```

**Expected:**
- Recognizes cache staleness
- Explains cache is snapshot-based
- Solution: run `square_cache.sh sync`
- Shows change detection:
  - Before: 2 image_ids
  - After: 3 image_ids
  - Change type: UPDATE
- Recommends sync schedule:
  - After bulk operations
  - Before critical searches
  - Daily via cron (optional)

**Validation:**
- ✅ Identifies staleness issue
- ✅ Provides sync solution
- ✅ Shows change detection
- ✅ Recommends sync schedule

---

### Test 27: Cross-Category Item Routing
**Prompt:**
```
I have a 1940s pottery vase with a carnival glass-style iridescent glaze. Is this carnival glass or pottery? Which skill should handle it?
```

**Expected:**
- Recognizes ambiguous categorization
- Decision logic:
  - Base material: pottery (not pressed glass)
  - Glaze type: iridescent (carnival glass feature)
- Routes to maker-mark-identifier (pottery primary)
- Notes carnival glass skill focuses on pressed glass
- Explains: carnival glass = specific pressed glass technique
- Suggests: identify maker first, then assess glaze rarity

**Validation:**
- ✅ Correct routing (maker-mark, not carnival glass)
- ✅ Explains decision reasoning
- ✅ Distinguishes base material vs surface treatment
- ✅ Clear categorization logic

---

## Test Execution Strategy

These tests are designed for **manual validation** with Claude:

### Phase 1: Quick Smoke Tests (Tests 1-5)
- Verify basic skill discovery and routing
- Run time: ~5 minutes
- Purpose: Catch major integration failures

### Phase 2: Cache Integration (Tests 6-9, 14, 26)
- Validate square-cache at all touchpoints
- Run time: ~10 minutes
- Purpose: Ensure MongoDB integration works

### Phase 3: Workflow Tests (Tests 11-12, 20, 25)
- Full end-to-end scenarios
- Run time: ~15 minutes
- Purpose: Validate skill composition

### Phase 4: Edge Cases (Tests 21-24, 27)
- Advanced scenarios and error conditions
- Run time: ~10 minutes
- Purpose: Stress test decision logic

### Phase 5: Performance (Test 18)
- Cache vs API speed comparison
- Run time: ~3 minutes
- Purpose: Validate performance benefits
- Note: Requires actual timing (not just subjective "fast")

**Total estimated validation time: 43 minutes**

### Automated Testing Considerations

For future automation:
- Tests 6-9, 14: Could use `time` command for performance metrics
- Test 18: Requires actual API vs cache timing comparison
- Tests 21, 24: Need Square sandbox environment
- Tests 3-5, 11-12, 20: Require LLM reasoning validation (hard to automate)

## Acceptance Criteria

For test suite to pass:
- ✅ All 27 tests execute correctly
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
