# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Repository Overview

This is a "skills" repository for Claude and Warp AI agents. It contains specialized workflow documentation (SKILL.md files) and tools for managing Richmond General (RG) vintage/antique inventory, Square e-commerce operations, and Linear project management. The repository serves as a knowledge base and automation hub for business operations.

## Repository Structure

```
~/.claude/skills/
├── rg-full-auto/           # Complete 7-phase workflow for new item onboarding
│   ├── SKILL.md            # Main workflow documentation
│   └── references/         # Supporting documentation
│       ├── label-format.md      # Print Master CSV and label layouts
│       ├── lot-tracking.md      # Estate/auction cost allocation
│       ├── pricing-guidelines.md # Margin targets and research methods
│       └── square-catalog.md    # Square API reference
├── rg-item-update/         # Quick edits to existing catalog items
│   └── SKILL.md
├── catalog-classifier/     # Category assignment logic
│   └── SKILL.md
└── linear-initiatives-mcp/ # Model Context Protocol server for Linear
    ├── index.js            # MCP server implementation
    ├── package.json
    └── node_modules/
```

## Key Concepts

### Skills System
SKILL.md files define specialized workflows with:
- **name**: Unique identifier
- **description**: When to use this skill (includes trigger phrases)
- **Content**: Step-by-step procedures, API specs, business rules

Skills are meant to be invoked by AI agents when keywords match, creating a routing system for complex multi-step operations.

### Richmond General (RG) Workflows
Business context: Vintage/antique resale operation using Square for e-commerce
- **rg-full-auto**: New item onboarding (appraisal → photography → catalog → fulfillment → labels → publishing)
- **rg-item-update**: Modify existing items (price, description, images, category)
- **catalog-classifier**: Determine which Square category an item belongs to

Critical IDs (used throughout):
- Square Location: `B87BAEZ0NWV34` (Richmond General)
- Merchant ID: `7MM9AFJAD0XHW`
- Categories: 
  - The Real Rarities: `FL4L42RRUE5UXMWFDLXOCNB5` (rare/pre-1950/significant)
  - The New Finds: `P34KX3L7XRZJJ5RP6W35K4YO` (standard vintage)

### Linear Initiatives MCP Server
A Node.js MCP server providing tools to create, list, update, archive, and link Linear initiatives via GraphQL API.

## Common Development Commands

### Linear Initiatives MCP
```bash
# Install dependencies
cd linear-initiatives-mcp && npm install

# Run the MCP server
npm start

# Test locally (requires LINEAR_API_KEY env var)
export LINEAR_API_KEY="lin_api_xxxxxxxxxxxxx"
node index.js
```

### MCP Configuration
Add to `~/.config/warp/mcp_config.json`:
```json
{
  "mcpServers": {
    "linear-initiatives": {
      "command": "node",
      "args": ["/Users/scottybe/.claude/skills/linear-initiatives-mcp/index.js"],
      "env": {
        "LINEAR_API_KEY": "your_linear_api_key_here"
      }
    }
  }
}
```

Or for Claude Desktop (`~/Library/Application Support/Claude/claude_desktop_config.json`).

### Git Operations
```bash
# The repository is tracked in Git
git status
git add .
git commit -m "Description" # Include Co-Authored-By: Warp <agent@warp.dev>
git push
```

## Architecture & Integration Points

### Square API Integration
All RG workflows interact with Square's REST API via MCP tools. Key operations:
- **catalog.batchInsertObjects**: Create items
- **catalog.batchUpdateObjects**: Update items (use `sparse_update: true`)
- **inventory.batchChange**: Set inventory counts (required after item creation)
- **checkout.createPaymentLink**: Generate square.link URLs

Image uploads are NOT supported via MCP (multipart form limitation) - generate curl commands for users instead.

### Linear GraphQL Integration
The MCP server (`linear-initiatives-mcp/index.js`) wraps Linear's GraphQL API with 7 tools:
- create_initiative, list_initiatives, get_initiative, update_initiative
- archive_initiative, link_project_to_initiative, create_initiative_update

Uses stdio transport for MCP protocol communication.

### Workflow Dependencies
Phase order matters in rg-full-auto:
1. Appraisal/Research → determines pricing
2. Photography → images needed for catalog
3. Square Catalog → generates SKU
4. Fulfillment → configure shipping
5. Payment Link → generates square.link URL
6. Labels → **requires SKU from phase 3 AND payment link from phase 5**
7. Info Card → publishes to GitHub Pages

Labels cannot be created until both SKU and payment link exist.

### External Assets
- **Label batch file**: `/Users/scottybe/items/rg-labels-batch.csv`
- **Info card site**: https://richmondgeneral.github.io/items/ (static GitHub Pages)
- **Working directory**: `/Users/scottybe/items/` (not in this repo)

### Reference Documents
The `rg-full-auto/references/` directory contains business rules that inform the main workflows:
- **label-format.md**: Print Master CSV structure, 2 layout types (default vs QR)
- **lot-tracking.md**: Cost allocation for estate/auction purchases (L## naming)
- **pricing-guidelines.md**: Margin targets by category, research sources
- **square-catalog.md**: API reference, category IDs, tax config

When modifying workflows, check if reference docs need updates.

## Environment & Secrets

### Required Environment Variables
```bash
# Linear MCP server
LINEAR_API_KEY="lin_api_xxxxxxxxxxxxx"  # Get from https://linear.app/settings/api

# Square API (stored in ~/.zshrc for curl commands)
SQUARE_ACCESS_TOKEN="your_square_token"
```

Never commit secrets to git. Square API calls via MCP use system-configured credentials.

## Testing

No automated tests exist. Validation is manual:
- Test Linear MCP: Run `npm start` and verify connection
- Test Square operations: Use actual Square sandbox/production (no test mode configured)
- Verify workflows: Execute SKILL.md steps and check Square dashboard

## Business Rules

### Category Assignment Logic (catalog-classifier)
Decision tree:
1. Food/snack → Snack Categories
2. French/Paris/🇫🇷 → TVM Categories
3. Tech/Digital → TBDL Categories
4. Wellness/Spiritual → Wellness Categories
5. General Vintage → RG Categories
   - Pre-1950 + Maker + Provenance → The Real Rarities
   - Standard vintage → The New Finds

### Label QR Code Decision
Include QR when:
- Pre-1950 antiques
- Collectibles with story/provenance
- Items with info cards on GitHub Pages

Omit for basic/common items and quick-flips.

### Pricing Strategy
- Quick flip ($1-5 cost): 2.5-3x multiplier
- Mid-range ($5-25 cost): 3-4x multiplier
- Showcase ($25+ cost): Research-based

Research via eBay Sold (most reliable), Worthpoint, LiveAuctioneers.

## Notes for AI Agents

1. **Skill Invocation**: When user mentions keywords in SKILL.md descriptions (e.g., "new item", "full workflow", "update price"), invoke the corresponding skill workflow.

2. **Square API Patterns**:
   - Always use `idempotency_key` (UUID v4)
   - Prices in cents (integer): $19.99 = 1999
   - Must set inventory after item creation or item shows "sold out"
   - Use `sparse_update: true` for updates to avoid overwriting fields

3. **Image Uploads**: Cannot use MCP tools. Generate curl commands like:
   ```bash
   curl -X POST "https://connect.squareup.com/v2/catalog/images" \
     -H "Authorization: Bearer $SQUARE_ACCESS_TOKEN" \
     -F "request={...};type=application/json" \
     -F "image_file=@filename.jpeg;type=image/jpeg"
   ```

4. **Multi-Brand Support**: The catalog-classifier supports 4 brands (TVM, RG, TBDL, Snacks) with different category IDs. Richmond General is the primary brand in this repo.

5. **Linear MCP**: Uses stdio transport. Errors logged to stderr. Requires restart if LINEAR_API_KEY changes.

6. **Lot Tracking**: When items come from estate/auction lots, use L## prefix and allocate costs per rg-full-auto/references/lot-tracking.md

7. **Version Control**: Always include `Co-Authored-By: Warp <agent@warp.dev>` in commit messages when committing changes.
