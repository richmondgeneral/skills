---
name: rg-new-item
description: Process new Richmond General items from photo to live listing. Use when the user provides an item photo and wants to create a complete listing including Square catalog, payment link, and GitHub Pages card. Triggers on "new item", "process this photo", "add to inventory", "create listing", or when user uploads a product photo for Richmond General. Claude-supervised workflow with user approval at key phases.
---

# Richmond General - New Item Workflow

Complete Claude-supervised workflow for processing vintage/antique items from a single photo to live listing.

## When to Use This Skill

Load this skill when:
- User provides a product photo (iPhone photo, uploaded image)
- User says "new item", "add to inventory", "process this"
- User wants to create a Square catalog listing from a photo
- User wants to publish an item to the Richmond General GitHub Pages site

## Workflow Overview

**7-Phase Process** (Claude supervises, user approves key steps):

1. **Appraisal & Research** - Claude analyzes photo visually
2. **Photography** - Background removal via remove.bg API
3. **Square Catalog** - Create item with categories, pricing, SEO
4. **Image Upload** - Attach processed photo to Square item
5. **Fulfillment** - Determine shipping vs pickup (manual Square Dashboard)
6. **Payment Link** - Generate Square checkout link
7. **Publishing** - Deploy to GitHub Pages with QR code

## Claude's Role

When user provides an image, Claude should:
1. **Analyze the photo** - Identify item, era, condition, maker
2. **Research pricing** - Look up comparable sales
3. **Ask for confirmation** - Present findings, get approval
4. **Execute workflow** - Run scripts with user supervision
5. **Handle errors** - Catch issues, retry, or escalate

## Environment Variables Required

```bash
# Add to ~/.zshrc or ~/.bashrc
export SQUARE_ACCESS_TOKEN="your_production_token"
export REMOVEBG_API_KEY="your_removebg_api_key"
```

## Quick Start (Claude's Internal Workflow)

### Phase 1: Appraisal & Research

When user uploads image:

```
1. Claude analyzes image visually:
   - What is it? (book, glassware, furniture, etc.)
   - Era/date (look for maker's marks, style indicators)
   - Condition (visible wear, damage, completeness)
   - Special features (signatures, labels, provenance clues)

2. Claude researches pricing:
   - Search eBay sold listings
   - Check auction records
   - Apply pricing tiers (quick flip $1-15, mid-range $15-75, showcase $75+)
   
3. Claude presents findings:
   "This appears to be a [item] from [era]. Based on [markers], 
   I estimate [price]. Condition: [grade]. Shall we proceed?"
```

**Route to domain appraisers when applicable:**
- Books pre-1970 → `book-appraiser` skill
- Carnival glass → `carnival-glass-appraiser` skill  
- Pottery/silver/furniture marks → `maker-mark-identifier` skill

### Phase 2: Photography

```bash
# Claude runs background removal
python3 ~/.claude/skills/rg-new-item/scripts/remove_background.py \
  <image_from_user> \
  assets/working-images/RG-XXXX-hero-converted.png
```

**Files created:**
- `assets/working-images/RG-XXXX-hero.jpeg` (original, tracked in git)
- `RG-XXXX-hero-converted.png` (processed, git-ignored, temporary)

### Phase 3: Square Catalog Creation

Claude collects data and calls Square API:

**Required data:**
- SKU (auto-generate next: RG-0007, RG-0008, etc.)
- Title
- Era
- Price  
- Condition
- Maker/Publisher
- Origin
- Description (HTML with `<br>` tags)
- SEO title, description, permalink

**Script:**
```python
# Claude calls this internally via process_new_item.py
# Creates item in Square with:
# - Both required categories (Timeless Treasures + The New Finds)
# - Reporting category (The New Finds)
# - Tax settings
# - Inventory count = 1
# - SEO metadata
```

**Returns:** `item_id`, `variation_id`

### Phase 4: Image Upload to Square

```bash
# Claude uploads processed image to Square item
python3 ~/.claude/skills/square-image-upload/scripts/upload_image.py \
  --image RG-XXXX-hero-converted.png \
  --item-id <ITEM_ID_FROM_PHASE_3> \
  --name "<Item Title> - Hero" \
  --caption "Front view" \
  --primary
```

**Then deploy to item folder:**
```bash
cp RG-XXXX-hero-converted.png RG-XXXX/hero.png
```

### Phase 5: Payment Link Generation

Claude calls Square API to create payment link:

```json
{
  "idempotency_key": "uuid",
  "quick_pay": {
    "name": "Item Title",
    "price_money": {"amount": 1999, "currency": "USD"},
    "location_id": "B87BAEZ0NWV34"
  },
  "checkout_options": {
    "ask_for_shipping_address": true
  }
}
```

**Returns:** `https://square.link/u/XXXXXXXX`

### Phase 6: Label CSV (Optional)

Add row to `rg-labels-batch.csv`:

```csv
Product Name,Attributes,Price,Condition,Condition Notes,SKU,QR Code URL
"Item Title","Era • Type • Feature",19.99,Good,"Brief notes",RG-0007,https://richmondgeneral.github.io/items/RG-0007/
```

### Phase 7: GitHub Pages Publishing

```bash
# Claude scaffolds the item page
./new-item.sh
# (or manually create RG-XXXX/index.html from template)

# Generate QR code for payment link (Python)
# Claude does this programmatically

# Validate
./validate-item.sh RG-XXXX

# Prompt user: "Ready to deploy? This will commit and push to GitHub."
git add RG-XXXX assets/working-images/RG-XXXX-hero.jpeg
git commit -m "Add RG-XXXX: Item Title"
git push origin main
```

## User Interaction Points

Claude should **pause and ask for approval** at these points:

1. After Phase 1 (Appraisal):
   - "Here's what I found. Price: $X. Proceed?"
   
2. After Phase 2 (Background removed):
   - "Background removed. Review the image?"
   
3. After Phase 3 (Square catalog created):
   - "Catalog item created. Item ID: XXX. Continue?"
   
4. After Phase 5 (Payment link generated):
   - "Payment link: square.link/u/XXX. Proceed to publishing?"
   
5. Before Phase 7 (GitHub commit):
   - "Ready to deploy to GitHub Pages?"

## Scripts Reference

### `scripts/remove_background.py`

Remove background from product images using remove.bg API.

```bash
python3 ~/.claude/skills/rg-new-item/scripts/remove_background.py \
  input.jpeg \
  output.png
```

**Options:**
- `--api-key` - Override REMOVEBG_API_KEY env var

**Returns:** Processed PNG with transparent background

### `scripts/process_new_item.py`

Orchestrates the complete workflow (Phases 1-3 currently implemented).

```bash
python3 ~/.claude/skills/rg-new-item/scripts/process_new_item.py \
  --image photo.jpeg \
  --interactive
```

**Options:**
- `--interactive` - User-supervised mode (default)
- `--auto` - Unsupervised mode (future)

**Current implementation:** Phases 1-3 (Appraisal → Photography → Catalog)
**TODO:** Phases 4-7 (Image upload → Fulfillment → Payment link → Publishing)

## Configuration

### Square Settings

**Location ID:** `B87BAEZ0NWV34` (Richmond General - ACTIVE)

**Required Categories (BOTH):**
- Timeless Treasures: `3N3II4W6Q7AA43RWQGEEWELY`
- The New Finds: `P34KX3L7XRZJJ5RP6W35K4YO` (also reporting category)

**Tax ID:** `LPKEJF7H27NOPK7EE6A5CA7V`

### File Organization

**Working directory:** `/Users/scottybe/Workspace/items/`

**Structure:**
```
items/
├── assets/working-images/     # Original photos (git tracked)
├── RG-XXXX/                   # Item folders
│   ├── index.html            # GitHub Pages card
│   ├── hero.{jpeg|png}       # Deployed image
│   └── qr-code.png           # Payment link QR
├── template/
│   └── rg-item-card-template.html
└── scripts/
    ├── new-item.sh           # Item scaffolding
    └── validate-item.sh      # Pre-deploy validation
```

## Integration with Other Skills

- **rg-inventory** - Parent workflow skill, broader inventory management
- **square-image-upload** - Upload images to Square (Phase 4)
- **square-cache** - Fast catalog searches, duplicate checking
- **book-appraiser** - Domain expert for books
- **carnival-glass-appraiser** - Domain expert for carnival glass
- **maker-mark-identifier** - Identify pottery/silver/furniture marks

## Troubleshooting

### Background Removal Fails

```
Error: API request failed: 403
Response: {"errors":[{"title":"Invalid API key"}]}
```

**Solution:** Check `REMOVEBG_API_KEY` is set:
```bash
echo $REMOVEBG_API_KEY
```

### Square API Errors

**401 Unauthorized:**
- Token expired or invalid
- Check `SQUARE_ACCESS_TOKEN`

**400 Bad Request:**
- Missing required fields
- Check item_data has both categories

### Image Upload Fails

**413 Too Large:**
- Image exceeds 15MB
- Compress before upload: `sips -Z 2000 image.jpeg`

**Unsupported format:**
- WebP not supported by Square
- Convert: `sips -s format jpeg file.webp --out file.jpg`

## Future Enhancements (Phase 2 & 3)

**Phase 2: Update Support (TVM-40)**
- Use Square's Update Catalog Image endpoint (beta)
- Replace existing item photos without breaking payment links

**Phase 3: Batch Processing (TVM-41)**
- Accept multiple images per item (hero, detail, mark, label)
- Intelligent image type detection
- Batch background removal

**Gemini Pro Integration:**
- Upgrade from remove.bg to Gemini Pro Nano B
- Higher quality, flawless results
- Local processing (no API costs)

## API Reference

See `~/.claude/skills/rg-inventory/SKILL.md` for detailed Square API documentation.

## Related Documentation

- Parent skill: `~/.claude/skills/rg-inventory/SKILL.md`
- Image upload: `~/.claude/skills/square-image-upload/SKILL.md`
- Site structure: `/Users/scottybe/Workspace/items/WARP.md`
- Item validation: `/Users/scottybe/Workspace/items/validate-item.sh`
